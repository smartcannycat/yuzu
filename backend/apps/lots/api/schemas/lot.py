"""Lot list feed, detail specification, and lifecycle action schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from apps.core.enums import (
    ItemProcessingStatus,
    LotArchiveReason,
    TaskStep,
    TrafficLightColor,
)
from apps.core.schemas import StrictBaseModel
from apps.lots.api.schemas.audit import CrossAuditReport, SafetyChecklist, TrafficLightVerdict
from apps.lots.api.schemas.batch import LotSummary
from apps.lots.api.schemas.common import NormalizedSheet
from apps.lots.api.schemas.economics import EconomicsDetail, MarketComparisonInfo


class LotMediaLinks(StrictBaseModel):
    sheet_thumbnail_url: str = Field(..., description="Auction sheet scan thumbnail URL")
    sheet_scan_url: str = Field(..., description="Full auction sheet scan URL for lightbox")
    drom_search_url: str = Field(..., description="Drom.ru analogs search URL")


class LotDetailResponse(StrictBaseModel):
    lot_id: UUID = Field(..., description="Unique lot identifier")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Update timestamp (UTC)")
    is_archived: bool = Field(False, description="Whether lot is archived")
    archived_at: datetime | None = Field(None, description="Archive timestamp (UTC)")
    archived_reason: LotArchiveReason | None = Field(None, description="Archive reason")
    expires_at: datetime | None = Field(None, description="Auto-archive deadline (UTC)")
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
    archived_lots_count: int = Field(
        0, ge=0, description="Total non-deleted archived lots for user"
    )
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


class LotLifecyclePatchRequest(StrictBaseModel):
    is_archived: bool = Field(
        ...,
        description="Archive manually (true) or restore to active without auto-archive (false)",
    )


class LotBulkDeleteRequest(StrictBaseModel):
    lot_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of lot UUIDs to soft-delete (1 to 100 per request)",
    )


class LotBulkDeleteResponse(StrictBaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs soft-deleted by this request")
    not_found_ids: list[UUID] = Field(
        default_factory=list,
        description="UUIDs not found, already deleted, or inaccessible to user",
    )
    deleted_count: int = Field(..., ge=0, description="Number of lots deleted in this request")
