from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.enums import ExternalCacheSource
from apps.lots.integrations.drom.schemas import DromFetchError


def read_drom_cache(key: str, *, allow_stale: bool = False) -> dict[str, Any] | None:
    """Read cached JSON payload from ExternalCache, optionally allowing expired entries."""
    from apps.core.models import ExternalCache

    entry = ExternalCache.objects.filter(key=key).first()
    if entry is None:
        return None
    if not allow_stale and entry.is_expired:
        return None
    return entry.payload if isinstance(entry.payload, dict) else None


def write_drom_cache(key: str, payload: dict[str, Any], *, ttl: timedelta) -> None:
    """Upsert a JSON payload into ExternalCache safely under concurrent threads."""
    from apps.core.models import ExternalCache

    expires_at = timezone.now() + ttl
    defaults = {
        "source": ExternalCacheSource.DROM,
        "payload": payload,
        "expires_at": expires_at,
    }
    try:
        with transaction.atomic():
            ExternalCache.objects.update_or_create(key=key, defaults=defaults)
    except IntegrityError:
        ExternalCache.objects.filter(key=key).update(**defaults, updated_at=timezone.now())


def fetch_with_drom_cache[T](
    key: str,
    *,
    fetcher: Callable[[], T | None],
    serialize: Callable[[T], dict[str, Any]],
    deserialize: Callable[[dict[str, Any]], T | None],
    ttl: timedelta,
    is_cacheable: Callable[[T], bool] | None = None,
    fallback_to_stale_on_empty: bool = True,
    on_error: Callable[[DromFetchError], None] | None = None,
) -> tuple[T | None, bool]:
    """Read-through Drom cache helper with stale fallback on fetch errors or empty results.

    Returns (value, is_stale_fallback).
    """
    fresh_payload = read_drom_cache(key, allow_stale=False)
    if fresh_payload is not None:
        fresh_value = deserialize(fresh_payload)
        if fresh_value is not None:
            return fresh_value, False

    fetch_failed = False
    live_value: T | None = None
    try:
        live_value = fetcher()
    except DromFetchError as exc:
        fetch_failed = True
        if on_error is not None:
            on_error(exc)

    if live_value is not None and (is_cacheable is None or is_cacheable(live_value)):
        write_drom_cache(key, serialize(live_value), ttl=ttl)
        return live_value, False

    if fetch_failed or fallback_to_stale_on_empty:
        stale_payload = read_drom_cache(key, allow_stale=True)
        if stale_payload is not None:
            stale_value = deserialize(stale_payload)
            if stale_value is not None:
                return stale_value, True

    return live_value, False
