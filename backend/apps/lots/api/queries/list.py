"""Paginated lot feed, faceted search, and active batch summary queries."""

import math

from django.db.models import CharField, Count, F, Q, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

from apps.core.enums import (
    BatchStatus,
    ItemProcessingStatus,
    LotLifecycleFilter,
    TrafficLightColor,
)
from apps.lots.api import schemas
from apps.lots.api.queries.helpers import _build_lot_summary
from apps.lots.models import Batch, BatchItem, Lot
from apps.users.models import User

_SORT_FIELD_MAP: dict[str, str] = {
    "created_at": "created_at",
    "net_benefit": "net_benefit_rub",
    "turnkey_cost": "turnkey_cost_rub",
}

_ACTIVE_BATCH_STATUSES = frozenset({BatchStatus.QUEUED, BatchStatus.PROCESSING})
_PROCESSING_ITEM_STATUSES = frozenset(
    {ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING}
)

_DEFAULT_PAGE = 1
_DEFAULT_PAGE_SIZE = 20


def _apply_search(qs, query: str | None):
    cleaned = query.strip() if query else ""
    if not cleaned:
        return qs
    return qs.annotate(
        _search=Concat(
            Coalesce(F("make"), Value("")),
            Value(" "),
            Coalesce(F("model"), Value("")),
            Value(" "),
            Coalesce(F("frame_id"), Value("")),
            Value(" "),
            Coalesce(F("lot_number"), Value("")),
            Value(" "),
            Coalesce(F("auction_house"), Value("")),
            Value(" "),
            Coalesce(F("verdict_headline"), Value("")),
            output_field=CharField(),
        ),
    ).filter(_search__icontains=cleaned)


def _apply_filters(
    qs,
    *,
    make: str | None,
    model: str | None,
    verdict: TrafficLightColor | None,
    has_anomaly: bool | None,
):
    if make:
        qs = qs.filter(make__iexact=make)
    if model:
        qs = qs.filter(model__iexact=model)
    if verdict:
        qs = qs.filter(verdict=verdict)
    if has_anomaly is not None:
        qs = qs.filter(has_anomaly=has_anomaly)
    return qs


def _apply_sorting(qs, *, sort_by: str, sort_order: str):
    field = _SORT_FIELD_MAP[sort_by]
    return qs.order_by(field if sort_order == "asc" else f"-{field}", "pk")


def _facet_counts(qs, field: str) -> list[schemas.FilterCountItem]:
    rows = (
        qs.exclude(**{f"{field}__isnull": True})
        .exclude(**{field: ""})
        .values(field)
        .annotate(count=Count("id"))
        .order_by("-count", field)
    )
    return [schemas.FilterCountItem(value=row[field], count=row["count"]) for row in rows]


def _build_available_filters(
    *,
    total_lots_count: int,
    archived_lots_count: int,
    make_facet_qs,
    model_facet_qs,
    verdict_facet_qs,
) -> schemas.AvailableFilters:
    return schemas.AvailableFilters(
        total_lots_count=total_lots_count,
        archived_lots_count=archived_lots_count,
        makes=_facet_counts(make_facet_qs, "make"),
        models=_facet_counts(model_facet_qs, "model"),
        counts_by_verdict={
            row["verdict"]: row["count"]
            for row in verdict_facet_qs.exclude(verdict__isnull=True)
            .exclude(verdict="")
            .values("verdict")
            .annotate(count=Count("id"))
        },
    )


def _build_in_progress_item(item: BatchItem) -> schemas.InProgressItemPreview:
    return schemas.InProgressItemPreview(
        batch_id=item.batch_id,
        lot_id=item.lot_id,
        display_title=item.preview_title or item.original_filename,
        status=item.status,
        current_step=item.current_step,
    )


def _build_in_progress(user: User) -> schemas.InProgressSummary:
    active_batches_count = Batch.objects.filter(
        user=user,
        status__in=_ACTIVE_BATCH_STATUSES,
    ).count()
    items = list(
        BatchItem.objects.filter(
            batch__user=user,
            batch__status__in=_ACTIVE_BATCH_STATUSES,
            status__in=_PROCESSING_ITEM_STATUSES,
        )
        .filter(Q(lot__isnull=True) | Q(lot__deleted_at__isnull=True))
        .select_related("batch")
        .order_by("-batch__created_at", "file_index"),
    )
    return schemas.InProgressSummary(
        active_batches_count=active_batches_count,
        total_processing_lots=len(items),
        items=[_build_in_progress_item(item) for item in items],
    )


def get_lots_list(
    user: User,
    *,
    query: str | None = None,
    make: str | None = None,
    model: str | None = None,
    verdict: TrafficLightColor | None = None,
    has_anomaly: bool | None = None,
    lifecycle: LotLifecycleFilter = LotLifecycleFilter.ACTIVE,
    page: int = _DEFAULT_PAGE,
    page_size: int = _DEFAULT_PAGE_SIZE,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> schemas.LotListResponse:
    """Return a paginated, filtered, and faceted lot feed for the user."""
    now = timezone.now()
    non_deleted_qs = Lot.objects.ready_for_user(user)
    archived_lots_count = non_deleted_qs.effectively_archived(now).count()
    if lifecycle == LotLifecycleFilter.ACTIVE:
        base_qs = non_deleted_qs.effectively_active(now)
    elif lifecycle == LotLifecycleFilter.ARCHIVED:
        base_qs = non_deleted_qs.effectively_archived(now)
    else:
        base_qs = non_deleted_qs
    total_lots_count = base_qs.count()
    searched = _apply_search(base_qs, query)
    if has_anomaly is not None:
        searched = searched.filter(has_anomaly=has_anomaly)

    make_facet_qs = _apply_filters(
        searched, make=None, model=None, verdict=verdict, has_anomaly=None
    )
    model_facet_qs = _apply_filters(
        searched, make=make, model=None, verdict=verdict, has_anomaly=None
    )
    verdict_facet_qs = _apply_filters(
        searched, make=make, model=model, verdict=None, has_anomaly=None
    )

    filtered = _apply_filters(searched, make=make, model=model, verdict=verdict, has_anomaly=None)
    sorted_qs = _apply_sorting(filtered, sort_by=sort_by, sort_order=sort_order)

    total_items = sorted_qs.count()
    total_pages = math.ceil(total_items / page_size) if total_items else 0
    offset = (page - 1) * page_size
    page_lots = list(sorted_qs[offset : offset + page_size])

    return schemas.LotListResponse(
        items=[_build_lot_summary(lot) for lot in page_lots],
        in_progress=_build_in_progress(user),
        pagination=schemas.PaginationMeta(
            total_items=total_items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
        available_filters=_build_available_filters(
            total_lots_count=total_lots_count,
            archived_lots_count=archived_lots_count,
            make_facet_qs=make_facet_qs,
            model_facet_qs=model_facet_qs,
            verdict_facet_qs=verdict_facet_qs,
        ),
    )
