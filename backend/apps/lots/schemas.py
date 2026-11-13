from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from apps.core.enums import (
    AgeCorridor,
    AnomalySeverity,
    AuctionHouse,
    BatchStatus,
    BodyPanel,
    ChecklistItemStatus,
    CrossAuditStatus,
    DriveType,
    DutyCalculationMode,
    FuelType,
    ItemProcessingStatus,
    MascotMood,
    OdometerStatus,
    RiskLevel,
    SystemKey,
    TaskStep,
    TrafficLightColor,
    WorkType,
)
from apps.core.schemas import StrictBaseModel


class CurrencyRates(StrictBaseModel):
    jpy_rub_bank: float = Field(..., description="Commercial JPY/RUB rate (Far East bank)")
    jpy_rate_source: str = Field("ДВ-банк (ориентир)", description="Source of JPY/RUB rate")
    eur_rub_cbrf: float = Field(..., description="Official EUR/RUB rate from CBRF")
    usd_rub_cbrf: float = Field(..., description="Official USD/RUB rate from CBRF")
    cbrf_date: str = Field(..., description="CBRF rate fixation date (DD.MM.YYYY)")


class NormalizedDefect(StrictBaseModel):
    panel_id: BodyPanel = Field(..., description="Canonical body panel identifier (1 of 16)")
    panel_ru: str = Field(..., description="Russian name of the panel")
    defect_types: list[str] = Field(..., description="Damage types (A, U, W, S, XX, etc.)")
    severity: int | None = Field(None, ge=1, le=3, description="Severity (1..3) or null for XX/X")
    raw_code: str = Field(..., description="Original code from auction sheet (A2, U2, W1, XX)")
    description_ru: str = Field(..., description="Short legend text for body diagram (Screen 5)")


class RiskFlags(StrictBaseModel):
    is_flooded: bool = Field(False, description="Flooded vehicle")
    airbag_deployed: bool = Field(False, description="Deployed airbags")
    hail_damage: bool = Field(False, description="Hail damage")
    underbody_rust: bool = Field(False, description="Surface underbody rust")
    underbody_corrosion: bool = Field(False, description="Through corrosion of sills/longerons")
    core_support_repair: bool = Field(False, description="Core support repair")
    pillar_or_frame_repair: bool = Field(False, description="Load-bearing pillar/frame repair")
    panel_replaced_xx: bool = Field(False, description="Panel already replaced in Japan (XX)")
    panel_needs_replacement_x: bool = Field(False, description="Panel needs replacement (X)")
    odometer_issue: bool = Field(False, description="Odometer issues: tampered, replaced, unknown")
    color_changed: bool = Field(False, description="Color change mark")
    windshield_damage: bool = Field(False, description="Windshield chip/crack/replacement")
    repaired_grade_r_ra: bool = Field(False, description="Official salvage grade R/RA/0")


