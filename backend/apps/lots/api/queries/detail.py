"""Lot detail query, lifecycle API serialization, and recalculation response mapping."""

import uuid

from apps.core.exceptions import BadRequestProblemError, NotFoundProblemError
from apps.lots.api import schemas
from apps.lots.api.queries.helpers import (
    _build_audit_out,
    _build_customs_out,
    _build_economics,
    _build_lot_summary,
    _build_media_links,
    _build_normalized_sheet,
    _build_safety_out,
    _build_verdict_out,
    _build_wise_cost_out,
)
from apps.lots.calculator.recalc import (
    RecalcOutcome,
    execute_recalculate,
    execute_reset_simulation,
)
from apps.lots.exceptions import LotNotFoundDomainError, RecalcDomainError
from apps.lots.lifecycle import (
    bulk_delete_lot_ids,
    resolve_effective_archive_state,
    update_lot_archive_state,
)
from apps.lots.lifecycle import (
    delete_lot as delete_lot_domain,
)
from apps.lots.models import Lot, has_full_detail
from apps.users.models import User

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


def _build_lot_detail(lot: Lot) -> schemas.LotDetailResponse:
    is_archived, archived_at, archived_reason = resolve_effective_archive_state(lot)
    return schemas.LotDetailResponse(
        lot_id=lot.id,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
        is_archived=is_archived,
        archived_at=archived_at,
        archived_reason=archived_reason,
        expires_at=lot.expires_at,
        passport=_build_normalized_sheet(lot),
        verdict=_build_verdict_out(lot.verdict_detail),
        market=schemas.MarketComparisonInfo.model_validate(lot.market_info),
        audit=_build_audit_out(lot.cross_audit),
        safety_checklist=_build_safety_out(lot.safety_checklist),
        economics=_build_economics(lot),
        media=_build_media_links(lot),
    )


def get_lot_detail(user: User, lot_id: uuid.UUID) -> schemas.LotDetailResponse:
    """Fetch and serialize the full specification for a completed user lot."""
    try:
        lot = (
            Lot.objects.ready_for_user(user)
            .select_related(*_DETAIL_RELATED_FIELDS)
            .prefetch_related(*_DETAIL_PREFETCH_FIELDS)
            .get(id=lot_id)
        )
    except Lot.DoesNotExist as exc:
        raise NotFoundProblemError("Лот не найден", title="Лот не найден") from exc
    if not has_full_detail(lot):
        raise NotFoundProblemError(
            "Детальная спецификация лота ещё не готова",
            title="Лот не найден",
        )
    return _build_lot_detail(lot)


def _outcome_to_recalc_response(outcome: RecalcOutcome) -> schemas.RecalculateResponse:
    lot = outcome.lot
    customs_model = outcome.customs
    ladder = outcome.ladder
    return schemas.RecalculateResponse(
        lot_id=lot.pk,
        recalculated_at=outcome.recalculated_at,
        applied_bid_jpy=ladder.car_bid_jpy,
        applied_bid_rub=outcome.applied_bid_rub,
        is_commercial_util=customs_model.is_commercial_util,
        include_repairs=lot.is_repairs_included,
        customs=_build_customs_out(customs_model),
        wise_cost_ladder=_build_wise_cost_out(ladder),
        turnkey_cost_rub=lot.turnkey_cost_rub,
        market_price_rf_rub=lot.market_price_rf_rub,
        net_benefit_rub=lot.net_benefit_rub,
        benefit_percentage=lot.benefit_percentage,
        bid_slider_min_jpy=lot.bid_slider_min_jpy,
        power_hp=lot.power_hp,
        power_hp_source=lot.power_hp_source,
        is_under_160_hp=lot.is_under_160_hp,
        ocr_warnings=list(lot.ocr_warnings or []),
        verdict=_build_verdict_out(outcome.verdict),
        is_simulation_modified=outcome.is_simulation_modified,
        pdf_report_stale=outcome.pdf_report_stale,
    )


def recalculate_lot(
    user: User, lot_id: uuid.UUID, payload: schemas.RecalculateRequest
) -> schemas.RecalculateResponse:
    # Keep unset vs explicitly False clear via model_fields_set.
    is_commercial_util: bool | None = (
        payload.is_commercial_util if "is_commercial_util" in payload.model_fields_set else None
    )
    include_repairs: bool | None = (
        payload.include_repairs if "include_repairs" in payload.model_fields_set else None
    )
    try:
        outcome = execute_recalculate(
            user,
            lot_id,
            bid_jpy=payload.bid_jpy,
            bid_rub=payload.bid_rub,
            is_commercial_util=is_commercial_util,
            include_repairs=include_repairs,
            custom_power_hp=payload.custom_power_hp,
            custom_freight_rub=payload.custom_freight_rub,
        )
    except LotNotFoundDomainError as exc:
        raise NotFoundProblemError(exc.detail, title=exc.title) from exc
    except RecalcDomainError as exc:
        raise BadRequestProblemError(exc.detail, title=exc.title) from exc
    return _outcome_to_recalc_response(outcome)


def reset_lot_simulation(user: User, lot_id: uuid.UUID) -> schemas.RecalculateResponse:
    try:
        outcome = execute_reset_simulation(user, lot_id)
    except LotNotFoundDomainError as exc:
        raise NotFoundProblemError(exc.detail, title=exc.title) from exc
    except RecalcDomainError as exc:
        raise BadRequestProblemError(exc.detail, title=exc.title) from exc
    return _outcome_to_recalc_response(outcome)


def update_lot_lifecycle(user: User, lot_id: uuid.UUID, *, is_archived: bool) -> schemas.LotSummary:
    try:
        lot = update_lot_archive_state(user, lot_id, is_archived=is_archived)
    except LotNotFoundDomainError as exc:
        raise NotFoundProblemError(exc.detail, title=exc.title) from exc
    return _build_lot_summary(lot)


def delete_lot(user: User, lot_id: uuid.UUID) -> None:
    try:
        delete_lot_domain(user, lot_id)
    except LotNotFoundDomainError as exc:
        raise NotFoundProblemError(exc.detail, title=exc.title) from exc


def bulk_delete_lots(user: User, lot_ids: list[uuid.UUID]) -> schemas.LotBulkDeleteResponse:
    deleted_ids, not_found_ids = bulk_delete_lot_ids(user, lot_ids)
    return schemas.LotBulkDeleteResponse(
        deleted_ids=deleted_ids,
        not_found_ids=not_found_ids,
        deleted_count=len(deleted_ids),
    )
