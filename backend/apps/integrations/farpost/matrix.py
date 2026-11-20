"""Repair matrix rules, panel mappings, body-code normalization, and offer selection."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from apps.core.enums import WorkType
from apps.integrations.farpost.parser import PartOffer, matches_paint_code
from apps.integrations.shared.aliases import FARPOST_MODEL_TRIM_RE
from apps.integrations.shared.katashiki import extract_farpost_body_code

if TYPE_CHECKING:
    from apps.lots.models import Lot

logger = logging.getLogger(__name__)

_SEVERITY_DEFECT_CODES = frozenset({"A", "U", "W", "S", "C", "Y", "G", "P"})

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


def _search_model(model: str) -> str:
    cleaned = re.sub(r"\s+", " ", FARPOST_MODEL_TRIM_RE.sub(" ", model or "")).strip(" -+/")
    return cleaned or (model or "").strip()


def _body_code(lot: Lot) -> str:
    return extract_farpost_body_code(
        frame_id=lot.frame_id,
        chassis_number=lot.chassis_number,
        model_code=lot.model_code,
    )


def _panel_codes(defects: list) -> dict[str, set[str]]:
    panels: dict[str, set[str]] = {}
    for defect in defects:
        tokens = re.findall(r"XX|[A-Z]\d*", (defect.raw_code or "").upper())
        if not tokens:
            tokens = [
                str(code).strip().upper() for code in defect.defect_types if str(code).strip()
            ]
        tokens = [
            f"{code}{defect.severity}"
            if defect.severity and code in _SEVERITY_DEFECT_CODES
            else code
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


def _select_best_offer(
    offers: list[PartOffer],
    *,
    paint_code: str,
    paint_cost_rub: int,
    panel: str,
    stale: bool,
) -> tuple[PartOffer | None, bool]:
    if not offers:
        return None, False
    best_plain = min(offers, key=lambda item: (item.price_rub, item.offer_id))
    if stale or not paint_code or panel == "windshield":
        return best_plain, False
    colored = [
        item
        for item in offers
        if item.color_matched or matches_paint_code(f"{item.title} {item.snippet}", paint_code)
    ]
    if not colored:
        return best_plain, False
    best_colored = min(colored, key=lambda item: (item.price_rub, item.offer_id))
    if best_colored.price_rub <= best_plain.price_rub + paint_cost_rub:
        return best_colored, True
    return best_plain, False


def _work_label(kind: WorkType, name: str, panel: str) -> str:
    if kind == WorkType.PDR_AND_POLISH and panel == "windshield":
        return f"Ремонт скола / полимер: {name} (расчёт по матрице)"
    if kind == WorkType.BODYWORK or panel in FIXED_PANELS:
        return f"{LABELS[kind]}: {name} (расчёт по матрице)"
    return f"{LABELS[kind]}: {name} (норматив СТО)"