class NormalizedSheet(StrictBaseModel):
    lot_number: str = Field(..., description="Auction lot number")
    auction_house: AuctionHouse = Field(..., description="Canonical auction house")
    auction_branch: str | None = Field(None, description="Auction branch if specified")
    auction_strictness_index: float = Field(
        ..., ge=0.0, le=1.0, description="Strictness index (0.55..1.00)"
    )
    make: str = Field(..., description="Vehicle make in Latin")
    model: str = Field(..., description="Vehicle model in Latin")
    trim: str | None = Field(None, description="Trim level (optional)")
    model_code: str = Field(..., description="Factory body model code")
    chassis_number: str = Field(..., description="Chassis serial number")
    frame_id: str = Field(..., description="Canonical Frame ID")
    frame_id_confidence: Literal["exact", "synthesized", "raw"] = Field("exact")
    first_reg_year: int | None = Field(None, description="First registration year")
    first_reg_month: int | None = Field(None, ge=1, le=12, description="First registration month")
    first_reg_date_str: str | None = Field(None, description="Formatted date and age string")
    is_pass_corridor_3_5: bool | None = Field(
        None, description="Pass-age 3-5 years (null if date not recognized)"
    )
    engine_cc: int | None = Field(None, description="Engine displacement in cc")
    power_hp: int | None = Field(None, description="Engine power in hp")
    power_hp_source: Literal["drom_catalog", "katashiki_cache", "manual"] | None = Field(None)
    is_under_160_hp: bool | None = Field(
        None, description="Power <= 160 hp (preferential util fee)"
    )
    mileage_km: int | None = Field(None, ge=0, description="Mileage in km")
    odometer_status: OdometerStatus = Field(..., description="Odometer status")
    transmission: str = Field(..., description="Transmission type in Russian")
    drive_type: DriveType | None = Field(None, description="Drive type (2WD / 4WD)")
    fuel_type: FuelType | None = Field(None, description="Fuel type")
    color_ru: str | None = Field(None, description="Body color in Russian")
    paint_code: str | None = Field(None, description="Factory paint code")
    overall_grade: str = Field(..., description="Overall auction grade")
    exterior_grade: str | None = Field(None, description="Exterior grade")
    interior_grade: str | None = Field(None, description="Interior grade")
    shaken_until: str | None = Field(None, description="Shaken expiry in Japan")
    recycling_fee_yen: int | None = Field(None, ge=0, description="Japanese recycling fee (JPY)")
    recycling_fee_paid: bool | None = Field(None, description="Japanese recycling fee paid mark")
    equipment_ru: list[str] = Field(default_factory=list, description="Options list")
    defects: list[NormalizedDefect] = Field(
        default_factory=list, description="Body defects (up to 16 panels)"
    )
    risk_flags: RiskFlags = Field(..., description="Safety risk flags (13 flags)")
    inspector_notes_ru: list[str] = Field(
        default_factory=list, description="Translated inspector notes"
    )
    inspector_notes_raw: list[str] = Field(
        default_factory=list, description="Raw Japanese inspector notes"
    )
    seller_comments_ru: list[str] = Field(
        default_factory=list, description="Translated seller comments"
    )
    extra_ru: list[str] = Field(default_factory=list, description="Additional sheet marks")
    ocr_warnings: list[str] = Field(default_factory=list, description="Parser warnings")
    low_confidence_fields: list[str] = Field(
        default_factory=list, description="Low-confidence OCR fields"
    )


class AnomalyAlert(StrictBaseModel):
    type: str = Field(..., description="Anomaly type")
    severity: AnomalySeverity = Field(..., description="Severity level")
    title_ru: str = Field(..., description="Anomaly title")
    message_ru: str = Field(..., description="Anomaly explanation")
    diff_details: dict[str, Any] | None = Field(None, description="Before/after diff object")


class PastAuctionRecord(StrictBaseModel):
    auction_date: str = Field(..., description="Past auction date (DD.MM.YYYY)")
    auction_house: str = Field(..., description="Past auction house")
    auction_strictness: float | None = Field(None, description="Auction strictness index")
    lot_number: str = Field(..., description="Archive lot number")
    overall_grade: str = Field(..., description="Past auction grade")
    mileage_km: int | None = Field(None, description="Past auction mileage in km")
    defects_summary: str | None = Field(None, description="Past auction defects summary")
    closing_price_jpy: int | None = Field(None, description="Closing price in JPY")
    sheet_archive_url: str | None = Field(None, description="Archive sheet scan URL")

    @field_validator("auction_date", mode="before")
    @classmethod
    def format_auction_date(cls, value: Any) -> Any:
        return value.strftime("%d.%m.%Y") if isinstance(value, date) else value


class CrossAuditReport(StrictBaseModel):
    status: CrossAuditStatus = Field(..., description="Cross-audit status by Frame ID")
    source_name: str = Field("AucJP + AAA Japan / Pravto", description="Aggregators used")
    is_archive_available: bool = Field(True, description="Whether archive history was obtained")
    risk_level: RiskLevel = Field(..., description="Safety risk level")
    has_critical_anomaly: bool = Field(
        ..., description="Critical anomaly flag (Sticky Alert trigger)"
    )
    headline_ru: str = Field(..., description="Short audit conclusion")
    times_auctioned: int = Field(
        ..., ge=0, description="How many times the car was found at auctions"
    )
    verified_at: datetime = Field(..., description="Verification timestamp (UTC)")
    anomalies: list[AnomalyAlert] = Field(default_factory=list, description="Detected anomalies")
    history: list[PastAuctionRecord] = Field(default_factory=list, description="Trading history")


