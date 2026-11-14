import time
from dataclasses import dataclass, field

from ml_service.domains.enums import (
    BatchItemState,
    BatchStatus,
    BodyPanel,
    DefectCode,
    DriveType,
    FrameIdConfidence,
    FuelType,
    LayoutComplexity,
    OdometerStatus,
    ParseStatus,
    TaskStep,
)


@dataclass(slots=True, frozen=True)
class LoadedImageEntity:
    """Validated input image bytes with SHA-256 fingerprint."""

    data: bytes
    mime_type: str
    sha256: str
    original_filename: str


@dataclass(slots=True, frozen=True)
class SlicedSheetEntity:
    """Normalized full sheet and 4 overlapping 60x60% quadrants ready for Vision OCR."""

    full_png: bytes
    crops_png: dict[str, bytes]
    width: int
    height: int
    mime_type: str = "image/png"


@dataclass(slots=True, frozen=True)
class GatekeeperDecisionEntity:
    """Decision from fast gatekeeper router (gemini-decision-1)."""

    is_auction_sheet: bool
    is_readable: bool
    complexity: LayoutComplexity
    model_used: str = "gemini-decision-1"
    duration_ms: int = 0
    warning: str | None = None

    @property
    def is_accepted(self) -> bool:
        return self.is_auction_sheet and self.is_readable


@dataclass(slots=True, frozen=True)
class ChassisOcrEntity:
    """Chassis number read from a small chassis-number image."""

    frame_id: str | None = None
    raw: str | None = None
    confidence: str = "low"
    cached: bool = False
    duration_ms: int = 0


@dataclass(slots=True, frozen=True)
class FastHeaderPreviewEntity:
    """Fast low-resolution header preview returned ahead of full extraction."""

    make: str | None = None
    model: str | None = None
    lot_number: str | None = None
    duration_ms: int = 0

    @property
    def preview_title(self) -> str | None:
        base = " ".join(part.strip() for part in (self.make or "", self.model or "") if part and part.strip())
        lot = (self.lot_number or "").strip()
        if base and lot:
            return f"{base} #{lot}"
        if base:
            return base
        if lot:
            return f"#{lot}"
        return None


@dataclass(slots=True, frozen=True)
class ModelAttemptEntity:
    """Telemetry record for a single Gemini model invocation attempt."""

    model: str
    status: str
    ms: int


@dataclass(slots=True, frozen=True)
class RawDefectEntity:
    """Single defect mark extracted from the vehicle body diagram before code splitting."""

    visual_location: str
    panel_id: BodyPanel
    panel_ru: str
    raw_code: str


@dataclass(slots=True, frozen=True)
class RawRiskFlagsEntity:
    """Safety and structural stop-factors extracted directly by the Vision model."""

    is_flooded: bool = False
    airbag_deployed: bool = False
    hail_damage: bool = False
    underbody_rust: bool = False
    underbody_corrosion: bool = False
    core_support_repair: bool = False
    pillar_or_frame_repair: bool = False
    color_changed: bool = False
    windshield_damage: bool = False


@dataclass(slots=True, frozen=True)
class RawExtractionEntity:
    """Dual-Schema raw + translated output from Vision LLM before Python postprocessing."""

    # 1. Raw Japanese anchor fields
    auction_house_raw: str | None
    lot_number_raw: str
    make_raw: str
    model_raw: str
    trim_raw: str | None
    model_code_raw: str
    chassis_number_raw: str
    first_reg_raw: str
    mileage_raw: str
    engine_cc_raw: str
    transmission_raw: str
    drive_type_raw: str | None
    color_raw: str | None
    paint_code_raw: str | None
    shaken_raw: str | None
    recycling_fee_raw: str | None
    overall_grade: str
    exterior_grade: str | None
    interior_grade: str | None
    inspector_notes_raw: list[str] = field(default_factory=list)
    seller_comments_raw: list[str] = field(default_factory=list)

    # 2. Typed & translated fields from sheet
    auction_house: str | None = None
    make_en: str = ""
    model_en: str = ""
    trim_en: str | None = None
    mileage_km: int | None = None
    odometer_status: OdometerStatus = OdometerStatus.CONFIRMED
    engine_cc: int | None = None
    transmission_ru: str = ""
    drive_type: DriveType | None = None
    fuel_type: FuelType | None = None
    color_ru: str | None = None
    color_changed_ru: str | None = None
    shaken_ru: str | None = None
    recycling_fee_yen: int | None = None
    recycling_fee_paid: bool | None = None
    equipment_ru: list[str] = field(default_factory=list)
    defects: list[RawDefectEntity] = field(default_factory=list)
    risk_flags: RawRiskFlagsEntity = field(
        default_factory=lambda: RawRiskFlagsEntity(
            is_flooded=False,
            airbag_deployed=False,
            hail_damage=False,
            underbody_rust=False,
            underbody_corrosion=False,
            core_support_repair=False,
            pillar_or_frame_repair=False,
            color_changed=False,
            windshield_damage=False,
        )
    )
    inspector_notes_ru: list[str] = field(default_factory=list)
    seller_comments_ru: list[str] = field(default_factory=list)
    extra_ru: list[str] = field(default_factory=list)
    unreadable_fields: list[str] = field(default_factory=list)
    auction_branch: str | None = None
    right_hand_drive: bool | None = None
    name_change_deadline: str | None = None
    ocr_warnings: list[str] = field(default_factory=list)
    model_used: str | None = None
    extract_ms: int = 0
    attempts: list[ModelAttemptEntity] = field(default_factory=list)

    def to_raw_dict(self) -> dict[str, object]:
        """Returns dictionary of raw anchor fields for audit and debugging."""
        return {
            "auction_house_raw": self.auction_house_raw,
            "auction_branch": self.auction_branch,
            "lot_number_raw": self.lot_number_raw,
            "make_raw": self.make_raw,
            "model_raw": self.model_raw,
            "trim_raw": self.trim_raw,
            "model_code_raw": self.model_code_raw,
            "chassis_number_raw": self.chassis_number_raw,
            "first_reg_raw": self.first_reg_raw,
            "mileage_raw": self.mileage_raw,
            "engine_cc_raw": self.engine_cc_raw,
            "transmission_raw": self.transmission_raw,
            "drive_type_raw": self.drive_type_raw,
            "right_hand_drive": self.right_hand_drive,
            "name_change_deadline": self.name_change_deadline,
            "color_raw": self.color_raw,
            "paint_code_raw": self.paint_code_raw,
            "shaken_raw": self.shaken_raw,
            "recycling_fee_raw": self.recycling_fee_raw,
            "inspector_notes_raw": list(self.inspector_notes_raw),
            "seller_comments_raw": list(self.seller_comments_raw),
        }


