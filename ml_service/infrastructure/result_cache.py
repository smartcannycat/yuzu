import asyncio
import json
import re
from dataclasses import asdict, replace
from enum import Enum
from pathlib import Path
from typing import Any

from app.domains.entities import (
    ModelAttemptEntity,
    NormalizedDefectEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RiskFlagsEntity,
)
from app.domains.enums import (
    BodyPanel,
    DefectCode,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    ParseStatus,
)

_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


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
        rf_raw = sheet_raw["risk_flags"]
        risk_flags = RiskFlagsEntity(
            is_flooded=bool(rf_raw["is_flooded"]),
            airbag_deployed=bool(rf_raw["airbag_deployed"]),
            hail_damage=bool(rf_raw["hail_damage"]),
            underbody_rust=bool(rf_raw["underbody_rust"]),
            underbody_corrosion=bool(rf_raw["underbody_corrosion"]),
            core_support_repair=bool(rf_raw["core_support_repair"]),
            pillar_or_frame_repair=bool(rf_raw["pillar_or_frame_repair"]),
            panel_replaced_xx=bool(rf_raw["panel_replaced_xx"]),
            panel_needs_replacement_x=bool(rf_raw["panel_needs_replacement_x"]),
            odometer_issue=bool(rf_raw["odometer_issue"]),
            color_changed=bool(rf_raw["color_changed"]),
            windshield_damage=bool(rf_raw["windshield_damage"]),
            repaired_grade_r_ra=bool(rf_raw["repaired_grade_r_ra"]),
        )
        drive_raw = sheet_raw.get("drive_type")
        fuel_raw = sheet_raw.get("fuel_type")

        sheet = NormalizedSheetEntity(
            lot_number=sheet_raw["lot_number"],
            auction_house=sheet_raw.get("auction_house"),
            auction_strictness_index=sheet_raw.get("auction_strictness_index"),
            make=sheet_raw["make"],
            model=sheet_raw["model"],
            trim=sheet_raw.get("trim"),
            model_code=sheet_raw["model_code"],
            chassis_number=sheet_raw["chassis_number"],
            frame_id=sheet_raw["frame_id"],
            frame_id_confidence=FrameIdConfidence(sheet_raw["frame_id_confidence"]),
            first_reg_year=sheet_raw.get("first_reg_year"),
            first_reg_month=sheet_raw.get("first_reg_month"),
            first_reg_date_str=sheet_raw.get("first_reg_date_str"),
            is_pass_corridor_3_5=bool(sheet_raw["is_pass_corridor_3_5"]),
            engine_cc=sheet_raw.get("engine_cc"),
            mileage_km=sheet_raw.get("mileage_km"),
            odometer_status=OdometerStatus(sheet_raw["odometer_status"]),
            transmission=sheet_raw["transmission"],
            drive_type=DriveType(drive_raw) if drive_raw is not None else None,
            fuel_type=FuelType(fuel_raw) if fuel_raw is not None else None,
            color_ru=sheet_raw.get("color_ru"),
            paint_code=sheet_raw.get("paint_code"),
            overall_grade=sheet_raw["overall_grade"],
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

    meta_raw = payload["meta"]
    meta = ParserMetaEntity(
        processing_ms=int(meta_raw["processing_ms"]),
        mode_used=meta_raw["mode_used"],
        cached=bool(meta_raw["cached"]),
        model_used=meta_raw["model_used"],
        sha256=meta_raw["sha256"],
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
    """Two-tier (in-memory + JSON disk) cache for parsed auction sheet results."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self._memory: dict[str, ParserResultEntity] = {}

    def _cache_path(self, sha256: str) -> Path | None:
        if not _SAFE_KEY_RE.fullmatch(sha256):
            return None
        return self.cache_dir / f"{sha256}.json"

    def _read_json_entity(self, path: Path) -> ParserResultEntity | None:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return deserialize_parser_result(payload)

    def _write_json_entity(self, path: Path, result: ParserResultEntity) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = serialize_parser_result(result)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def get(self, sha256: str, filename: str = "") -> ParserResultEntity | None:
        """Retrieve a cached result by SHA-256 from in-memory or disk cache."""
        cached = self._memory.get(sha256)
        if cached is not None:
            return replace(cached, meta=replace(cached.meta, cached=True))

        disk_path = self._cache_path(sha256)
        if disk_path is not None:
            disk_result = await asyncio.to_thread(self._read_json_entity, disk_path)
            if disk_result is not None:
                self._memory[sha256] = disk_result
                return replace(disk_result, meta=replace(disk_result.meta, cached=True))

        return None

    async def set(self, sha256: str, result: ParserResultEntity) -> None:
        """Store a ParserResultEntity in both in-memory and disk caches."""
        self._memory[sha256] = result
        disk_path = self._cache_path(sha256)
        if disk_path is not None:
            await asyncio.to_thread(self._write_json_entity, disk_path, result)