class DamagedPartItem(StrictBaseModel):
    panel_id: BodyPanel = Field(..., description="Body panel")
    defect_code: str = Field(..., description="Defect code (XX, X, A2, U2)")
    part_name_ru: str = Field(..., description="Replaceable part name")
    subtitle_ru: str | None = Field(None, description="Subtitle under the row")
    price_from_rub: int = Field(..., ge=0, description="Lower bound part price in Vladivostok")
    in_stock_vladivostok: bool = Field(..., description="In stock in Vladivostok")
    is_statistical_fallback: bool = Field(
        False, description="From statistical matrix instead of live Farpost"
    )


class ServiceWorkItem(StrictBaseModel):
    work_type: WorkType = Field(..., description="Work category")
    label_ru: str = Field(..., description="Work name for UI")
    amount_rub: int = Field(..., ge=0, description="Work cost in RUB")
    zero_cost_reason_ru: str | None = Field(None, description="Zero cost reason")


class FarpostRepairSummary(StrictBaseModel):
    parts: list[DamagedPartItem] = Field(default_factory=list, description="Parts for replacement")
    service_works: list[ServiceWorkItem] = Field(default_factory=list, description="STO works")
    total_parts_from_rub: int = Field(..., ge=0, description="Total parts 'from' sum")
    total_works_rub: int = Field(..., ge=0, description="Total STO works sum")
    grand_total_repair_rub: int = Field(..., ge=0, description="Total estimated repair")
    has_color_matched_parts: bool = Field(..., description="Color-matched parts present")
    included_in_turnkey_hint_ru: str = Field("Сумма уже включена в расчёт под ключ")


class WiseCostStep(StrictBaseModel):
    step_number: int = Field(..., ge=1, le=10, description="Step ordinal")
    name_ru: str = Field(..., description="Expense item name")
    amount_rub: int = Field(..., ge=0, description="Amount in RUB")
    original_currency: str | None = Field(None, description="Original currency (JPY, EUR, RUB)")
    original_amount: float | None = Field(None, description="Amount in original currency")
    is_optional: bool = Field(False, description="Toggleable step (repair estimate)")


class WiseCostLadder(StrictBaseModel):
    car_bid_jpy: int = Field(..., ge=0, description="Auction bid in JPY")
    car_bid_rub: int = Field(..., ge=0, description="Bid equivalent in RUB")
    turnkey_cost_rub: int = Field(..., ge=0, description="Total turnkey cost in Vladivostok")
    market_price_rf_rub: int = Field(..., ge=0, description="Median RF market price (Drom)")
    net_benefit_rub: int = Field(..., description="Net benefit for the client")
    benefit_percentage: float = Field(..., description="Benefit percentage")
    steps: list[WiseCostStep] = Field(..., description="Cost ladder steps (Screen 6)")


class MarketComparisonInfo(StrictBaseModel):
    market_price_rf_rub: int = Field(..., ge=0, description="Median analog price in RF (RUB)")
    analogs_count: int = Field(..., ge=0, description="Comparable listings in stock in RF")
    price_min_rub: int | None = Field(None, ge=0, description="Min analog price in RF")
    price_max_rub: int | None = Field(None, ge=0, description="Max analog price in RF")
    search_region_ru: str = Field("ДФО / Владивосток", description="Search region")
    excludes_under_order: bool = Field(True, description="Under-order listings filtered out")
    filtered_out_under_order_count: int = Field(
        0, ge=0, description="Filtered out under-order/anomaly count"
    )
    is_fallback: bool = Field(False, description="True if expanded due to <3 exact analogs")
    fallback_reason_ru: str | None = Field(None, description="Expansion reason")
    drom_search_url: str = Field(..., description="Ready Drom.ru search URL with filters")