@dataclass(slots=True, frozen=True)
class NormalizedDefectEntity:
    """Normalized body panel defect with validated defect codes, severity (1..3), and description."""

    panel_id: BodyPanel
    panel_ru: str
    defect_types: list[DefectCode]
    severity: int | None
    raw_code: str
    description_ru: str = ""


@dataclass(slots=True, frozen=True)
class RiskFlagsEntity:
    """Complete set of 13 safety and structural risk flags (Domain 1 + Pipeline)."""

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


@dataclass(slots=True, frozen=True)
class NormalizedSheetEntity:
    """Canonical normalized auction sheet passport (Domain 1 SSOT + Pipeline)."""

    lot_number: str
    auction_house: str | None
    auction_strictness_index: float | None
    make: str
    model: str
    trim: str | None
    model_code: str
    chassis_number: str
    frame_id: str
    frame_id_confidence: FrameIdConfidence
    first_reg_year: int | None
    first_reg_month: int | None
    first_reg_date_str: str | None
    is_pass_corridor_3_5: bool
    engine_cc: int | None
    mileage_km: int | None
    odometer_status: OdometerStatus
    transmission: str
    drive_type: DriveType | None
    fuel_type: FuelType | None
    color_ru: str | None
    paint_code: str | None
    overall_grade: str
    exterior_grade: str | None
    interior_grade: str | None
    shaken_until: str | None
    recycling_fee_yen: int | None
    recycling_fee_paid: bool | None
    equipment_ru: list[str]
    defects: list[NormalizedDefectEntity]
    risk_flags: RiskFlagsEntity
    inspector_notes_ru: list[str]
    seller_comments_ru: list[str]
    extra_ru: list[str]
    auction_branch: str | None = None
    right_hand_drive: bool | None = None
    name_change_deadline: str | None = None
    inspector_notes_raw: list[str] = field(default_factory=list)
    ocr_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ParserMetaEntity:
    """Execution telemetry metadata."""

    processing_ms: int
    mode_used: str
    cached: bool
    model_used: str
    sha256: str
    gatekeeper_model: str | None = None
    gatekeeper_ms: int = 0
    header_ms: int | None = None
    extract_ms: int = 0
    attempts: list[ModelAttemptEntity] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ParserResultEntity:
    """Top-level domain result of parsing a single auction sheet."""

    status: ParseStatus
    warnings: list[str]
    low_confidence_fields: list[str]
    sheet: NormalizedSheetEntity | None
    raw: dict[str, object] | None
    summary_md: str | None
    meta: ParserMetaEntity


@dataclass(slots=True)
class BatchItemStatusEntity:
    """Mutable state of a single sheet inside a batch processing queue."""

    lot_id: str | None
    file_index: int
    original_filename: str
    status: BatchItemState
    current_step: TaskStep
    progress_pct: int
    preview_title: str | None = None
    error_message: str | None = None
    result: ParserResultEntity | None = None


@dataclass(slots=True)
class BatchJobEntity:
    """Mutable state of an asynchronous multi-sheet batch (up to 10 sheets)."""

    batch_id: str
    created_at: str
    items: list[BatchItemStatusEntity] = field(default_factory=list)
    created_monotonic: float = field(default_factory=time.monotonic)

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def ready_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.READY)

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.FAILED)

    @property
    def rejected_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.REJECTED_NOT_SHEET)

    @property
    def processed_count(self) -> int:
        return self.ready_count + self.failed_count + self.rejected_count

    @property
    def status(self) -> BatchStatus:
        if not self.items:
            return BatchStatus.QUEUED
        if all(item.status == BatchItemState.QUEUED for item in self.items):
            return BatchStatus.QUEUED
        if self.processed_count < self.total_items:
            return BatchStatus.PROCESSING
        if self.ready_count == 0 and (self.failed_count + self.rejected_count) > 0:
            return BatchStatus.FAILED
        if (self.failed_count + self.rejected_count) > 0:
            return BatchStatus.PARTIAL_FAILED
        return BatchStatus.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return self.status in {BatchStatus.COMPLETED, BatchStatus.PARTIAL_FAILED, BatchStatus.FAILED}
