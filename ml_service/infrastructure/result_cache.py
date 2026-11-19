"""Two-tier (in-memory LRU + atomic JSON disk) cache for parsed auction sheets."""

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from dataclasses import asdict, fields, replace
from enum import Enum
from pathlib import Path
from typing import Any

from ml_service.domains.entities import (
    ModelAttemptEntity,
    NormalizedDefectEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RiskFlagsEntity,
)
from ml_service.domains.enums import (
    BodyPanel,
    DefectCode,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    ParseStatus,
)
from ml_service.infrastructure.atomic_io import atomic_write_json, enforce_cache_limits

_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
logger = logging.getLogger(__name__)


def build_sheet_cache_key(
    sha256: str,
    *,
    reference_year: int,
    reference_month: int,
    default_auction_strictness: float,
    schema_version: str,
) -> str:
    """Build deterministic cache key scoped by image digest, normalization params, and schema."""
    fingerprint = (
        f"{reference_year}:{reference_month}:{default_auction_strictness:.6f}:{schema_version}"
    )
    suffix = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"{sha256}_{suffix}"


def _normalize_for_json(value: Any) -> Any:
    """Recursively convert Enum instances into plain JSON-serializable primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _normalize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    return value


def serialize_parser_result(result: ParserResultEntity) -> dict[str, Any]:
    """Serialize ParserResultEntity into a plain JSON-compatible dictionary."""
    return _normalize_for_json(asdict(result))


def deserialize_parser_result(payload: dict[str, Any]) -> ParserResultEntity:
    """Reconstruct ParserResultEntity with typed domain dataclasses and enums."""
    sheet_raw = payload.get("sheet")
    sheet: NormalizedSheetEntity | None = None
    if sheet_raw is not None:
        defects = [
            NormalizedDefectEntity(
                panel_id=BodyPanel(d["panel_id"]),
                panel_ru=d["panel_ru"],
                defect_types=[DefectCode(code) for code in d["defect_types"]],
                severity=d.get("severity"),
                raw_code=d["raw_code"],
                description_ru=d.get("description_ru", ""),
            )
            for d in sheet_raw.get("defects", [])
        ]
        rf_raw = sheet_raw.get("risk_flags") or {}
        risk_flags = RiskFlagsEntity(
            **{f.name: bool(rf_raw.get(f.name, False)) for f in fields(RiskFlagsEntity)}
        )
        drive_raw = sheet_raw.get("drive_type")
        fuel_raw = sheet_raw.get("fuel_type")

        sheet = NormalizedSheetEntity(
            lot_number=str(sheet_raw.get("lot_number", "UNKNOWN")),
            auction_house=sheet_raw.get("auction_house"),
            auction_strictness_index=sheet_raw.get("auction_strictness_index"),
            make=str(sheet_raw.get("make", "")),
            model=str(sheet_raw.get("model", "")),
            trim=sheet_raw.get("trim"),
            model_code=str(sheet_raw.get("model_code", "")),
            chassis_number=str(sheet_raw.get("chassis_number", "")),
            frame_id=str(sheet_raw.get("frame_id", "")),
            frame_id_confidence=FrameIdConfidence(
                sheet_raw.get("frame_id_confidence", FrameIdConfidence.RAW)
            ),
            first_reg_year=sheet_raw.get("first_reg_year"),
            first_reg_month=sheet_raw.get("first_reg_month"),
            first_reg_date_str=sheet_raw.get("first_reg_date_str"),
            is_pass_corridor_3_5=sheet_raw.get("is_pass_corridor_3_5"),
            engine_cc=sheet_raw.get("engine_cc"),
            mileage_km=sheet_raw.get("mileage_km"),
            odometer_status=OdometerStatus(
                sheet_raw.get("odometer_status", OdometerStatus.UNKNOWN)
            ),
            transmission=str(sheet_raw.get("transmission", "UNKNOWN")),
            drive_type=DriveType(drive_raw) if drive_raw is not None else None,
            fuel_type=FuelType(fuel_raw) if fuel_raw is not None else None,
            color_ru=sheet_raw.get("color_ru"),
            paint_code=sheet_raw.get("paint_code"),
            overall_grade=str(sheet_raw.get("overall_grade", "")),
            exterior_grade=sheet_raw.get("exterior_grade"),
            interior_grade=sheet_raw.get("interior_grade"),
            shaken_until=sheet_raw.get("shaken_until"),
            recycling_fee_yen=sheet_raw.get("recycling_fee_yen"),
            recycling_fee_paid=sheet_raw.get("recycling_fee_paid"),
            equipment_ru=list(sheet_raw.get("equipment_ru", [])),
            defects=defects,
            risk_flags=risk_flags,
            inspector_notes_ru=list(sheet_raw.get("inspector_notes_ru", [])),
            seller_comments_ru=list(sheet_raw.get("seller_comments_ru", [])),
            extra_ru=list(sheet_raw.get("extra_ru", [])),
            auction_branch=sheet_raw.get("auction_branch"),
            right_hand_drive=sheet_raw.get("right_hand_drive"),
            name_change_deadline=sheet_raw.get("name_change_deadline"),
            inspector_notes_raw=list(sheet_raw.get("inspector_notes_raw", [])),
            ocr_warnings=list(sheet_raw.get("ocr_warnings", [])),
        )

    meta_raw = payload.get("meta") or {}
    meta = ParserMetaEntity(
        processing_ms=int(meta_raw.get("processing_ms") or 0),
        mode_used=str(meta_raw.get("mode_used", "unknown")),
        cached=bool(meta_raw.get("cached", False)),
        model_used=str(meta_raw.get("model_used", "")),
        sha256=str(meta_raw.get("sha256", "")),
        gatekeeper_model=meta_raw.get("gatekeeper_model"),
        gatekeeper_ms=int(meta_raw.get("gatekeeper_ms") or 0),
        header_ms=int(meta_raw["header_ms"]) if meta_raw.get("header_ms") is not None else None,
        extract_ms=int(meta_raw.get("extract_ms") or 0),
        attempts=[
            ModelAttemptEntity(model=str(a["model"]), status=str(a["status"]), ms=int(a["ms"]))
            for a in meta_raw.get("attempts", [])
        ],
    )

    return ParserResultEntity(
        status=ParseStatus(payload["status"]),
        warnings=list(payload.get("warnings", [])),
        low_confidence_fields=list(payload.get("low_confidence_fields", [])),
        sheet=sheet,
        raw=payload.get("raw"),
        summary_md=payload.get("summary_md"),
        meta=meta,
    )


class ResultCache:
    """Two-tier (bounded LRU in-memory + atomic JSON disk) cache for parsed auction sheets."""

    def __init__(
        self,
        cache_dir: Path,
        max_memory_entries: int = 512,
        ttl_seconds: float | None = 604800.0,
        max_disk_bytes: int | None = 512 * 1024 * 1024,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self._max_memory_entries = max(1, max_memory_entries)
        self._ttl_seconds = ttl_seconds
        self._max_disk_bytes = max_disk_bytes
        self._memory: OrderedDict[str, tuple[float, ParserResultEntity]] = OrderedDict()

    def _is_expired(self, stored_at: float) -> bool:
        if self._ttl_seconds is None or self._ttl_seconds <= 0:
            return False
        return (time.time() - stored_at) > self._ttl_seconds

    def _remember(
        self, cache_key: str, result: ParserResultEntity, *, stored_at: float | None = None
    ) -> None:
        self._memory[cache_key] = (stored_at if stored_at is not None else time.time(), result)
        self._memory.move_to_end(cache_key)
        while len(self._memory) > self._max_memory_entries:
            self._memory.popitem(last=False)

    def _cache_path(self, cache_key: str) -> Path | None:
        if not _SAFE_KEY_RE.fullmatch(cache_key):
            return None
        return self.cache_dir / f"{cache_key}.json"

    def _read_json_entity(self, path: Path) -> tuple[float, ParserResultEntity] | None:
        if not path.is_file():
            return None
        try:
            st = path.stat()
            if self._is_expired(st.st_mtime):
                path.unlink(missing_ok=True)
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            return st.st_mtime, deserialize_parser_result(payload)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Ignoring corrupted sheet cache entry %s: %s", path.name, exc)
            return None

    def _write_json_entity(self, path: Path, result: ParserResultEntity) -> None:
        payload = serialize_parser_result(result)
        atomic_write_json(path, payload, prefix=".tmp_sheet_", indent=2)
        enforce_cache_limits(
            self.cache_dir,
            max_age_seconds=self._ttl_seconds,
            max_bytes=self._max_disk_bytes,
            pattern="*.json",
        )

    async def get(self, cache_key: str, filename: str = "") -> ParserResultEntity | None:  # noqa: ARG002
        """Retrieve a cached result by key from in-memory or disk cache."""
        entry = self._memory.get(cache_key)
        if entry is not None:
            stored_at, cached = entry
            if not self._is_expired(stored_at):
                self._memory.move_to_end(cache_key)
                return replace(cached, meta=replace(cached.meta, cached=True))
            self._memory.pop(cache_key, None)

        disk_path = self._cache_path(cache_key)
        if disk_path is not None:
            loaded = await asyncio.to_thread(self._read_json_entity, disk_path)
            if loaded is not None:
                stored_at, disk_result = loaded
                self._remember(cache_key, disk_result, stored_at=stored_at)
                return replace(disk_result, meta=replace(disk_result.meta, cached=True))

        return None

    async def set(self, cache_key: str, result: ParserResultEntity) -> None:
        """Store a result in memory and best-effort disk cache without crashing on OSError."""
        self._remember(cache_key, result)
        disk_path = self._cache_path(cache_key)
        if disk_path is not None:
            try:
                await asyncio.to_thread(self._write_json_entity, disk_path, result)
            except OSError as exc:
                logger.warning("Failed to write sheet cache entry %s: %s", disk_path.name, exc)