class CustomsCalculation(StrictBaseModel):
    age_corridor: AgeCorridor = Field(..., description="EAEU age corridor")
    duty_calculation_mode: DutyCalculationMode = Field(DutyCalculationMode.EUR_PER_CC)
    engine_cc: int = Field(..., description="Engine displacement in cc")
    duty_rate_eur_per_cc: float | None = Field(
        None, description="Duty rate EUR per cc (for 3-5 and 5+ years)"
    )
    effective_duty_pct: float | None = Field(
        None, description="Duty percentage of vehicle value (under 3 years)"
    )
    customs_duty_eur: float = Field(..., description="Duty in EUR")
    customs_duty_rub: int = Field(..., description="Duty in RUB")
    excise_rub: int = Field(0, ge=0, description="Import excise (EVs outside unified EAEU rates)")
    import_vat_rub: int = Field(0, ge=0, description="Import VAT (EVs outside unified EAEU rates)")
    is_under_160_hp: bool | None = Field(None, description="Power <= 160 hp")
    is_commercial_util: bool = Field(..., description="Commercial utilization fee")
    utilization_fee_rub: int = Field(..., description="RF utilization fee")
    customs_clearance_fee_rub: int = Field(..., description="Customs clearance fee")
    freight_vladivostok_rub: int = Field(..., description="Sea freight to Vladivostok and SVH")
    broker_svh_sbkts_rub: int = Field(..., description="Broker, SBKTS, lab, EPTS")
    meti_sanction_risk: bool = Field(
        False, description="METI sanction risk (hybrid, EV, ICE >1900cc)"
    )
    rates_snapshot: CurrencyRates = Field(
        ..., description="Currency rates snapshot (CBRF + Far East bank)"
    )


class TrafficLightVerdict(StrictBaseModel):
    verdict: TrafficLightColor = Field(..., description="Traffic light color")
    headline: str = Field(..., description="Verdict headline (Screen 4)")
    short_verdict_label: str = Field(..., description="Short verdict label for card (Screen 1)")
    badge_text: str = Field(..., description="Green/yellow/red badge text (Screen 4)")
    net_benefit_rub: int = Field(..., description="Net benefit in RUB")
    benefit_percentage: float = Field(..., description="Benefit percentage")
    body_summary_ru: str = Field(..., description="Short 'Body' bullet (Screen 4)")
    interior_summary_ru: str = Field(..., description="Short 'Interior' bullet (Screen 4)")
    reasoning_bullets: list[str] = Field(default_factory=list, description="Additional PDF bullets")


class SafetyCheckItem(StrictBaseModel):
    system_key: SystemKey = Field(..., description="System key")
    label_ru: str = Field(..., description="System name for Bottom Sheet")
    status: ChecklistItemStatus = Field(..., description="Status from sheet data")
    detail_ru: str = Field(..., description="Explanation strictly from sheet marks")


class SafetyChecklist(StrictBaseModel):
    overall_status: ChecklistItemStatus = Field(..., description="Overall status for Screen 5 row")
    overall_label_ru: str = Field(..., description="Short status label ('В норме', etc.)")
    items: list[SafetyCheckItem] = Field(..., description="Checklist items for Bottom Sheet")


class LotSummary(StrictBaseModel):
    lot_id: UUID = Field(..., description="Unique lot identifier")
    make: str = Field(..., description="Vehicle make")
    model: str = Field(..., description="Vehicle model")
    year: int | None = Field(None, description="Production year (null on partial OCR)")
    engine_cc: int | None = Field(None, description="Engine displacement in cc")
    frame_id: str = Field(..., description="Canonical body number")
    auction_house: AuctionHouse = Field(..., description="Canonical auction house")
    lot_number: str = Field(..., description="Lot number")
    overall_grade: str = Field(..., description="Auction grade")
    mileage_km: int | None = Field(None, ge=0, description="Mileage in km")
    turnkey_cost_rub: int = Field(..., description="Turnkey price in Vladivostok")
    market_price_rf_rub: int = Field(..., description="RF market price (Drom)")
    verdict: TrafficLightColor = Field(..., description="Traffic light verdict")
    verdict_headline: str = Field(..., description="Verdict text in card")
    net_benefit_rub: int = Field(..., description="Net benefit vs RF market")
    meti_sanction_risk: bool = Field(False, description="METI sanction risk")
    has_anomaly: bool = Field(..., description="Cross-audit anomaly flag")
    anomaly_text: str | None = Field(None, description="Anomaly warning text")
    thumbnail_url: str | None = Field(None, description="Auction sheet scan thumbnail URL")
    created_at: datetime = Field(..., description="Record creation timestamp (UTC)")


