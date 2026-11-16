"""Repair matrix rules, panel mappings, body-code normalization, and offer selection."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from apps.core.enums import WorkType
from apps.lots.integrations.farpost.parser import PartOffer, matches_paint_code

if TYPE_CHECKING:
    from apps.lots.models import Lot

logger = logging.getLogger(__name__)

_MODEL_TRIM_RE = re.compile(
    r"\b(?:hv|hybrid|phev|phv|e:hev|e-power|epower|4wd|awd|2wd|"
    r"custom|crosstar|spada|g4|modulo|nismo|gr\s*sport)\b",
    re.I,
)
_BODY_CODE_RE = re.compile(r"[A-Z]{1,5}\d{1,4}[A-Z]{0,2}")
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

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
    cleaned = re.sub(r"\s+", " ", _MODEL_TRIM_RE.sub(" ", model or "")).strip(" -+/")
    return cleaned or (model or "").strip()


def _body_code(lot: Lot) -> str:
    # Prefer the raw frame/chassis series (e.g., GB5, GE6, NRE210) over full katashiki codes.
    candidates: list[str] = []
    for value in (lot.frame_id, lot.chassis_number):
        upper = (value or "").upper().strip()
        if not upper:
            continue
        if "-" not in upper and _VIN_RE.fullmatch(upper):
            # 17-char VINs do not start with a searchable Farpost chassis series.
            continue
        candidates.append(upper.split("-", 1)[0])
    if lot.model_code:
        upper = lot.model_code.upper().strip()
        if "-" in upper:
            candidates.append(upper.split("-", 1)[1])
        candidates.append(upper)
    for candidate in candidates:
        match = _BODY_CODE_RE.search(candidate)
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
            f"{code}{defect.severity}" if defect.severity and code in "AUWSCYGP" else code
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
