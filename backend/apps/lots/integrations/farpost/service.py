"""Estimate parts and STO work, then atomically persist the existing repair contract."""

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, replace
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.core.enums import ExternalCacheSource, WorkType
from apps.core.models import ExternalCache
from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
    PartCriteria,
    PartOffer,
)
from apps.lots.models import DamagedPartItem, FarpostRepairSummary, Lot, ServiceWorkItem
from apps.lots.schemas import FarpostRepairSummary as RepairSchema
from config.settings.config import get_settings

logger = logging.getLogger(__name__)

# Each panel has a single query identity; fixed panels require restoration instead.
PANELS = {
    "front_bumper": ("Передний бампер", "бампер", "", "передний"),
    "rear_bumper": ("Задний бампер", "бампер", "", "задний"),
    "hood": ("Капот", "капот", "", ""),
    "tailgate": ("Крышка багажника", "багажник", "", ""),
    "front_left_fender": ("Переднее левое крыло", "крыло", "левое", "переднее"),
    "front_right_fender": ("Переднее правое крыло", "крыло", "правое", "переднее"),
    "front_left_door": ("Передняя левая дверь", "дверь", "левая", "передняя"),
    "front_right_door": ("Передняя правая дверь", "дверь", "правая", "передняя"),
    "rear_left_door": ("Задняя левая дверь", "дверь", "левая", "задняя"),
    "rear_right_door": ("Задняя правая дверь", "дверь", "правая", "задняя"),
    "windshield": ("Лобовое стекло", "стекло", "", "лобовое"),
}
FIXED_PANELS = {
    "roof": "Крыша",
    "rear_left_quarter": "Заднее левое крыло",
    "rear_right_quarter": "Заднее правое крыло",
    "left_sill": "Левый порог",
    "right_sill": "Правый порог",
}
LABELS = {
    WorkType.MOUNT_DISMOUNT: "Снятие и монтаж",
    WorkType.PAINT: "Покраска с материалами",
    WorkType.PDR_AND_POLISH: "PDR / полировка",
    WorkType.BODYWORK: "Кузовное восстановление",
}


@lru_cache
def repair_matrix() -> dict:
    return json.loads((Path(__file__).parent / "data/repair_matrix.json").read_text())


def _cache_key(criteria: PartCriteria) -> str:
    identity = json.dumps(asdict(criteria), sort_keys=True, ensure_ascii=True).encode()
    return "farpost:parts:v1:" + hashlib.sha256(identity).hexdigest()


def _read_offers(entry: ExternalCache | None) -> list[PartOffer] | None:
    if entry is None or not isinstance(entry.payload, dict):
        return None
    try:
        rows = entry.payload["offers"]
        if not isinstance(rows, list):
            return None
        offers = [PartOffer(**row) for row in rows]
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


def search_cached(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool]:
    """Keep successful offers separate from short-lived valid empty results."""
    key = _cache_key(criteria)
    entry = ExternalCache.objects.filter(key=key, source=ExternalCacheSource.FARPOST).first()
    offers = _read_offers(entry)
    if offers is not None and not entry.is_expired:
        return offers, False
    empty = ExternalCache.objects.filter(key=key + ":empty").first()
    if empty is not None and not empty.is_expired:
        return [], False
    try:
        offers = client.search(criteria, deadline=deadline)
    except FarpostFetchError as exc:
        logger.warning("Farpost search failed for %s: %s", criteria.panel_id, exc)
        previous = _read_offers(entry)
        if previous and timedelta(0) <= timezone.now() - entry.updated_at <= timedelta(days=1):
            return previous, True
        return [], True
    if offers:
        ExternalCache.objects.update_or_create(
            key=key,
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": [asdict(offer) for offer in offers]},
                "expires_at": timezone.now() + timedelta(hours=1),
            },
        )
        ExternalCache.objects.filter(key=key + ":empty").delete()
    else:
        ExternalCache.objects.update_or_create(
            key=key + ":empty",
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": []},
                "expires_at": timezone.now() + timedelta(minutes=10),
            },
        )
    return offers, False