class MascotState(StrictBaseModel):
    mood: MascotMood = Field(..., description="Mascot mood")
    phrase_ru: str = Field(..., description="Contextual mascot phrase")
    badge_text: str = Field(..., description="Progress text ('Распознаем лоты... 3/4')")


class BatchItemStatus(StrictBaseModel):
    lot_id: UUID | None = Field(
        None, description="Lot ID (created on intake; null on failed / rejected_not_sheet)"
    )
    file_index: int = Field(..., ge=0, description="File ordinal in batch")
    original_filename: str = Field(..., description="Original uploaded filename")
    preview_title: str | None = Field(None, description="Fast Header OCR preview title")
    status: ItemProcessingStatus = Field(..., description="File processing status")
    current_step: TaskStep = Field(..., description="Current DAG step")
    error_message: str | None = Field(None, description="Failure error text")
    summary: LotSummary | None = Field(None, description="Compact lot card (filled when ready)")


class BatchProgressResponse(StrictBaseModel):
    batch_id: UUID = Field(..., description="Polled batch identifier")
    status: BatchStatus = Field(..., description="Overall batch status")
    mascot: MascotState = Field(..., description="Current mascot state")
    total_count: int = Field(..., ge=1, description="Total files in batch")
    processed_count: int = Field(..., ge=0, description="Fully processed files")
    ready_count: int = Field(..., ge=0, description="Successfully ready lots")
    failed_count: int = Field(..., ge=0, description="Failed files")
    items: list[BatchItemStatus] = Field(..., description="Detailed per-file status")


class BatchCreateResponse(StrictBaseModel):
    batch_id: UUID = Field(..., description="Created batch identifier")
    total_items: int = Field(..., ge=1, le=10, description="Accepted file count")
    status: BatchStatus = Field(..., description="Batch status")
    created_at: datetime = Field(..., description="Enqueue timestamp (UTC)")
    poll_interval_ms: int = Field(1500, description="Recommended polling interval in ms")


class LotMediaLinks(StrictBaseModel):
    sheet_thumbnail_url: str = Field(..., description="Auction sheet scan thumbnail URL")
    sheet_scan_url: str = Field(..., description="Full auction sheet scan URL for lightbox")
    drom_search_url: str = Field(..., description="Drom.ru analogs search URL")


class EconomicsDetail(StrictBaseModel):
    bid_slider_min_jpy: int = Field(300000, description="Min bid slider value (JPY)")
    bid_slider_max_jpy: int = Field(2500000, description="Max bid slider value (JPY)")
    bid_slider_step_jpy: int = Field(10000, description="Bid slider step (JPY)")
    is_repairs_included: bool = Field(
        True, description="Whether Farpost repair is included in turnkey cost"
    )
    customs: CustomsCalculation = Field(..., description="Customs and logistics calculation")
    farpost_repair: FarpostRepairSummary = Field(..., description="Parts and STO works estimate")
    wise_cost_ladder: WiseCostLadder = Field(..., description="Transparent cost ladder (Screen 6)")


class LotDetailResponse(StrictBaseModel):
    lot_id: UUID = Field(..., description="Unique lot identifier")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Update timestamp (UTC)")
    passport: NormalizedSheet = Field(
        ..., description="Vehicle passport, defects, risks, inspector notes"
    )
    verdict: TrafficLightVerdict = Field(
        ..., description="Traffic light, body/interior bullets, net benefit"
    )
    market: MarketComparisonInfo = Field(..., description="RF market comparison (Drom.ru)")
    audit: CrossAuditReport = Field(..., description="Cross-audit history result (AucJP)")
    safety_checklist: SafetyChecklist = Field(
        ..., description="Safety systems summary and checklist"
    )
    economics: EconomicsDetail = Field(
        ..., description="Slider params, customs, repair, cost ladder"
    )
    media: LotMediaLinks = Field(..., description="Original sheet scan and Drom.ru link")


