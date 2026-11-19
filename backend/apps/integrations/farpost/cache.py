"""Farpost read-through cache, negative cache, and rate-limit cooldown state."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, replace
from datetime import timedelta
from typing import Protocol, runtime_checkable

from django.conf import settings
from django.utils import timezone
from redis.exceptions import RedisError

from apps.core.enums import ExternalCacheSource, PartSourceKind
from apps.core.models import ExternalCache
from apps.core.redis_utils import get_redis_client
from apps.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
    FarpostRateLimitedError,
    ParseResult,
    PartCriteria,
    PartOffer,
)
from apps.integrations.shared.cache import upsert_external_cache

logger = logging.getLogger(__name__)

_FARPOST_COOLDOWN_KEY = "yuzu:farpost:cooldown"
_STALE_CACHE_MAX_AGE = timedelta(days=7)

_cooldown_lock = threading.Lock()
_local_cooldown_until = 0.0


def reset_farpost_cooldown() -> None:
    """Reset in-process Farpost rate-limit cooldown state (for test isolation)."""
    global _local_cooldown_until
    with _cooldown_lock:
        _local_cooldown_until = 0.0


def _cache_key(criteria: PartCriteria) -> str:
    normalized = replace(criteria, paint_code="")
    identity = json.dumps(asdict(normalized), sort_keys=True, ensure_ascii=True).encode()
    return "farpost:parts:v2:" + hashlib.sha256(identity).hexdigest()


def _read_offers(entry: ExternalCache | None) -> list[PartOffer] | None:
    if entry is None or not isinstance(entry.payload, dict):
        return None
    try:
        rows = entry.payload["offers"]
        if not isinstance(rows, list):
            return None
        offers = [
            PartOffer(
                offer_id=row["offer_id"],
                url=row["url"],
                title=row["title"],
                price_rub=row["price_rub"],
                color_matched=row["color_matched"],
                snippet=row.get("snippet", "") if isinstance(row.get("snippet", ""), str) else "",
            )
            for row in rows
        ]
        if any(
            type(o.price_rub) is not int
            or o.price_rub <= 0
            or not o.offer_id
            or type(o.color_matched) is not bool
            or not isinstance(o.url, str)
            or not isinstance(o.title, str)
            for o in offers
        ):
            return None
        return offers
    except (KeyError, TypeError, ValueError):
        return None


def _is_rate_limit_cooldown_active() -> bool:
    with _cooldown_lock:
        if _local_cooldown_until > time.monotonic():
            return True
    redis_client = get_redis_client()
    if redis_client is None:
        return False
    try:
        return bool(redis_client.get(_FARPOST_COOLDOWN_KEY))
    except RedisError as exc:
        logger.debug("Redis cooldown check skipped: %s", exc)
        return False


def _activate_rate_limit_cooldown(cooldown_sec: int) -> None:
    global _local_cooldown_until
    if cooldown_sec <= 0:
        return
    with _cooldown_lock:
        _local_cooldown_until = max(_local_cooldown_until, time.monotonic() + cooldown_sec)
    redis_client = get_redis_client()
    if redis_client is None:
        return
    try:
        redis_client.set(_FARPOST_COOLDOWN_KEY, "1", ex=cooldown_sec)
    except RedisError as exc:
        logger.debug("Redis cooldown store skipped: %s", exc)


def _stale_fallback(entry: ExternalCache | None) -> tuple[list[PartOffer], bool]:
    previous = _read_offers(entry)
    if (
        previous
        and entry is not None
        and timedelta(0) <= timezone.now() - entry.updated_at <= _STALE_CACHE_MAX_AGE
    ):
        return previous, True
    return [], True


@runtime_checkable
class FarpostMetadataSearchClient(Protocol):
    """Protocol for Farpost clients exposing metadata-aware search."""

    def search_with_metadata(self, criteria: PartCriteria, *, deadline: float) -> ParseResult: ...


def _supports_metadata_search(client: object) -> bool:
    return isinstance(client, FarpostMetadataSearchClient) and callable(
        getattr(type(client), "search_with_metadata", None)
    )


def _search_cached_with_reason(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool, str]:
    """Read-through cache keyed independently of paint_code with typed fallback reasons."""
    cooldown_sec = int(getattr(settings, "FARPOST_COOLDOWN_SEC", 45))
    cache_ttl_hours = int(getattr(settings, "FARPOST_CACHE_TTL_HOURS", 24))
    query_criteria = replace(criteria, paint_code="")
    key = _cache_key(query_criteria)
    entry = ExternalCache.objects.filter(key=key, source=ExternalCacheSource.FARPOST).first()
    offers = _read_offers(entry)
    if offers is not None and not entry.is_expired:
        return offers, False, ""
    empty = ExternalCache.objects.filter(
        key=key + ":empty", source=ExternalCacheSource.FARPOST
    ).first()
    if empty is not None and not empty.is_expired:
        return [], False, PartSourceKind.NOT_FOUND.value
    if _is_rate_limit_cooldown_active():
        logger.info("Farpost cooldown active; using fallback for %s", criteria.panel_id)
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, PartSourceKind.RATE_LIMITED.value
    try:
        if _supports_metadata_search(client):
            parse_result = client.search_with_metadata(query_criteria, deadline=deadline)
        else:
            parse_result = ParseResult(
                offers=client.search(query_criteria, deadline=deadline),
                exact_feed_count=None,
            )
    except FarpostRateLimitedError as exc:
        logger.warning("Farpost rate limited on %s: %s", criteria.panel_id, exc)
        if getattr(exc, "triggers_global_cooldown", True):
            _activate_rate_limit_cooldown(cooldown_sec)
            reason = PartSourceKind.RATE_LIMITED.value
        else:
            reason = PartSourceKind.FETCH_ERROR.value
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, reason
    except FarpostFetchError as exc:
        logger.warning("Farpost search failed for %s: %s", criteria.panel_id, exc)
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, PartSourceKind.FETCH_ERROR.value

    offers = parse_result.offers
    if offers:
        upsert_external_cache(
            key,
            source=ExternalCacheSource.FARPOST,
            payload={"offers": [asdict(offer) for offer in offers]},
            ttl=timedelta(hours=cache_ttl_hours),
        )
        ExternalCache.objects.filter(key=key + ":empty").delete()
        return offers, False, ""

    # Only negative-cache when Farpost confirms 0 listings (or mock/unparsed feed count),
    # never when exactFeedCount > 0 simply had incompatible/unlabeled rows on pages 1-2.
    if parse_result.exact_feed_count is None or parse_result.exact_feed_count == 0:
        upsert_external_cache(
            key + ":empty",
            source=ExternalCacheSource.FARPOST,
            payload={"offers": []},
            ttl=timedelta(minutes=10),
        )
    return [], False, PartSourceKind.NOT_FOUND.value


def search_cached(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool]:
    """Keep successful offers separate from short-lived valid empty results."""
    offers, stale, _reason = _search_cached_with_reason(client, criteria, deadline=deadline)
    return offers, stale
