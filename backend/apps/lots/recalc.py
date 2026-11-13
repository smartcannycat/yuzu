"""Lot economics mutation services (recalculate endpoint)."""

import math

from django.utils import timezone

from apps.core.enums import TrafficLightColor
from apps.core.exceptions import BadRequestProblemError, NotFoundProblemError
from apps.lots import schemas
from apps.lots.economics import load_lot_currency_rates, recompute_lot_economics
from apps.lots.models import CustomsCalculation, Lot, WiseCostLadder
from apps.lots.scoring import compute_verdict
from apps.users.models import User


def recalculate_lot(
    user: User,
    lot_id,
    payload: schemas.RecalculateRequest,
) -> schemas.RecalculateResponse:
    lot = Lot.objects.filter(pk=lot_id, user=user).first()
    if lot is None:
        raise NotFoundProblemError(
            "Лот не найден",
            title="Лот не найден",
        )

    # Bid currency resolution: JPY directly, or RUB converted back to JPY
    # using the stored rates so the ladder keeps a single JPY base.
    bid_jpy = payload.bid_jpy
    if bid_jpy is None and payload.bid_rub is not None:
        rates_data = load_lot_currency_rates(lot)
        if rates_data is None:
            raise BadRequestProblemError(
                "Для пересчёта по ставке в рублях требуется снимок курсов валют",
                title="Курсы валют недоступны",
            )
        if rates_data.jpy_rub_bank <= 0:
            raise BadRequestProblemError(
                "Некорректный курс JPY/RUB в снимке курсов",
                title="Курсы валют недоступны",
            )
        bid_jpy = math.floor(payload.bid_rub / rates_data.jpy_rub_bank + 0.5)

    # The schema field is a plain bool (default False), so distinguish "not
    # sent" from "explicitly False" via model_fields_set: an omitted toggle
    # keeps the previously applied utilization mode, an explicit False
    # switches the lot back to the personal grid.
    is_commercial_util: bool | None = (
        payload.is_commercial_util if "is_commercial_util" in payload.model_fields_set else None
    )
    try:
        recompute_lot_economics(
            lot,
            bid_jpy=bid_jpy,
            is_commercial_util=is_commercial_util,
            include_repairs=payload.include_repairs,
            custom_power_hp=payload.custom_power_hp,
            custom_freight_rub=payload.custom_freight_rub,
        )
    except ValueError as exc:
        raise BadRequestProblemError(
            str(exc),
            title="Недостаточно данных для расчёта",
        ) from exc

    lot.refresh_from_db()
    verdict = compute_verdict(lot)

    customs_model = CustomsCalculation.objects.select_related("rates_snapshot").get(lot=lot)
    ladder = WiseCostLadder.objects.select_related("lot").get(lot=lot)
    rates_model = customs_model.rates_snapshot
    applied_bid_rub = math.floor(ladder.car_bid_jpy * rates_model.jpy_rub_bank + 0.5)

    return schemas.RecalculateResponse(
        lot_id=lot.pk,
        recalculated_at=timezone.now(),
        applied_bid_jpy=ladder.car_bid_jpy,
        applied_bid_rub=applied_bid_rub,
        is_commercial_util=customs_model.is_commercial_util,
        include_repairs=lot.is_repairs_included,
        customs=schemas.CustomsCalculation.model_validate(customs_model),
        wise_cost_ladder=_build_ladder_schema(ladder),
        turnkey_cost_rub=lot.turnkey_cost_rub,
        market_price_rf_rub=lot.market_price_rf_rub,
        net_benefit_rub=lot.net_benefit_rub,
        benefit_percentage=lot.benefit_percentage,
        verdict=_build_verdict_schema(verdict),
        pdf_report_stale=True,
    )


def _build_ladder_schema(ladder: WiseCostLadder) -> schemas.WiseCostLadder:
    steps = [
        schemas.WiseCostStep(
            step_number=step.step_number,
            name_ru=step.name_ru,
            amount_rub=step.amount_rub,
            original_currency=step.original_currency,
            original_amount=step.original_amount,
            is_optional=step.is_optional,
        )
        for step in ladder.steps.all().order_by("step_number")
    ]
    return schemas.WiseCostLadder(
        car_bid_jpy=ladder.car_bid_jpy,
        car_bid_rub=ladder.car_bid_rub,
        turnkey_cost_rub=ladder.turnkey_cost_rub,
        market_price_rf_rub=ladder.market_price_rf_rub,
        net_benefit_rub=ladder.net_benefit_rub,
        benefit_percentage=ladder.benefit_percentage,
        steps=steps,
    )


def _build_verdict_schema(verdict) -> schemas.TrafficLightVerdict:
    return schemas.TrafficLightVerdict(
        verdict=TrafficLightColor(verdict.verdict),
        headline=verdict.headline,
        short_verdict_label=verdict.short_verdict_label,
        badge_text=verdict.badge_text,
        net_benefit_rub=verdict.net_benefit_rub,
        benefit_percentage=verdict.benefit_percentage,
        body_summary_ru=verdict.body_summary_ru,
        interior_summary_ru=verdict.interior_summary_ru,
        reasoning_bullets=list(verdict.reasoning_bullets),
    )
