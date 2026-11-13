import math
import uuid

from django.db.models import CharField, Count, F, Value
from django.db.models.functions import Coalesce, Concat

from apps.core.enums import BatchStatus, ItemProcessingStatus, TrafficLightColor
from apps.core.exceptions import NotFoundProblemError
from apps.lots import schemas
from apps.lots.models import (
    Batch,
    BatchItem,
    CrossAuditReport,
    FarpostRepairSummary,
    Lot,
    SafetyChecklist,
    WiseCostLadder,
)
from apps.lots.schemas import LotSummary
from apps.lots.services.economics import _build_customs_out
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

_DETAIL_RELATED_FIELDS = (
    "risk_flags",
    "verdict_detail",
    "market_info",
    "cross_audit",
    "safety_checklist",
    "customs_calc",
    "customs_calc__rates_snapshot",
    "farpost_repair",
    "wise_cost_ladder",
)

_DETAIL_PREFETCH_FIELDS = (
    "defects",
    "cross_audit__anomalies",
    "cross_audit__history",
    "safety_checklist__items",
    "farpost_repair__parts",
    "farpost_repair__service_works",
    "wise_cost_ladder__steps",
)


def _build_thumbnail_url(lot: Lot) -> str | None:
    if lot.sheet_thumbnail:
        return lot.sheet_thumbnail.url
    return None


def _build_lot_summary(lot: Lot) -> LotSummary:
    return LotSummary(
        lot_id=lot.id,
        make=lot.make,
        model=lot.model,
        year=lot.year,
        engine_cc=lot.engine_cc,
        frame_id=lot.frame_id,
        auction_house=lot.auction_house,
        lot_number=lot.lot_number,
        overall_grade=lot.overall_grade,
        mileage_km=lot.mileage_km,
        turnkey_cost_rub=lot.turnkey_cost_rub,
        market_price_rf_rub=lot.market_price_rf_rub,
        verdict=lot.verdict,
        verdict_headline=lot.verdict_headline,
        net_benefit_rub=lot.net_benefit_rub,
        meti_sanction_risk=lot.meti_sanction_risk,
        has_anomaly=lot.has_anomaly,
        anomaly_text=lot.anomaly_text,
        thumbnail_url=_build_thumbnail_url(lot),
        created_at=lot.created_at,
    )


def _apply_search(qs, query: str | None):
    query = query.strip() if query else ""
    if not query:
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
    ).filter(_search__icontains=query)


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
        .exclude(**{f"{field}": ""})
        .values(field)
        .annotate(count=Count("id"))
        .order_by("-count", field)
    )
    return [schemas.FilterCountItem(value=row[field], count=row["count"]) for row in rows]


def _build_available_filters(
    *,
    make_facet_qs,
    model_facet_qs,
    verdict_facet_qs,
) -> schemas.AvailableFilters:
    return schemas.AvailableFilters(
        total_lots_count=make_facet_qs.count(),
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
    page: int = _DEFAULT_PAGE,
    page_size: int = _DEFAULT_PAGE_SIZE,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> schemas.LotListResponse:
    base_qs = Lot.objects.filter(user=user, completed_at__isnull=False)
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
            make_facet_qs=make_facet_qs,
            model_facet_qs=model_facet_qs,
            verdict_facet_qs=verdict_facet_qs,
        ),
    )


def _has_full_detail(lot: Lot) -> bool:
    required_attrs = (
        "risk_flags",
        "verdict_detail",
        "market_info",
        "cross_audit",
        "safety_checklist",
        "customs_calc",
        "farpost_repair",
        "wise_cost_ladder",
    )
    if not all(hasattr(lot, name) for name in required_attrs):
        return False
    return hasattr(lot.customs_calc, "rates_snapshot")


def _build_normalized_sheet(lot: Lot) -> schemas.NormalizedSheet:
    return schemas.NormalizedSheet(
        lot_number=lot.lot_number,
        auction_house=lot.auction_house,
        auction_branch=lot.auction_branch,
        auction_strictness_index=lot.auction_strictness_index,
        make=lot.make,
        model=lot.model,
        trim=lot.trim,
        model_code=lot.model_code,
        chassis_number=lot.chassis_number,
        frame_id=lot.frame_id,
        frame_id_confidence=lot.frame_id_confidence,
        first_reg_year=lot.first_reg_year,
        first_reg_month=lot.first_reg_month,
        first_reg_date_str=lot.first_reg_date_str,
        is_pass_corridor_3_5=lot.is_pass_corridor_3_5,
        engine_cc=lot.engine_cc,
        power_hp=lot.power_hp,
        power_hp_source=lot.power_hp_source,
        is_under_160_hp=lot.is_under_160_hp,
        mileage_km=lot.mileage_km,
        odometer_status=lot.odometer_status,
        transmission=lot.transmission,
        drive_type=lot.drive_type,
        fuel_type=lot.fuel_type,
        color_ru=lot.color_ru,
        paint_code=lot.paint_code,
        overall_grade=lot.overall_grade,
        exterior_grade=lot.exterior_grade,
        interior_grade=lot.interior_grade,
        shaken_until=lot.shaken_until,
        recycling_fee_yen=lot.recycling_fee_yen,
        recycling_fee_paid=lot.recycling_fee_paid,
        equipment_ru=lot.equipment_ru,
        defects=[schemas.NormalizedDefect.model_validate(d) for d in lot.defects.all()],
        risk_flags=schemas.RiskFlags.model_validate(lot.risk_flags),
        inspector_notes_ru=lot.inspector_notes_ru,
        inspector_notes_raw=lot.inspector_notes_raw,
        seller_comments_ru=lot.seller_comments_ru,
        extra_ru=lot.extra_ru,
        ocr_warnings=lot.ocr_warnings,
        low_confidence_fields=lot.low_confidence_fields,
    )


