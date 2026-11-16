"""Estimate parts and STO work, then atomically persist the existing repair contract."""

from __future__ import annotations

import logging
import time

from django.db import transaction

from apps.core.enums import PartSourceKind, WorkType
from apps.integrations.captcha import (
    FarpostCaptchaSolver,
    TesseractImageCaptchaSolver,
)
from apps.integrations.farpost.cache import (
    _cache_key,
    _search_cached_with_reason,
    reset_farpost_cooldown,
    search_cached,
)
from apps.integrations.farpost.client import FarpostClient, PartCriteria, PartOffer
from apps.integrations.farpost.matrix import (
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
from apps.integrations.farpost.schemas import FarpostRepairEstimate as RepairSchema
from apps.lots.models import DamagedPartItem, FarpostRepairSummary, Lot, ServiceWorkItem
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
    "reset_farpost_cooldown",
    "save_repair_estimate",
    "search_cached",
]

logger = logging.getLogger(__name__)

_FALLBACK_SUBTITLES = {
    PartSourceKind.MISSING_IDENTITY.value: "Статистическая оценка; не определён код кузова",
    PartSourceKind.RATE_LIMITED.value: "Статистическая оценка; Farpost временно ограничил выдачу",
    PartSourceKind.FETCH_ERROR.value: "Статистическая оценка; источник Farpost временно недоступен",
    PartSourceKind.NOT_FOUND.value: "Статистическая оценка; на Farpost нет подходящих предложений",
}


def _build_farpost_client(settings) -> FarpostClient:
    image_solver = (
        TesseractImageCaptchaSolver(command=settings.FARPOST_CAPTCHA_OCR_COMMAND)
        if settings.FARPOST_CAPTCHA_OCR_ENABLED
        else None
    )
    return FarpostClient(
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


def _describe_part_source(
    offer: PartOffer | None, *, matched: bool, stale: bool, paint_code: str, reason: str
) -> tuple[str, str]:
    if offer and not stale:
        if matched:
            return (
                f"Контрактная деталь в заводской цвет {paint_code}",
                PartSourceKind.FARPOST_COLOR_MATCH.value,
            )
        return (
            "Контрактная деталь; цвет не подтверждён, требуется окраска",
            PartSourceKind.FARPOST_PLAIN.value,
        )
    if offer:
        return (
            "Предварительная цена из кэша; наличие и цвет не подтверждены",
            PartSourceKind.FARPOST_CACHE.value,
        )
    subtitle = _FALLBACK_SUBTITLES.get(reason, _FALLBACK_SUBTITLES[PartSourceKind.NOT_FOUND.value])
    source_kind = reason if reason in _FALLBACK_SUBTITLES else PartSourceKind.MATRIX.value
    return subtitle, source_kind


def _estimate_replacement_panel(
    *,
    active_client: FarpostClient,
    panel: str,
    codes: set[str],
    name: str,
    search_make: str,
    search_model: str,
    body_code: str,
    paint_code: str,
    deadline: float,
    matrix: dict,
) -> tuple[dict, bool, dict[WorkType, int]]:
    _, part_name, side, position = PANELS[panel]
    criteria = PartCriteria(
        search_make, search_model, body_code, panel, part_name, side, position, ""
    )
    offers, stale, reason = [], False, PartSourceKind.MISSING_IDENTITY.value
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
    subtitle, source_kind = _describe_part_source(
        offer, matched=matched, stale=stale, paint_code=paint_code, reason=reason
    )
    part_payload = {
        "panel_id": panel,
        "defect_code": "XX" if "XX" in codes else "X",
        "part_name_ru": name,
        "subtitle_ru": subtitle,
        "source_kind": source_kind,
        "price_from_rub": offer.price_rub
        if offer
        else matrix["parts"].get(panel, matrix["parts"]["default"]),
        "in_stock_vladivostok": bool(offer and not stale),
        "is_statistical_fallback": not bool(offer) or stale,
    }
    operations: dict[WorkType, int] = {WorkType.MOUNT_DISMOUNT: matrix["mount_dismount"]}
    if panel != "windshield":
        operations[WorkType.PAINT] = 0 if matched else matrix["paint"]
    return part_payload, matched, operations


def estimate_repair(lot: Lot, *, client: FarpostClient | None = None) -> RepairSchema:
    settings = get_settings()
    managed = client is None
    active_client = client or _build_farpost_client(settings)
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
                part_payload, matched, operations = _estimate_replacement_panel(
                    active_client=active_client,
                    panel=panel,
                    codes=codes,
                    name=name,
                    search_make=search_make,
                    search_model=search_model,
                    body_code=body_code,
                    paint_code=paint_code,
                    deadline=deadline,
                    matrix=matrix,
                )
                has_color_matched_parts |= matched
                parts.append(part_payload)
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
