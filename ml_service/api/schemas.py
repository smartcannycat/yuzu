"""Pydantic v2 HTTP request and response schemas for ml_service."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ml_service.domains.enums import (
    BatchItemState,
    BatchStatus,
    BodyPanel,
    DefectCode,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    ParseStatus,
    TaskStep,
)


class StrictBaseModel(BaseModel):
    """Strict API model forbidding unexpected fields per contract rules."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class ParseUrlRequest(StrictBaseModel):
    """Request body for parsing an auction sheet image by remote URL."""

    url: HttpUrl
    force_refresh: bool = False


class HealthResponse(StrictBaseModel):
    """Service liveness and configuration summary."""

    status: Literal["ok"] = "ok"
    keys_configured: int
    reference_year: int


class ChassisOcrResponse(StrictBaseModel):
    """Chassis number read from a small chassis-number image."""

    frame_id: str | None = None
    raw: str | None = None
    confidence: Literal["high", "medium", "low"] = "low"
    cached: bool = False


class DefectResponse(StrictBaseModel):
    """Normalized body panel defect entry."""

    panel_id: BodyPanel
    panel_ru: str
    defect_types: list[DefectCode]
    severity: int | None = None
    description_ru: str
    raw_code: str


class RiskFlagsResponse(StrictBaseModel):
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


class NormalizedSheetResponse(StrictBaseModel):
    """Fully normalized auction sheet payload matching canonical Domain 1 schema."""

    lot_number: str
    auction_house: str | None = None
    auction_strictness_index: float | None = None
    auction_branch: str | None = None
    make: str
    model: str
    trim: str | None = None
    model_code: str
    chassis_number: str
    frame_id: str
    frame_id_confidence: FrameIdConfidence
    first_reg_year: int | None = None
    first_reg_month: int | None = None
    first_reg_date_str: str | None = None
    is_pass_corridor_3_5: bool | None = None
    engine_cc: int | None = None
    mileage_km: int | None = None
    odometer_status: OdometerStatus
    transmission: str
    drive_type: DriveType | None = None
    fuel_type: FuelType | None = None
    right_hand_drive: bool | None = None
    name_change_deadline: str | None = None
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
    inspector_notes_raw: list[str] = Field(default_factory=list)
    inspector_notes_ru: list[str] = Field(default_factory=list)
    seller_comments_ru: list[str] = Field(default_factory=list)
    extra_ru: list[str] = Field(default_factory=list)
    ocr_warnings: list[str] = Field(default_factory=list)


class ModelAttemptResponse(StrictBaseModel):
    """Telemetry record for a single Gemini model invocation attempt."""

    model: str
    status: str
    ms: int


class ParserMetaResponse(StrictBaseModel):
    """Operational metadata about a sheet parsing execution."""

    processing_ms: int
    mode_used: str
    cached: bool
    model_used: str
    sha256: str
    gatekeeper_model: str | None = None
    gatekeeper_ms: int = 0
    header_ms: int | None = None
    extract_ms: int = 0
    attempts: list[ModelAttemptResponse] = Field(default_factory=list)


class ParserResponse(StrictBaseModel):
    """Unified response for single-sheet parsing endpoints."""

    status: ParseStatus
    warnings: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    sheet: NormalizedSheetResponse | None = None
    raw: dict[str, object] | None = None
    summary_md: str | None = None
    meta: ParserMetaResponse


class BatchCreateResponse(StrictBaseModel):
    """Immediate 202 Accepted response upon creating or extending a batch job."""

    batch_id: UUID
    total_items: int
    status: BatchStatus
    created_at: str
    poll_interval_ms: int = 1500


class SheetSummaryProjection(StrictBaseModel):
    """Lightweight vehicle summary for batch polling UI cards."""

    lot_number: str
    make: str
    model: str
    year: int | None = None
    engine_cc: int | None = None
    model_code: str
    frame_id: str
    overall_grade: str
    auction_house: str | None = None
    mileage_km: int | None = None
    first_reg_date_str: str | None = None
    is_pass_corridor_3_5: bool | None = None


class BatchItemStatusResponse(StrictBaseModel):
    """Per-file progress and parsed result inside a batch job."""

    lot_id: UUID | None = None
    file_index: int
    original_filename: str
    status: BatchItemState
    current_step: TaskStep
    progress_pct: int = Field(ge=0, le=100)
    preview_title: str | None = None
    error_message: str | None = None
    summary: SheetSummaryProjection | None = None
    result: ParserResponse | None = None


class MascotResponse(StrictBaseModel):
    """UI mascot status descriptor for batch progress display."""

    mood: Literal["thinking", "happy", "confused", "warning"]
    phrase_ru: str
    badge_text: str


class BatchProgressResponse(StrictBaseModel):
    """Aggregated status and per-item progress for batch polling."""

    batch_id: UUID
    created_at: str
    status: BatchStatus
    total_count: int
    processed_count: int
    ready_count: int
    failed_count: int
    mascot: MascotResponse
    items: list[BatchItemStatusResponse]


class InvalidParamDetail(StrictBaseModel):
    """Single validation failure entry inside RFC 7807 Problem Details."""

    name: str
    reason: str


class ProblemDetailsResponse(StrictBaseModel):
    """RFC 7807 Problem Details error response schema."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    invalid_params: list[InvalidParamDetail] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
