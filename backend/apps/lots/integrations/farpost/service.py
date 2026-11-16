"""Estimate parts and STO work, then atomically persist the existing repair contract."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, replace
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from redis.exceptions import RedisError

from apps.core.enums import ExternalCacheSource, WorkType
from apps.core.models import ExternalCache
from apps.core.redis_utils import get_redis_client
from apps.lots.integrations.captcha import (
    FarpostCaptchaSolver,
    TesseractImageCaptchaSolver,
)
from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
    FarpostRateLimitedError,
    ParseResult,
    PartCriteria,
    PartOffer,
)
from apps.lots.integrations.farpost.matrix import (
    FIXED_PANELS,
    LABELS,
    PANELS,
    _body_code,
    _operations,
    _panel_codes,
    _search_model,
    _select_best_offer,
    _work_label,
    repair_matrix,
)
from apps.lots.models import DamagedPartItem, FarpostRepairSummary, Lot, ServiceWorkItem
from apps.lots.schemas import FarpostRepairSummary as RepairSchema
from config.settings.config import get_settings

__all__ = [
    "FIXED_PANELS",
    "LABELS",
    "PANELS",
    "_body_code",
    "_cache_key",
    "_search_model",
    "_select_best_offer",
    "_work_label",
    "estimate_repair",
    "repair_matrix",
    "save_repair_estimate",
    "search_cached",
]

logger = logging.getLogger(__name__)

_FARPOST_COOLDOWN_KEY = "yuzu:farpost:cooldown"

_cooldown_lock = threading.Lock()
_local_cooldown_until = 0.0

_FALLBACK_SUBTITLES = {
    "missing_identity": "Статистическая оценка; не определён код кузова",
    "rate_limited": "Статистическая оценка; Farpost временно ограничил выдачу",
    "fetch_error": "Статистическая оценка; источник Farpost временно недоступен",
    "not_found": "Статистическая оценка; на Farpost нет подходящих предложений",
}


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
        and timedelta(0) <= timezone.now() - entry.updated_at <= timedelta(days=1)
    ):
        return previous, True
    return [], True


def _search_cached_with_reason(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool, str]:
    """Read-through cache keyed independently of paint_code with typed fallback reasons."""
    settings = get_settings()
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
        return [], False, "not_found"
    if _is_rate_limit_cooldown_active():
        logger.info("Farpost cooldown active; using fallback for %s", criteria.panel_id)
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, "rate_limited"
    try:
        real_search = getattr(FarpostClient, "search", None)
        if real_search is not None and getattr(type(client), "search", None) is real_search:
            parse_result = client.search_with_metadata(query_criteria, deadline=deadline)
        else:
            parse_result = ParseResult(
                offers=client.search(query_criteria, deadline=deadline),
                exact_feed_count=None,
            )
    except FarpostRateLimitedError as exc:
        logger.warning("Farpost rate limited on %s: %s", criteria.panel_id, exc)
        _activate_rate_limit_cooldown(settings.FARPOST_COOLDOWN_SEC)
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, "rate_limited"
    except FarpostFetchError as exc:
        logger.warning("Farpost search failed for %s: %s", criteria.panel_id, exc)
        stale_offers, stale = _stale_fallback(entry)
        return stale_offers, stale, "fetch_error"

    offers = parse_result.offers
    if offers:
        ExternalCache.objects.update_or_create(
            key=key,
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": [asdict(offer) for offer in offers]},
                "expires_at": timezone.now() + timedelta(hours=settings.FARPOST_CACHE_TTL_HOURS),
            },
        )
        ExternalCache.objects.filter(key=key + ":empty").delete()
        return offers, False, ""

    # Only negative-cache when Farpost confirms 0 listings (or mock/unparsed feed count),
    # never when exactFeedCount > 0 simply had incompatible/unlabeled rows on pages 1-2.
    if parse_result.exact_feed_count is None or parse_result.exact_feed_count == 0:
        ExternalCache.objects.update_or_create(
            key=key + ":empty",
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": []},
                "expires_at": timezone.now() + timedelta(minutes=10),
            },
        )
    return [], False, "not_found"


def search_cached(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool]:
    """Keep successful offers separate from short-lived valid empty results."""
    offers, stale, _reason = _search_cached_with_reason(client, criteria, deadline=deadline)
    return offers, stale


def estimate_repair(lot: Lot, *, client: FarpostClient | None = None) -> RepairSchema:
    settings = get_settings()
    managed = client is None
    image_solver = (
        TesseractImageCaptchaSolver(command=settings.FARPOST_CAPTCHA_OCR_COMMAND)
        if settings.FARPOST_CAPTCHA_OCR_ENABLED
        else None
    )
    active_client = client or FarpostClient(
        timeout_sec=settings.SCRAPER_TIMEOUT_SEC,
        request_interval_sec=settings.SCRAPER_REQUEST_INTERVAL_SEC,
        request_jitter_sec=settings.SCRAPER_REQUEST_JITTER_SEC,
        proxy_ban_sec=settings.SCRAPER_PROXY_BAN_SEC,
        proxy_urls=settings.SCRAPER_PROXY_URLS,
        captcha_solver=FarpostCaptchaSolver(
            max_attempts=settings.FARPOST_CAPTCHA_MAX_ATTEMPTS,
            solve_budget_sec=settings.FARPOST_CAPTCHA_SOLVE_BUDGET_SEC,
            max_workers=settings.FARPOST_CAPTCHA_MAX_WORKERS,
            request_timeout_sec=settings.SCRAPER_TIMEOUT_SEC,
            image_solver=image_solver,
        ),
    )
    deadline = time.monotonic() + settings.FARPOST_BUDGET_SEC
    matrix = repair_matrix()
    parts, works = [], []
    has_color_matched_parts = False
    search_make = (lot.make or "").strip()
    search_model = _search_model(lot.model or "")
    body_code = _body_code(lot)
    paint_code = (lot.paint_code or "").strip().upper()
    if managed and hasattr(type(active_client), "__enter__"):
        active_client.__enter__()
    try:
        for panel, codes in sorted(_panel_codes(list(lot.defects.all())).items()):
            name = FIXED_PANELS.get(panel, PANELS.get(panel, (panel,))[0])
            is_replacement = bool(codes & {"X", "XX"})
            if is_replacement and panel in FIXED_PANELS:
                operations = {WorkType.BODYWORK: matrix["bodywork"]}
            elif is_replacement and panel in PANELS:
                _, part_name, side, position = PANELS[panel]
                criteria = PartCriteria(
                    search_make,
                    search_model,
                    body_code,
                    panel,
                    part_name,
                    side,
                    position,
                    "",
                )
                offers, stale, reason = [], False, "missing_identity"
                if criteria.make and criteria.model and criteria.body_code:
                    offers, stale, reason = _search_cached_with_reason(
                        active_client, criteria, deadline=deadline
                    )
                offer, matched = _select_best_offer(
                    offers,
                    paint_code=paint_code,
                    paint_cost_rub=matrix["paint"],
                    panel=panel,
                    stale=stale,
                )
                has_color_matched_parts |= matched
                if offer and not stale:
                    subtitle = (
                        f"Контрактная деталь в заводской цвет {paint_code}"
                        if matched
                        else "Контрактная деталь; цвет не подтверждён, требуется окраска"
                    )
                elif offer:
                    subtitle = "Предварительная цена из кэша; наличие и цвет не подтверждены"
                else:
                    subtitle = _FALLBACK_SUBTITLES.get(reason, _FALLBACK_SUBTITLES["not_found"])
                parts.append(
                    {
                        "panel_id": panel,
                        "defect_code": "XX" if "XX" in codes else "X",
                        "part_name_ru": name,
                        "subtitle_ru": subtitle,
                        "price_from_rub": offer.price_rub
                        if offer
                        else matrix["parts"].get(panel, matrix["parts"]["default"]),
                        "in_stock_vladivostok": bool(offer and not stale),
                        "is_statistical_fallback": not bool(offer) or stale,
                    }
                )
                operations = {WorkType.MOUNT_DISMOUNT: matrix["mount_dismount"]}
                if panel != "windshield":
                    operations[WorkType.PAINT] = 0 if matched else matrix["paint"]
            else:
                operations = _operations(codes, matrix)
            for kind, amount in operations.items():
                works.append(
                    {
                        "work_type": kind,
                        "label_ru": _work_label(kind, name, panel),
                        "amount_rub": amount,
                        "zero_cost_reason_ru": "не требуется"
                        if kind == WorkType.PAINT and amount == 0
                        else None,
                    }
                )
    finally:
        if managed and hasattr(type(active_client), "__enter__"):
            active_client.__exit__(None, None, None)
    total_parts = sum(part["price_from_rub"] for part in parts)
    total_works = sum(work["amount_rub"] for work in works)
    return RepairSchema(
        parts=parts,
        service_works=works,
        total_parts_from_rub=total_parts,
        total_works_rub=total_works,
        grand_total_repair_rub=total_parts + total_works,
        has_color_matched_parts=has_color_matched_parts,
        included_in_turnkey_hint_ru=(
            "Оценка ремонта; включение в стоимость под ключ определяется расчётом экономики"
        ),
    )


def save_repair_estimate(lot: Lot, *, client: FarpostClient | None = None) -> FarpostRepairSummary:
    estimate = estimate_repair(lot, client=client)
    # Network requests have finished before locking the lot or writing the estimate.
    with transaction.atomic():
        Lot.objects.select_for_update().get(pk=lot.pk)
        summary, _ = FarpostRepairSummary.objects.update_or_create(
            lot=lot, defaults=estimate.model_dump(exclude={"parts", "service_works"})
        )
        summary.parts.all().delete()
        summary.service_works.all().delete()
        DamagedPartItem.objects.bulk_create(
            DamagedPartItem(repair=summary, **part.model_dump()) for part in estimate.parts
        )
        ServiceWorkItem.objects.bulk_create(
            ServiceWorkItem(repair=summary, **work.model_dump()) for work in estimate.service_works
        )
    return summary