class InProgressItemPreview(StrictBaseModel):
    batch_id: UUID = Field(..., description="Batch identifier")
    lot_id: UUID | None = Field(None, description="Lot ID if already created")
    display_title: str = Field(..., description="Make/model from Fast Header OCR or filename")
    status: ItemProcessingStatus = Field(..., description="Item status")
    current_step: TaskStep = Field(..., description="Current pipeline step")


class InProgressSummary(StrictBaseModel):
    active_batches_count: int = Field(..., ge=0, description="Active batches count")
    total_processing_lots: int = Field(..., ge=0, description="Cars in processing (no percentages)")
    items: list[InProgressItemPreview] = Field(
        default_factory=list, description="In-progress items for accordion"
    )


class PaginationMeta(StrictBaseModel):
    total_items: int = Field(..., ge=0, description="Total records")
    page: int = Field(..., ge=1, description="Current page")
    page_size: int = Field(..., ge=1, le=100, description="Page size")
    total_pages: int = Field(..., ge=0, description="Total pages")


class FilterCountItem(StrictBaseModel):
    value: str = Field(..., description="Filter value for query param")
    count: int = Field(..., ge=0, description="Ready lots count")


class AvailableFilters(StrictBaseModel):
    total_lots_count: int = Field(..., ge=0, description="Counter for 'All (N)' chip")
    makes: list[FilterCountItem] = Field(default_factory=list, description="Makes with counts")
    models: list[FilterCountItem] = Field(default_factory=list, description="Models with counts")
    counts_by_verdict: dict[TrafficLightColor, int] = Field(
        default_factory=dict, description="Counts by traffic light color"
    )


class LotListResponse(StrictBaseModel):
    items: list[LotSummary] = Field(..., description="Ready lots list (LIFO)")
    in_progress: InProgressSummary = Field(
        ..., description="Active tasks block for header dropdown"
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    available_filters: AvailableFilters = Field(..., description="Filters with counts")


class RecalculateRequest(StrictBaseModel):
    bid_jpy: int | None = Field(None, ge=100000, le=50000000, description="New auction bid in JPY")
    bid_rub: int | None = Field(
        None, ge=50000, le=50000000, description="Alternative direct bid in RUB"
    )
    is_commercial_util: bool = Field(
        False, description="Util fee toggle: False=Personal, True=Commercial"
    )
    include_repairs: bool = Field(True, description="Include Farpost repair in turnkey cost")
    custom_power_hp: int | None = Field(
        None, ge=1, le=2000, description="Manual power override in hp"
    )
    custom_freight_rub: int | None = Field(None, ge=0, description="Custom freight cost")

    @model_validator(mode="after")
    def validate_exclusive_bid_currency(self) -> "RecalculateRequest":
        if self.bid_jpy is not None and self.bid_rub is not None:
            raise PydanticCustomError(
                "exclusive_bid_currency",
                "Укажите либо 'bid_jpy', либо 'bid_rub', но не оба поля одновременно",
            )
        return self


class RecalculateResponse(StrictBaseModel):
    lot_id: UUID = Field(..., description="Lot identifier")
    recalculated_at: datetime = Field(..., description="Recalculation timestamp (UTC)")
    applied_bid_jpy: int = Field(..., description="Applied bid in JPY")
    applied_bid_rub: int = Field(..., description="Applied bid in RUB")
    is_commercial_util: bool = Field(..., description="Applied util fee mode")
    include_repairs: bool = Field(..., description="Whether repair estimate is included")
    customs: CustomsCalculation = Field(..., description="Updated customs calculation")
    wise_cost_ladder: WiseCostLadder = Field(..., description="Updated cost ladder")
    turnkey_cost_rub: int = Field(..., description="Updated turnkey cost")
    market_price_rf_rub: int = Field(..., description="RF market price")
    net_benefit_rub: int = Field(..., description="Updated net benefit")
    benefit_percentage: float = Field(..., description="Updated benefit percentage")
    verdict: TrafficLightVerdict = Field(..., description="Updated traffic light verdict")
    pdf_report_stale: bool = Field(True, description="Flag that PDF export needs simulation params")
