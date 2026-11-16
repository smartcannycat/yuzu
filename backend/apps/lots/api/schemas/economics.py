"""Customs, Farpost repair, market comparison, Wise Cost Ladder, and recalculate schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from apps.core.enums import (
    AgeCorridor,
    BodyPanel,
    DutyCalculationMode,
    PowerHpSource,
    WorkType,
)
from apps.core.schemas import StrictBaseModel
from apps.lots.api.schemas.audit import TrafficLightVerdict
from apps.lots.api.schemas.common import CurrencyRates


class DamagedPartItem(StrictBaseModel):
    panel_id: BodyPanel = Field(..., description="Body panel")
    defect_code: str = Field(..., description="Defect code (XX, X, A2, U2)")
    part_name_ru: str = Field(..., description="Replaceable part name")
    subtitle_ru: str | None = Field(None, description="Subtitle under the row")
    source_kind: str = Field("", description="Machine-readable price source / fallback reason")
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


class EconomicsDetail(StrictBaseModel):
    bid_slider_min_jpy: int = Field(100000, description="Min bid slider value (JPY)")
    bid_slider_max_jpy: int = Field(2500000, description="Max bid slider value (JPY)")
    bid_slider_step_jpy: int = Field(10000, description="Bid slider step (JPY)")
    is_repairs_included: bool = Field(
        True, description="Whether Farpost repair is included in turnkey cost"
    )
    is_simulation_modified: bool = Field(
        False, description="Whether persisted economics differ from initial baseline"
    )
    customs: CustomsCalculation = Field(..., description="Customs and logistics calculation")
    farpost_repair: FarpostRepairSummary = Field(..., description="Parts and STO works estimate")
    wise_cost_ladder: WiseCostLadder = Field(..., description="Transparent cost ladder (Screen 6)")


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
    bid_slider_min_jpy: int = Field(100000, description="Min bid slider value (JPY)")
    power_hp: int | None = Field(None, description="Effective engine power (hp)")
    power_hp_source: PowerHpSource | None = Field(None, description="Power figure origin")
    is_under_160_hp: bool | None = Field(None, description="Whether power is confirmed <= 160 hp")
    ocr_warnings: list[str] = Field(
        default_factory=list, description="Updated OCR/calculator warnings"
    )
    verdict: TrafficLightVerdict = Field(..., description="Updated traffic light verdict")
    is_simulation_modified: bool = Field(
        False, description="Whether persisted economics differ from initial baseline"
    )
    pdf_report_stale: bool = Field(True, description="Flag that PDF export needs simulation params")