def _build_audit_out(audit: CrossAuditReport) -> schemas.CrossAuditReport:
    return schemas.CrossAuditReport(
        status=audit.status,
        source_name=audit.source_name,
        is_archive_available=audit.is_archive_available,
        risk_level=audit.risk_level,
        has_critical_anomaly=audit.has_critical_anomaly,
        headline_ru=audit.headline_ru,
        times_auctioned=audit.times_auctioned,
        verified_at=audit.verified_at,
        anomalies=[schemas.AnomalyAlert.model_validate(a) for a in audit.anomalies.all()],
        history=[schemas.PastAuctionRecord.model_validate(h) for h in audit.history.all()],
    )


def _build_safety_out(checklist: SafetyChecklist) -> schemas.SafetyChecklist:
    return schemas.SafetyChecklist(
        overall_status=checklist.overall_status,
        overall_label_ru=checklist.overall_label_ru,
        items=[schemas.SafetyCheckItem.model_validate(i) for i in checklist.items.all()],
    )


def _build_farpost_out(repair: FarpostRepairSummary) -> schemas.FarpostRepairSummary:
    return schemas.FarpostRepairSummary(
        parts=[schemas.DamagedPartItem.model_validate(p) for p in repair.parts.all()],
        service_works=[
            schemas.ServiceWorkItem.model_validate(w) for w in repair.service_works.all()
        ],
        total_parts_from_rub=repair.total_parts_from_rub,
        total_works_rub=repair.total_works_rub,
        grand_total_repair_rub=repair.grand_total_repair_rub,
        has_color_matched_parts=repair.has_color_matched_parts,
        included_in_turnkey_hint_ru=repair.included_in_turnkey_hint_ru,
    )


def _build_wise_cost_out(ladder: WiseCostLadder) -> schemas.WiseCostLadder:
    return schemas.WiseCostLadder(
        car_bid_jpy=ladder.car_bid_jpy,
        car_bid_rub=ladder.car_bid_rub,
        turnkey_cost_rub=ladder.turnkey_cost_rub,
        market_price_rf_rub=ladder.market_price_rf_rub,
        net_benefit_rub=ladder.net_benefit_rub,
        benefit_percentage=ladder.benefit_percentage,
        steps=[schemas.WiseCostStep.model_validate(s) for s in ladder.steps.all()],
    )


def _build_economics(lot: Lot) -> schemas.EconomicsDetail:
    return schemas.EconomicsDetail(
        bid_slider_min_jpy=lot.bid_slider_min_jpy,
        bid_slider_max_jpy=lot.bid_slider_max_jpy,
        bid_slider_step_jpy=lot.bid_slider_step_jpy,
        is_repairs_included=lot.is_repairs_included,
        customs=_build_customs_out(lot.customs_calc),
        farpost_repair=_build_farpost_out(lot.farpost_repair),
        wise_cost_ladder=_build_wise_cost_out(lot.wise_cost_ladder),
    )


def _build_media_links(lot: Lot) -> schemas.LotMediaLinks:
    return schemas.LotMediaLinks(
        sheet_thumbnail_url=lot.sheet_thumbnail.url if lot.sheet_thumbnail else "",
        sheet_scan_url=lot.sheet_scan.url if lot.sheet_scan else "",
        drom_search_url=lot.market_info.drom_search_url,
    )


def _build_lot_detail(lot: Lot) -> schemas.LotDetailResponse:
    return schemas.LotDetailResponse(
        lot_id=lot.id,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
        passport=_build_normalized_sheet(lot),
        verdict=schemas.TrafficLightVerdict.model_validate(lot.verdict_detail),
        market=schemas.MarketComparisonInfo.model_validate(lot.market_info),
        audit=_build_audit_out(lot.cross_audit),
        safety_checklist=_build_safety_out(lot.safety_checklist),
        economics=_build_economics(lot),
        media=_build_media_links(lot),
    )


def get_lot_detail(user: User, lot_id: uuid.UUID) -> schemas.LotDetailResponse:
    try:
        lot = (
            Lot.objects.select_related(*_DETAIL_RELATED_FIELDS)
            .prefetch_related(*_DETAIL_PREFETCH_FIELDS)
            .get(id=lot_id, user=user, completed_at__isnull=False)
        )
    except Lot.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Лот не найден",
            title="Лот не найден",
        ) from exc
    if not _has_full_detail(lot):
        raise NotFoundProblemError(
            "Детальная спецификация лота ещё не готова",
            title="Лот не найден",
        )
    return _build_lot_detail(lot)
