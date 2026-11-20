"""Estimate parts and STO work, then atomically persist the existing repair contract."""

from __future__ import annotations

import contextlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection, transaction

if TYPE_CHECKING:
    from collections.abc import Callable

from apps.core.enums import BodyPanel, PartSourceKind, WorkType
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


def _build_farpost_client() -> FarpostClient:
    ocr_enabled = bool(getattr(settings, "FARPOST_CAPTCHA_OCR_ENABLED", False))
    ocr_command = str(getattr(settings, "FARPOST_CAPTCHA_OCR_COMMAND", "tesseract"))
    timeout_sec = float(getattr(settings, "SCRAPER_TIMEOUT_SEC", 10.0))
    image_solver = TesseractImageCaptchaSolver(command=ocr_command) if ocr_enabled else None
    return FarpostClient(
        timeout_sec=timeout_sec,
        request_interval_sec=float(getattr(settings, "SCRAPER_REQUEST_INTERVAL_SEC", 1.2)),
        request_jitter_sec=float(getattr(settings, "SCRAPER_REQUEST_JITTER_SEC", 0.4)),
        proxy_ban_sec=int(getattr(settings, "SCRAPER_PROXY_BAN_SEC", 120)),
        proxy_urls=getattr(settings, "SCRAPER_PROXY_URLS", ()),
        captcha_solver=FarpostCaptchaSolver(
            max_attempts=int(getattr(settings, "FARPOST_CAPTCHA_MAX_ATTEMPTS", 2)),
            solve_budget_sec=float(getattr(settings, "FARPOST_CAPTCHA_SOLVE_BUDGET_SEC", 20.0)),
            max_workers=int(getattr(settings, "FARPOST_CAPTCHA_MAX_WORKERS", 8)),
            request_timeout_sec=timeout_sec,
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


_REPLACEMENT_CODE_RE = re.compile(r"XX?[1-4]?")


def _has_replacement_code(codes: set[str]) -> bool:
    return any(bool(_REPLACEMENT_CODE_RE.fullmatch(code)) for code in codes)


@dataclass(frozen=True, slots=True)
class _RepairContext:
    search_make: str
    search_model: str
    body_code: str
    paint_code: str
    deadline: float
    matrix: dict


def _estimate_replacement_panel(
    *,
    active_client: FarpostClient,
    panel: str,
    codes: set[str],
    name: str,
    ctx: _RepairContext,
) -> tuple[dict, bool, dict[WorkType, int]]:
    _, part_name, side, position = PANELS[panel]
    criteria = PartCriteria(
        ctx.search_make, ctx.search_model, ctx.body_code, panel, part_name, side, position, ""
    )
    offers, stale, reason = [], False, PartSourceKind.MISSING_IDENTITY.value
    if criteria.make and criteria.model and criteria.body_code:
        offers, stale, reason = _search_cached_with_reason(
            active_client, criteria, deadline=ctx.deadline
        )
    offer, matched = _select_best_offer(
        offers,
        paint_code=ctx.paint_code,
        paint_cost_rub=ctx.matrix["paint"],
        panel=panel,
        stale=stale,
    )
    subtitle, source_kind = _describe_part_source(
        offer, matched=matched, stale=stale, paint_code=ctx.paint_code, reason=reason
    )
    part_payload = {
        "panel_id": panel,
        "defect_code": "XX" if any(c.startswith("XX") for c in codes) else "X",
        "part_name_ru": name,
        "subtitle_ru": subtitle,
        "source_kind": source_kind,
        "price_from_rub": offer.price_rub
        if offer
        else ctx.matrix["parts"].get(panel, ctx.matrix["parts"]["default"]),
        "in_stock_vladivostok": bool(offer and not stale),
        "is_statistical_fallback": not bool(offer) or stale,
    }
    operations: dict[WorkType, int] = {WorkType.MOUNT_DISMOUNT: ctx.matrix["mount_dismount"]}
    if panel != "windshield":
        operations[WorkType.PAINT] = 0 if matched else ctx.matrix["paint"]
    return part_payload, matched, operations


def _estimate_panel_isolated(
    factory: Callable[[], FarpostClient],
    *,
    panel: str,
    codes: set[str],
    name: str,
    ctx: _RepairContext,
) -> tuple[dict, bool, dict[WorkType, int]]:
    try:
        with contextlib.ExitStack() as stack:
            worker_client = factory()
            if hasattr(type(worker_client), "__enter__"):
                stack.enter_context(worker_client)
            elif callable(getattr(worker_client, "close", None)):
                stack.callback(worker_client.close)
            return _estimate_replacement_panel(
                active_client=worker_client,
                panel=panel,
                codes=codes,
                name=name,
                ctx=ctx,
            )
    finally:
        if not connection.in_atomic_block:
            connection.close()


def _resolve_replacement_panels(
    *,
    targets: list[tuple[str, set[str], str]],
    client: FarpostClient | None,
    client_factory: Callable[[], FarpostClient] | None,
    proxy_urls: object,
    ctx: _RepairContext,
) -> dict[str, tuple[dict, bool, dict[WorkType, int]]]:
    managed = client is None
    proxy_count = len(proxy_urls) if isinstance(proxy_urls, (list, tuple, set)) else 0
    if len(targets) > 1 and (client_factory is not None or (managed and proxy_count > 1)):
        factory = client_factory or _build_farpost_client
        max_workers = min(len(targets), max(2, proxy_count), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                panel: pool.submit(
                    _estimate_panel_isolated,
                    factory,
                    panel=panel,
                    codes=codes,
                    name=name,
                    ctx=ctx,
                )
                for panel, codes, name in targets
            }
            return {panel: future.result() for panel, future in futures.items()}

    active_client = client or _build_farpost_client()
    results: dict[str, tuple[dict, bool, dict[WorkType, int]]] = {}
    with contextlib.ExitStack() as stack:
        if managed and hasattr(type(active_client), "__enter__"):
            stack.enter_context(active_client)
        for panel, codes, name in targets:
            results[panel] = _estimate_replacement_panel(
                active_client=active_client,
                panel=panel,
                codes=codes,
                name=name,
                ctx=ctx,
            )
    return results


def _assemble_repair_schema(
    ordered_panels: list[tuple[str, set[str]]],
    panel_results: dict[str, tuple[dict, bool, dict[WorkType, int]]],
    matrix: dict,
) -> RepairSchema:
    parts, works = [], []
    has_color_matched_parts = False
    for panel, codes in ordered_panels:
        name = FIXED_PANELS.get(panel, PANELS.get(panel, (panel,))[0])
        is_replacement = _has_replacement_code(codes)
        if is_replacement and panel in FIXED_PANELS:
            operations = {WorkType.BODYWORK: matrix["bodywork"]}
        elif is_replacement and panel in PANELS:
            part_payload, matched, operations = panel_results[panel]
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


def estimate_repair(
    lot: Lot,
    *,
    client: FarpostClient | None = None,
    client_factory: Callable[[], FarpostClient] | None = None,
) -> RepairSchema:
    matrix = repair_matrix()
    ctx = _RepairContext(
        search_make=(lot.make or "").strip(),
        search_model=_search_model(lot.model or ""),
        body_code=_body_code(lot),
        paint_code=(lot.paint_code or "").strip().upper(),
        deadline=time.monotonic() + float(getattr(settings, "FARPOST_BUDGET_SEC", 30.0)),
        matrix=matrix,
    )
    ordered_panels = [
        (panel, codes)
        for panel, codes in sorted(_panel_codes(list(lot.defects.all())).items())
        if panel != BodyPanel.OTHER
    ]
    replacement_targets = [
        (panel, codes, PANELS[panel][0])
        for panel, codes in ordered_panels
        if _has_replacement_code(codes) and panel not in FIXED_PANELS and panel in PANELS
    ]
    panel_results = _resolve_replacement_panels(
        targets=replacement_targets,
        client=client,
        client_factory=client_factory,
        proxy_urls=getattr(settings, "SCRAPER_PROXY_URLS", ()),
        ctx=ctx,
    )
    return _assemble_repair_schema(ordered_panels, panel_results, matrix)


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
