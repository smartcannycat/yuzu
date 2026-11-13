"""Adapter that plugs the external ML sheet parsing service into the pipeline.

The adapter matches the parser contract expected by
``apps.lots.pipeline._run_ocr_stage``: ``gatekeeper(item)``,
``fast_header(item)`` and ``parse(item)``. The whole heavy work (OCR, model
inference) happens during the single ``POST /api/v1/sheets/parse`` call issued
by ``gatekeeper``; the response is cached on the instance so ``fast_header``
and ``parse`` are pure cache lookups.
"""

import hashlib
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import TextChoices

from apps.core.enums import (
    AuctionHouse,
    BodyPanel,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
)
from apps.lots.integrations.ml.client import MlServiceClient, MlServiceError
from apps.lots.integrations.ml.schemas import Defect, NormalizedSheet, ParserResponse
from apps.lots.models import BatchItem, Lot, LotDefect, LotRiskFlags

logger = logging.getLogger(__name__)

_NOT_SHEET_MESSAGE = "Изображение не является аукционным листом или нечитаемо"

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


class MlServiceParser:
    """Per-item parser backed by the external ML sheet parsing service.

    The pipeline creates one instance inside ``_run_ocr_stage`` for each
    batch item; the instance caches the single ``/sheets/parse`` response
    made by ``gatekeeper`` so that ``fast_header`` and ``parse`` reuse it
    without extra HTTP calls, and releases the HTTP client in ``parse``.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        client: MlServiceClient | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            # Injected clients are managed (and closed) by their owner.
            self._owns_client = False
        else:
            self._client = MlServiceClient(
                base_url=base_url if base_url is not None else settings.ML_SERVICE_URL,
                timeout_sec=timeout if timeout is not None else settings.ML_SERVICE_TIMEOUT_SEC,
                api_key=api_key if api_key is not None else settings.ML_SERVICE_API_KEY,
            )
            self._owns_client = True
        # item.pk -> {"bytes": ..., "sha256": ..., "response": ParserResponse}
        self._cache: dict[Any, dict[str, Any]] = {}

    def gatekeeper(self, item: BatchItem) -> str | None:
        """Read the sheet image, run the remote parse and gate on rejection.

        Returns a human-readable rejection reason, or None when the sheet was
        accepted (the parsed response stays cached for fast_header/parse).
        """
        image_bytes, sha256 = _load_image(item)
        response = self._client.parse_sheet(image_bytes, item.original_filename)
        _log_response(item, response)
        if response.status == "rejected_not_sheet":
            return _NOT_SHEET_MESSAGE
        self._cache[item.pk] = {"bytes": image_bytes, "sha256": sha256, "response": response}
        return None

    def fast_header(self, item: BatchItem) -> str | None:
        """Build a preview title from the cached parse response."""
        response = self._cached_response(item)
        if response is None or response.sheet is None:
            return None
        sheet = response.sheet
        parts = [part for part in (sheet.make, sheet.model) if part]
        if not parts:
            return None
        title = " ".join(parts)
        if sheet.lot_number:
            title = f"{title} #{sheet.lot_number}"
        return title[:200]

    def parse(self, item: BatchItem) -> None:
        """Apply the cached parse response to the lot and its related rows."""
        response = self._cached_response(item)
        if response is None:
            response = self._parse_fresh(item)
        if response.status == "rejected_not_sheet" or response.sheet is None:
            raise MlServiceError(
                f"ML service returned no sheet for item {item.pk} (status={response.status})"
            )
        try:
            self._apply_sheet(item, response)
        finally:
            self._cache.pop(item.pk, None)
            # The parser instance is per-item (created inside _run_ocr_stage):
            # release the self-created connection pool as soon as the item is
            # done. Injected clients stay owned by their callers.
            if self._owns_client:
                self._client.close()

    # Internal helpers -----------------------------------------------------

    def _parse_fresh(self, item: BatchItem) -> ParserResponse:
        image_bytes, _sha256 = _load_image(item)
        response = self._client.parse_sheet(image_bytes, item.original_filename)
        _log_response(item, response)
        return response

    def _cached_response(self, item: BatchItem) -> ParserResponse | None:
        cached = self._cache.get(item.pk)
        return cached["response"] if cached else None

    def _apply_sheet(self, item: BatchItem, response: ParserResponse) -> None:
        lot = item.lot
        if lot is None:
            raise MlServiceError(f"Batch item {item.pk} has no lot to fill")
        sheet = response.sheet
        assert sheet is not None  # guaranteed by the caller
        mapping_warnings: list[str] = [
            _unknown_panel_warning(defect) for defect in _unknown_panel_defects(sheet.defects)
        ]
        fields = _sheet_to_lot_fields(sheet, response, mapping_warnings)

        with transaction.atomic():
            for name, value in fields.items():
                setattr(lot, name, value)
            lot.save(update_fields=[*fields.keys(), "updated_at"])
            LotRiskFlags.objects.update_or_create(lot=lot, defaults=sheet.risk_flags.model_dump())
            _replace_defects(lot, sheet.defects)

        for warning in mapping_warnings:
            logger.warning("ML mapping issue for item %s: %s", item.pk, warning)


def _load_image(item: BatchItem) -> tuple[bytes, str]:
    if not item.original_file:
        raise MlServiceError(f"Batch item {item.pk} has no original file")
    with item.original_file.open("rb") as file_obj:
        image_bytes = file_obj.read()
    return image_bytes, hashlib.sha256(image_bytes).hexdigest()


def _log_response(item: BatchItem, response: ParserResponse) -> None:
    meta = response.meta
    logger.debug(
        "ML parse for item %s: status=%s mode=%s cached=%s processing_ms=%s model=%s",
        item.pk,
        response.status,
        meta.mode_used,
        meta.cached,
        meta.processing_ms,
        meta.model_used,
    )
    if response.warnings:
        logger.debug("ML parse warnings for item %s: %s", item.pk, response.warnings)
    if response.low_confidence_fields:
        logger.debug(
            "ML low confidence fields for item %s: %s",
            item.pk,
            response.low_confidence_fields,
        )


def _sheet_to_lot_fields(
    sheet: NormalizedSheet,
    response: ParserResponse,
    mapping_warnings: list[str],
) -> dict[str, Any]:
    """Map a normalized sheet onto Lot column values (choices-safe)."""
    # Mapping warnings produced earlier (unknown panel zones) surface in the
    # lot's ocr_warnings alongside service warnings, capped to the column limit.
    ocr_warnings = [
        *[str(w)[:300] for w in sheet.ocr_warnings],
        *[str(w)[:300] for w in response.warnings],
        *[str(w)[:300] for w in mapping_warnings],
    ]

    def map_choice(choices: type[TextChoices], value: str | None, field_name: str) -> str | None:
        return _map_choice(choices, value, field_name, ocr_warnings, mapping_warnings)

    return {
        "lot_number": _clip(sheet.lot_number, "lot_number"),
        "auction_house": map_choice(AuctionHouse, sheet.auction_house, "auction_house"),
        "auction_branch": _clip(sheet.auction_branch, "auction_branch"),
        "auction_strictness_index": sheet.auction_strictness_index,
        "make": _clip(sheet.make, "make"),
        "model": _clip(sheet.model, "model"),
        "trim": _clip(sheet.trim, "trim"),
        "model_code": _clip(sheet.model_code, "model_code"),
        "chassis_number": _clip(sheet.chassis_number, "chassis_number"),
        "frame_id": _clip(sheet.frame_id, "frame_id"),
        "frame_id_confidence": map_choice(
            FrameIdConfidence, sheet.frame_id_confidence, "frame_id_confidence"
        ),
        "first_reg_year": sheet.first_reg_year,
        "first_reg_month": sheet.first_reg_month,
        "first_reg_date_str": _clip(sheet.first_reg_date_str, "first_reg_date_str"),
        "is_pass_corridor_3_5": sheet.is_pass_corridor_3_5,
        "engine_cc": sheet.engine_cc,
        "mileage_km": sheet.mileage_km,
        "odometer_status": map_choice(OdometerStatus, sheet.odometer_status, "odometer_status"),
        "transmission": _clip(sheet.transmission, "transmission"),
        "drive_type": map_choice(DriveType, sheet.drive_type, "drive_type"),
        "fuel_type": map_choice(FuelType, sheet.fuel_type, "fuel_type"),
        "color_ru": _clip(sheet.color_ru, "color_ru"),
        "paint_code": _clip(sheet.paint_code, "paint_code"),
        "overall_grade": _clip(sheet.overall_grade, "overall_grade"),
        "exterior_grade": _clip(sheet.exterior_grade, "exterior_grade"),
        "interior_grade": _clip(sheet.interior_grade, "interior_grade"),
        "shaken_until": _clip(sheet.shaken_until, "shaken_until"),
        "recycling_fee_yen": sheet.recycling_fee_yen,
        "recycling_fee_paid": sheet.recycling_fee_paid,
        "equipment_ru": [entry[:200] for entry in sheet.equipment_ru],
        "inspector_notes_raw": list(sheet.inspector_notes_raw),
        "inspector_notes_ru": list(sheet.inspector_notes_ru),
        "seller_comments_ru": list(sheet.seller_comments_ru),
        "extra_ru": list(sheet.extra_ru),
        "ocr_warnings": ocr_warnings,
        "low_confidence_fields": [entry[:100] for entry in response.low_confidence_fields],
        # first_reg_year drives the model year. auction_bid_jpy is intentionally
        # left untouched: the sheet has no bid price, and the start bid is
        # resolved later by economics.resolve_start_bid_jpy.
        "year": sheet.first_reg_year,
    }


def _clip(value: str | None, field_name: str) -> str | None:
    if not value:
        return None
    limit = _FIELD_LIMITS.get(field_name)
    if limit is not None and len(value) > limit:
        return value[:limit]
    return value


def _map_choice(
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


def _replace_defects(lot: Lot, defects: list[Defect]) -> None:
    lot.defects.all().delete()
    valid_panels = set(BodyPanel.values)
    rows: list[LotDefect] = []
    for defect in defects:
        if defect.panel_id not in valid_panels:
            # BodyPanel has no OTHER member (16 canonical zones only), so an
            # unknown panel cannot be stored without violating the choices
            # contract; skip the defect and surface a warning instead.
            continue
        rows.append(
            LotDefect(
                lot=lot,
                panel_id=defect.panel_id,
                panel_ru=defect.panel_ru[:100],
                defect_types=[code[:10] for code in defect.defect_types],
                severity=defect.severity,
                raw_code=defect.raw_code[:20],
                description_ru=defect.description_ru[:300],
            )
        )
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
