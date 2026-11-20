"""Common currency, defect, risk-flag, and normalized auction-sheet schemas."""

from typing import Literal

from pydantic import Field

from apps.core.enums import (
    AuctionHouse,
    BodyPanel,
    DriveType,
    FuelType,
    OdometerStatus,
)
from apps.core.schemas import StrictBaseModel


class CurrencyRates(StrictBaseModel):
    jpy_rub_bank: float = Field(..., description="Commercial JPY/RUB rate (Far East bank)")
    jpy_rate_source: str = Field("ДВ-банк (ориентир)", description="Source of JPY/RUB rate")
    eur_rub_cbrf: float = Field(..., description="Official EUR/RUB rate from CBRF")
    usd_rub_cbrf: float = Field(..., description="Official USD/RUB rate from CBRF")
    cbrf_date: str = Field(..., description="CBRF rate fixation date (DD.MM.YYYY)")


class NormalizedDefect(StrictBaseModel):
    panel_id: BodyPanel = Field(
        ..., description="Canonical body panel identifier (16 panels or 'other')"
    )
    panel_ru: str = Field(..., description="Russian name of the panel")
    defect_types: list[str] = Field(..., description="Damage types (A, U, W, S, XX, etc.)")
    severity: int | None = Field(None, ge=1, le=4, description="Severity (1..4) or null for XX/X")
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
    auction_date: str | None = Field(None, description="Auction date (DD.MM.YYYY)")
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
