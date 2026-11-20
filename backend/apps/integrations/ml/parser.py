"""Adapter that plugs the external ML sheet parsing service into the pipeline."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import transaction

from apps.integrations.ml.client import MlServiceClient, MlServiceError
from apps.integrations.ml.mapper import (
    _DEFAULT_AUCTION_STRICTNESS,
    _MISSING_AUCTION_HOUSE_WARNING,
    _collect_defect_warnings,
    _replace_defects,
    _sheet_to_lot_fields,
    _unknown_panel_defects,
    _unknown_panel_warning,
    _unmatched_defect_notes,
)
from apps.lots.models import BatchItem, LotRiskFlags

if TYPE_CHECKING:
    from apps.integrations.ml.schemas import ParserResponse

logger = logging.getLogger(__name__)

_NOT_SHEET_MESSAGE = "Изображение не является аукционным листом или нечитаемо"

__all__ = [
    "_DEFAULT_AUCTION_STRICTNESS",
    "_MISSING_AUCTION_HOUSE_WARNING",
    "MlServiceParser",
    "_sheet_to_lot_fields",
    "_unknown_panel_defects",
    "_unknown_panel_warning",
]


class MlServiceParser:
    """Per-item parser backed by the external ML sheet parsing service."""

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
            self._owns_client = False
        else:
            self._client = MlServiceClient(
                base_url=base_url if base_url is not None else settings.ML_SERVICE_URL,
                timeout_sec=timeout if timeout is not None else settings.ML_SERVICE_TIMEOUT_SEC,
                api_key=api_key if api_key is not None else settings.ML_SERVICE_API_KEY,
            )
            self._owns_client = True
        self._cache: dict[Any, dict[str, Any]] = {}

    def close(self) -> None:
        """Clear cached sheet payloads and close the owned ML HTTP client."""
        self._cache.clear()
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> MlServiceParser:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def gatekeeper(self, item: BatchItem) -> str | None:
        """Read the sheet image, run the remote parse and gate on rejection."""
        image_bytes, sha256 = _load_image(item)
        response = self._client.parse_sheet(image_bytes, item.original_filename)
        _log_response(item, response)
        if response.status == "rejected_not_sheet":
            self._cache.pop(item.pk, None)
            return _NOT_SHEET_MESSAGE
        self._cache[item.pk] = {"bytes": image_bytes, "sha256": sha256, "response": response}
        return None

    def parse(self, item: BatchItem) -> None:
        """Apply the cached parse response to the lot and its related rows."""
        try:
            response = self._cached_response(item)
            if response is None:
                response = self._parse_fresh(item)
            if response.status == "rejected_not_sheet" or response.sheet is None:
                raise MlServiceError(
                    f"ML service returned no sheet for item {item.pk} (status={response.status})"
                )
            self._apply_sheet(item, response)
        finally:
            self._cache.pop(item.pk, None)
            if self._owns_client:
                self._client.close()

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
        assert sheet is not None
        mapping_warnings = _collect_defect_warnings(sheet.defects)
        fields = _sheet_to_lot_fields(sheet, response, mapping_warnings)
        unmatched_defect_notes = [
            note.strip() for note in _unmatched_defect_notes(sheet.defects) if note.strip()
        ]

        with transaction.atomic():
            for name, value in fields.items():
                setattr(lot, name, value)
            if unmatched_defect_notes:
                fields["extra_ru"] = [
                    *fields.get("extra_ru", []),
                    *unmatched_defect_notes,
                ]
                lot.extra_ru = fields["extra_ru"]
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
