"""Batch upload, progress polling, and compact LotSummary schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from apps.core.enums import (
    AuctionHouse,
    BatchStatus,
    ItemProcessingStatus,
    LotArchiveReason,
    MascotMood,
    TaskStep,
    TrafficLightColor,
)
from apps.core.schemas import StrictBaseModel


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
    auction_date: str | None = Field(None, description="Auction date (DD.MM.YYYY)")
    is_archived: bool = Field(False, description="Whether lot is archived")
    archived_at: datetime | None = Field(None, description="Archive timestamp (UTC)")
    archived_reason: LotArchiveReason | None = Field(None, description="Archive reason")
    expires_at: datetime | None = Field(None, description="Auto-archive deadline (UTC)")
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
