"""Pydantic v2 HTTP schemas and explicit domain-to-API converters."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.domains.entities import (
    BatchItemStatusEntity,
    BatchJobEntity,
    NormalizedDefectEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RiskFlagsEntity,
)
from app.domains.enums import (
    BatchItemState,
    BatchStatus,
    BodyPanel,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    ParseStatus,
)


class ParseUrlRequest(BaseModel):
    """Request body for parsing an auction sheet image by remote URL."""

    url: HttpUrl
    force_refresh: bool = False


class HealthResponse(BaseModel):
    """Service liveness and configuration summary."""

    status: Literal["ok"] = "ok"
    keys_configured: int
    cache_dir: str
    reference_year: int


class DefectResponse(BaseModel):
    """Normalized body panel defect entry."""

    panel_id: BodyPanel
    panel_ru: str
    defect_types: list[str]
    severity: int | None = None
    raw_code: str


class RiskFlagsResponse(BaseModel):
    """Risk and stop-factor flags derived from sheet inspection notes and defects."""

    is_flooded: bool
    airbag_deployed: bool
    hail_damage: bool
    underbody_rust: bool
    underbody_corrosion: bool
    core_support_repair: bool
    pillar_or_frame_repair: bool
    panel_replaced_xx: bool
    panel_needs_replacement_x: bool
    odometer_issue: bool
    color_changed: bool
    windshield_damage: bool
    repaired_grade_r_ra: bool


class NormalizedSheetResponse(BaseModel):
    """Fully normalized auction sheet payload matching canonical Domain 1 schema."""

    lot_number: str
    auction_house: str | None = None
    auction_strictness_index: float | None = None
    make: str
    model: str
    trim: str | None = None
    model_code: str
    chassis_number: str
    frame_id: str
    frame_id_confidence: FrameIdConfidence
    first_reg_year: int | None = None
    first_reg_month: int | None = None
    first_reg_date: str | None = None
    first_reg_date_str: str | None = None
    is_pass_corridor_3_5: bool | None = None
    engine_cc: int | None = None
    mileage_km: int | None = None
    odometer_status: OdometerStatus
    transmission: str
    drive_type: DriveType | None = None
    fuel_type: FuelType | None = None
    color_ru: str | None = None
    paint_code: str | None = None
    overall_grade: str
    exterior_grade: str | None = None
    interior_grade: str | None = None
    shaken_until: str | None = None
    recycling_fee_yen: int | None = None
    recycling_fee_paid: bool | None = None
    equipment_ru: list[str] = Field(default_factory=list)
    defects: list[DefectResponse] = Field(default_factory=list)
    risk_flags: RiskFlagsResponse
    inspector_notes_ru: list[str] = Field(default_factory=list)
    seller_comments_ru: list[str] = Field(default_factory=list)
    extra_ru: list[str] = Field(default_factory=list)


class ParserMetaResponse(BaseModel):
    """Operational metadata about a sheet parsing execution."""

    processing_ms: int
    mode_used: str
    cached: bool
    model_used: str
    sha256: str


class ParserResponse(BaseModel):
    """Unified response for single-sheet parsing endpoints."""

    status: ParseStatus
    warnings: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    sheet: NormalizedSheetResponse | None = None
    raw: dict[str, object] | None = None
    summary_md: str | None = None
    meta: ParserMetaResponse


class BatchCreateResponse(BaseModel):
    """Immediate 202 Accepted response upon creating or extending a batch job."""

    batch_id: str
    total_count: int
    status: BatchStatus
    created_at: str


class SheetSummaryProjection(BaseModel):
    """Lightweight vehicle summary for batch polling UI cards."""

    make: str
    model: str
    model_code: str
    frame_id: str
    overall_grade: str
    auction_house: str | None = None
    mileage_km: int | None = None
    first_reg_date_str: str | None = None
    is_pass_corridor_3_5: bool | None = None


class BatchItemStatusResponse(BaseModel):
    """Per-file progress and parsed result inside a batch job."""

    lot_id: str
    file_index: int
    original_filename: str
    status: BatchItemState
    current_step: str
    progress_pct: int
    error_message: str | None = None
    summary: SheetSummaryProjection | None = None
    result: ParserResponse | None = None


class BatchProgressResponse(BaseModel):
    """Aggregated status and per-item progress for batch polling."""

    batch_id: str
    created_at: str
    status: BatchStatus
    total_count: int
    processed_count: int
    ready_count: int
    failed_count: int
    items: list[BatchItemStatusResponse]


def _to_defect_response(defect: NormalizedDefectEntity) -> DefectResponse:
    return DefectResponse(
        panel_id=defect.panel_id,
        panel_ru=defect.panel_ru,
        defect_types=list(defect.defect_types),
        severity=defect.severity,
        raw_code=defect.raw_code,
    )


def _to_risk_flags_response(flags: RiskFlagsEntity) -> RiskFlagsResponse:
    return RiskFlagsResponse(
        is_flooded=flags.is_flooded,
        airbag_deployed=flags.airbag_deployed,
        hail_damage=flags.hail_damage,
        underbody_rust=flags.underbody_rust,
        underbody_corrosion=flags.underbody_corrosion,
        core_support_repair=flags.core_support_repair,
        pillar_or_frame_repair=flags.pillar_or_frame_repair,
        panel_replaced_xx=flags.panel_replaced_xx,
        panel_needs_replacement_x=flags.panel_needs_replacement_x,
        odometer_issue=flags.odometer_issue,
        color_changed=flags.color_changed,
        windshield_damage=flags.windshield_damage,
        repaired_grade_r_ra=flags.repaired_grade_r_ra,
    )


def _to_sheet_response(sheet: NormalizedSheetEntity) -> NormalizedSheetResponse:
    return NormalizedSheetResponse(
        lot_number=sheet.lot_number,
        auction_house=sheet.auction_house,
        auction_strictness_index=sheet.auction_strictness_index,
        make=sheet.make,
        model=sheet.model,
        trim=sheet.trim,
        model_code=sheet.model_code,
        chassis_number=sheet.chassis_number,
        frame_id=sheet.frame_id,
        frame_id_confidence=sheet.frame_id_confidence,
        first_reg_year=sheet.first_reg_year,
        first_reg_month=sheet.first_reg_month,
        first_reg_date=sheet.first_reg_date,
        first_reg_date_str=sheet.first_reg_date_str,
        is_pass_corridor_3_5=sheet.is_pass_corridor_3_5,
        engine_cc=sheet.engine_cc,
        mileage_km=sheet.mileage_km,
        odometer_status=sheet.odometer_status,
        transmission=sheet.transmission,
        drive_type=sheet.drive_type,
        fuel_type=sheet.fuel_type,
        color_ru=sheet.color_ru,
        paint_code=sheet.paint_code,
        overall_grade=sheet.overall_grade,
        exterior_grade=sheet.exterior_grade,
        interior_grade=sheet.interior_grade,
        shaken_until=sheet.shaken_until,
        recycling_fee_yen=sheet.recycling_fee_yen,
        recycling_fee_paid=sheet.recycling_fee_paid,
        equipment_ru=list(sheet.equipment_ru),
        defects=[_to_defect_response(item) for item in sheet.defects],
        risk_flags=_to_risk_flags_response(sheet.risk_flags),
        inspector_notes_ru=list(sheet.inspector_notes_ru),
        seller_comments_ru=list(sheet.seller_comments_ru),
        extra_ru=list(sheet.extra_ru),
    )


def _to_meta_response(meta: ParserMetaEntity) -> ParserMetaResponse:
    return ParserMetaResponse(
        processing_ms=meta.processing_ms,
        mode_used=meta.mode_used,
        cached=meta.cached,
        model_used=meta.model_used,
        sha256=meta.sha256,
    )


def to_parser_response(entity: ParserResultEntity) -> ParserResponse:
    """Convert domain ParserResultEntity to external API ParserResponse."""
    return ParserResponse(
        status=entity.status,
        warnings=list(entity.warnings),
        low_confidence_fields=list(entity.low_confidence_fields),
        sheet=_to_sheet_response(entity.sheet) if entity.sheet is not None else None,
        raw=dict(entity.raw) if entity.raw is not None else None,
        summary_md=entity.summary_md,
        meta=_to_meta_response(entity.meta),
    )


def _to_summary_projection(sheet: NormalizedSheetEntity | None) -> SheetSummaryProjection | None:
    if sheet is None:
        return None
    return SheetSummaryProjection(
        make=sheet.make,
        model=sheet.model,
        model_code=sheet.model_code,
        frame_id=sheet.frame_id,
        overall_grade=sheet.overall_grade,
        auction_house=sheet.auction_house,
        mileage_km=sheet.mileage_km,
        first_reg_date_str=sheet.first_reg_date_str,
        is_pass_corridor_3_5=sheet.is_pass_corridor_3_5,
    )


def _to_batch_item_response(item: BatchItemStatusEntity) -> BatchItemStatusResponse:
    summary = _to_summary_projection(item.result.sheet) if item.result is not None else None
    result_resp = to_parser_response(item.result) if item.result is not None else None
    return BatchItemStatusResponse(
        lot_id=item.lot_id,
        file_index=item.file_index,
        original_filename=item.original_filename,
        status=item.status,
        current_step=item.current_step,
        progress_pct=item.progress_pct,
        error_message=item.error_message,
        summary=summary,
        result=result_resp,
    )


def to_batch_create_response(batch: BatchJobEntity) -> BatchCreateResponse:
    """Convert domain BatchJobEntity to compact 202 creation response."""
    return BatchCreateResponse(
        batch_id=batch.batch_id,
        total_count=batch.total_count,
        status=batch.status,
        created_at=batch.created_at,
    )


def to_batch_progress_response(batch: BatchJobEntity) -> BatchProgressResponse:
    """Convert domain BatchJobEntity to detailed polling response."""
    return BatchProgressResponse(
        batch_id=batch.batch_id,
        created_at=batch.created_at,
        status=batch.status,
        total_count=batch.total_count,
        processed_count=batch.processed_count,
        ready_count=batch.ready_count,
        failed_count=batch.failed_count,
        items=[_to_batch_item_response(item) for item in batch.items],
    )
