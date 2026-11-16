"""Cross-audit, safety checklist, and traffic-light verdict schemas."""

from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator

from apps.core.enums import (
    AnomalySeverity,
    ChecklistItemStatus,
    CrossAuditStatus,
    RiskLevel,
    SystemKey,
    TrafficLightColor,
)
from apps.core.schemas import StrictBaseModel


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
