"""Pydantic models for responses of the external ML sheet parsing service.

These schemas describe an external API payload, so they deliberately do not
inherit ``apps.core.schemas.StrictBaseModel`` (a django-ninja ``Schema``):
ninja's validation wrapper requires ``from_attributes=True`` and is designed
for ORM-bound API payloads, while external JSON must be validated with plain
``pydantic`` semantics. Unknown fields are ignored (the ML service may add
fields independently of the backend), but declared field types are strict.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MlServiceBaseModel(BaseModel):
    """Base model for external ML service payloads (extra fields are ignored)."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        use_enum_values=True,
        from_attributes=False,
    )


class ParserMeta(MlServiceBaseModel):
    processing_ms: float | None = None
    mode_used: str | None = None
    cached: bool = False
    model_used: str | None = None
    sha256: str | None = None


class RiskFlags(MlServiceBaseModel):
    is_flooded: bool = False
    airbag_deployed: bool = False
    hail_damage: bool = False
    underbody_rust: bool = False
    underbody_corrosion: bool = False
    core_support_repair: bool = False
    pillar_or_frame_repair: bool = False
    panel_replaced_xx: bool = False
    panel_needs_replacement_x: bool = False
    odometer_issue: bool = False
    color_changed: bool = False
    windshield_damage: bool = False
    repaired_grade_r_ra: bool = False


class Defect(MlServiceBaseModel):
    panel_id: str
    panel_ru: str
    defect_types: list[str] = Field(default_factory=list)
    severity: int | None = None
    description_ru: str
    raw_code: str


class NormalizedSheet(MlServiceBaseModel):
    lot_number: str | None = None
    auction_house: str | None = None
    auction_strictness_index: float | None = None
    auction_branch: str | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    model_code: str | None = None
    chassis_number: str | None = None
    frame_id: str | None = None
    frame_id_confidence: str | None = None
    first_reg_year: int | None = None
    first_reg_month: int | None = None
    first_reg_date_str: str | None = None
    is_pass_corridor_3_5: bool | None = None
    engine_cc: int | None = None
    mileage_km: int | None = None
    odometer_status: str | None = None
    transmission: str | None = None
    drive_type: str | None = None
    fuel_type: str | None = None
    color_ru: str | None = None
    paint_code: str | None = None
    overall_grade: str | None = None
    exterior_grade: str | None = None
    interior_grade: str | None = None
    shaken_until: str | None = None
    recycling_fee_yen: int | None = None
    recycling_fee_paid: bool | None = None
    equipment_ru: list[str] = Field(default_factory=list)
    defects: list[Defect] = Field(default_factory=list)
    risk_flags: RiskFlags = Field(default_factory=RiskFlags)
    inspector_notes_raw: list[str] = Field(default_factory=list)
    inspector_notes_ru: list[str] = Field(default_factory=list)
    seller_comments_ru: list[str] = Field(default_factory=list)
    extra_ru: list[str] = Field(default_factory=list)
    ocr_warnings: list[str] = Field(default_factory=list)


class ParserResponse(MlServiceBaseModel):
    status: Literal["ok", "partial", "rejected_not_sheet"]
    warnings: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    sheet: NormalizedSheet | None = None
    meta: ParserMeta = Field(default_factory=ParserMeta)
