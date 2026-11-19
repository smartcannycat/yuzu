"""Domain result schemas for the Farpost repair estimator."""

from pydantic import Field

from apps.core.enums import BodyPanel, PartSourceKind, WorkType
from apps.core.schemas import StrictBaseModel


class DamagedPartEstimate(StrictBaseModel):
    panel_id: BodyPanel
    defect_code: str
    part_name_ru: str
    subtitle_ru: str | None = None
    source_kind: PartSourceKind | str = ""
    price_from_rub: int
    in_stock_vladivostok: bool
    is_statistical_fallback: bool


class ServiceWorkEstimate(StrictBaseModel):
    work_type: WorkType
    label_ru: str
    amount_rub: int
    zero_cost_reason_ru: str | None = None


class FarpostRepairEstimate(StrictBaseModel):
    parts: list[DamagedPartEstimate] = Field(default_factory=list)
    service_works: list[ServiceWorkEstimate] = Field(default_factory=list)
    total_parts_from_rub: int
    total_works_rub: int
    grand_total_repair_rub: int
    has_color_matched_parts: bool
    included_in_turnkey_hint_ru: str