def _body_code(lot: Lot) -> str:
    for value in (lot.model_code, lot.chassis_number, lot.frame_id):
        match = re.search(r"[A-Z]{2,5}\d{2,4}[A-Z]?", (value or "").upper())
        if match:
            return match[0]
    return ""


def _panel_codes(defects: list) -> dict[str, set[str]]:
    panels: dict[str, set[str]] = {}
    for defect in defects:
        tokens = re.findall(r"XX|[A-Z]\d*", (defect.raw_code or "").upper())
        if not tokens:
            tokens = list(defect.defect_types)
        tokens = [
            f"{code}{defect.severity}" if defect.severity and code in "AUWSCY" else code
            for code in tokens
        ]
        panels.setdefault(defect.panel_id, set()).update(tokens or ["UNKNOWN"])
    return panels


def _operations(codes: set[str], matrix: dict) -> dict[str, int]:
    work: dict[str, int] = {}
    for code in codes:
        key = code
        if key in matrix["maximum_severity"]:
            key += str(matrix["maximum_severity"][key])
        operations = matrix["operations"].get(key)
        if operations is None:
            logger.warning("Unknown repair defect code: %s", code)
            operations = {WorkType.BODYWORK: matrix["bodywork"]}
        for kind, amount in operations.items():
            work[kind] = max(work.get(kind, 0), amount)
    # Restoration prices include preparation and paint, so do not add paint again.
    if WorkType.BODYWORK in work:
        work[WorkType.BODYWORK] = max(work[WorkType.BODYWORK], work.pop(WorkType.PAINT, 0))
        work.pop(WorkType.PDR_AND_POLISH, None)
    return work


def estimate_repair(lot: Lot, *, client: FarpostClient | None = None) -> RepairSchema:
    settings = get_settings()
    client = client or FarpostClient(timeout_sec=settings.FARPOST_TIMEOUT_SEC)
    deadline = time.monotonic() + settings.FARPOST_BUDGET_SEC
    matrix = repair_matrix()
    parts, works = [], []
    has_color_matched_parts = False
    for panel, codes in sorted(_panel_codes(list(lot.defects.all())).items()):
        name = FIXED_PANELS.get(panel, PANELS.get(panel, (panel,))[0])
        is_replacement = bool(codes & {"X", "XX"})
        if is_replacement and panel in FIXED_PANELS:
            operations = {WorkType.BODYWORK: matrix["bodywork"]}
        elif is_replacement and panel in PANELS:
            _, part_name, side, position = PANELS[panel]
            criteria = PartCriteria(
                lot.make or "",
                lot.model or "",
                _body_code(lot),
                panel,
                part_name,
                side,
                position,
                (lot.paint_code or "").strip().upper(),
            )
            offers, stale = [], False
            if criteria.make and criteria.model and criteria.body_code:
                offers, stale = search_cached(client, criteria, deadline=deadline)
                if not offers and criteria.paint_code and not stale:
                    criteria = replace(criteria, paint_code="")
                    offers, stale = search_cached(client, criteria, deadline=deadline)
            offer = min(offers, key=lambda item: item.price_rub) if offers else None
            matched = bool(offer and offer.color_matched and not stale)
            has_color_matched_parts |= matched
            if offer and not stale:
                subtitle = (
                    f"Контрактная деталь в заводской цвет {lot.paint_code}"
                    if matched
                    else "Контрактная деталь; цвет не подтверждён, требуется окраска"
                )
            elif offer:
                subtitle = "Предварительная цена из кэша; наличие и цвет не подтверждены"
            else:
                subtitle = "Статистическая оценка; наличие и цвет не подтверждены"
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
                    "label_ru": f"{LABELS[kind]}: {name} (оценка по матрице)",
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
