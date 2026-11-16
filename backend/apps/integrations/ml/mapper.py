"""Mapping helpers converting ML NormalizedSheet payloads into Lot fields and defects."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from apps.core.enums import (
    AuctionHouse,
    BodyPanel,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
)
from apps.lots.models import Lot, LotDefect

if TYPE_CHECKING:
    from django.db.models import TextChoices

    from apps.integrations.ml.schemas import Defect, NormalizedSheet, ParserResponse

_DEFAULT_AUCTION_STRICTNESS = 0.65
_MISSING_AUCTION_HOUSE_WARNING = (
    "Аукционный дом не указан в листе — установлена площадка «Прочее» (OTHER)"
)

_FIELD_LIMITS: dict[str, int] = {
    "lot_number": 50,
    "auction_branch": 100,
    "make": 100,
    "model": 200,
    "trim": 100,
    "model_code": 50,
    "chassis_number": 50,
    "frame_id": 50,
    "first_reg_date_str": 100,
    "transmission": 50,
    "color_ru": 100,
    "paint_code": 20,
    "overall_grade": 10,
    "exterior_grade": 5,
    "interior_grade": 5,
    "shaken_until": 50,
}


def clip_field(value: str | None, field_name: str) -> str | None:
    if not value:
        return None
    limit = _FIELD_LIMITS.get(field_name)
    if limit is not None and len(value) > limit:
        return value[:limit]
    return value


def map_choice(
    choices: type[TextChoices],
    value: str | None,
    field_name: str,
    ocr_warnings: list[str],
    mapping_warnings: list[str],
) -> str | None:
    """Return the value when it matches strict choices, otherwise None + warning."""
    if value is None or value == "":
        return None
    if value in choices.values:
        return value
    message = f"Unknown {field_name} value from ML service: {value!r}"
    mapping_warnings.append(message)
    ocr_warnings.append(message[:300])
    return None


def _sheet_to_lot_fields(
    sheet: NormalizedSheet,
    response: ParserResponse,
    mapping_warnings: list[str],
) -> dict[str, Any]:
    """Map a normalized sheet onto Lot column values (choices-safe)."""
    ocr_warnings = [
        *[str(w)[:300] for w in sheet.ocr_warnings],
        *[str(w)[:300] for w in response.warnings],
        *[str(w)[:300] for w in mapping_warnings],
    ]

    def resolve_choice(
        choices: type[TextChoices], value: str | None, field_name: str
    ) -> str | None:
        return map_choice(choices, value, field_name, ocr_warnings, mapping_warnings)

    auction_house = resolve_choice(AuctionHouse, sheet.auction_house, "auction_house")
    if auction_house is None:
        auction_house = AuctionHouse.OTHER.value
        if not sheet.auction_house:
            ocr_warnings.append(_MISSING_AUCTION_HOUSE_WARNING)
    raw_strictness = sheet.auction_strictness_index
    auction_strictness_index = (
        float(raw_strictness)
        if raw_strictness is not None and math.isfinite(raw_strictness)
        else _DEFAULT_AUCTION_STRICTNESS
    )
    first_reg_month = sheet.first_reg_month
    if first_reg_month is not None and not 1 <= first_reg_month <= 12:
        ocr_warnings.append(
            f"Некорректный месяц первой регистрации '{first_reg_month}' от OCR — сброшен"
        )
        first_reg_month = None

    return {
        "lot_number": clip_field(sheet.lot_number, "lot_number"),
        "auction_house": auction_house,
        "auction_branch": clip_field(sheet.auction_branch, "auction_branch"),
        "auction_strictness_index": auction_strictness_index,
        "make": clip_field(sheet.make, "make"),
        "model": clip_field(sheet.model, "model"),
        "trim": clip_field(sheet.trim, "trim"),
        "model_code": clip_field(sheet.model_code, "model_code"),
        "chassis_number": clip_field(sheet.chassis_number, "chassis_number"),
        "frame_id": clip_field(sheet.frame_id, "frame_id"),
        "frame_id_confidence": resolve_choice(
            FrameIdConfidence, sheet.frame_id_confidence, "frame_id_confidence"
        ),
        "first_reg_year": sheet.first_reg_year,
        "first_reg_month": first_reg_month,
        "first_reg_date_str": clip_field(sheet.first_reg_date_str, "first_reg_date_str"),
        "is_pass_corridor_3_5": sheet.is_pass_corridor_3_5,
        "engine_cc": sheet.engine_cc,
        "mileage_km": sheet.mileage_km,
        "odometer_status": resolve_choice(OdometerStatus, sheet.odometer_status, "odometer_status"),
        "transmission": clip_field(sheet.transmission, "transmission"),
        "drive_type": resolve_choice(DriveType, sheet.drive_type, "drive_type"),
        "fuel_type": resolve_choice(FuelType, sheet.fuel_type, "fuel_type"),
        "color_ru": clip_field(sheet.color_ru, "color_ru"),
        "paint_code": clip_field(sheet.paint_code, "paint_code"),
        "overall_grade": clip_field(sheet.overall_grade, "overall_grade"),
        "exterior_grade": clip_field(sheet.exterior_grade, "exterior_grade"),
        "interior_grade": clip_field(sheet.interior_grade, "interior_grade"),
        "shaken_until": clip_field(sheet.shaken_until, "shaken_until"),
        "recycling_fee_yen": sheet.recycling_fee_yen,
        "recycling_fee_paid": sheet.recycling_fee_paid,
        "equipment_ru": [entry[:200] for entry in sheet.equipment_ru],
        "inspector_notes_raw": list(sheet.inspector_notes_raw),
        "inspector_notes_ru": list(sheet.inspector_notes_ru),
        "seller_comments_ru": list(sheet.seller_comments_ru),
        "extra_ru": list(sheet.extra_ru),
        "ocr_warnings": ocr_warnings,
        "low_confidence_fields": [entry[:100] for entry in response.low_confidence_fields],
        "year": sheet.first_reg_year,
    }


def _replace_defects(lot: Lot, defects: list[Defect]) -> None:
    """Replace stored defects with the canonical-zone subset."""
    lot.defects.all().delete()
    valid_panels = set(BodyPanel.values)
    rows = [
        LotDefect(
            lot=lot,
            panel_id=defect.panel_id,
            panel_ru=defect.panel_ru[:100],
            defect_types=[code[:10] for code in defect.defect_types],
            severity=defect.severity,
            raw_code=defect.raw_code[:20],
            description_ru=defect.description_ru[:300],
        )
        for defect in defects
        if defect.panel_id in valid_panels
    ]
    if rows:
        LotDefect.objects.bulk_create(rows)


def _unknown_panel_defects(defects: list[Defect]) -> list[Defect]:
    valid_panels = set(BodyPanel.values)
    return [defect for defect in defects if defect.panel_id not in valid_panels]


def _unknown_panel_warning(defect: Defect) -> str:
    return (
        f"Unknown panel_id from ML service: {defect.panel_id!r} "
        f"(raw_code={defect.raw_code!r}); defect skipped"
    )


def _unmatched_defect_notes(defects: list[Defect]) -> list[str]:
    """Russian notes for defects whose panel_id is outside the 16 zones."""
    valid_panels = set(BodyPanel.values)
    notes: list[str] = []
    for defect in defects:
        if defect.panel_id in valid_panels:
            continue
        parts = [defect.panel_ru, defect.raw_code, defect.description_ru]
        note = " — ".join(part for part in parts if part)
        if note:
            notes.append(note)
    return notes
