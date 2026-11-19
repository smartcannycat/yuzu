"""Transactional economics recomputation and start-bid resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AgeCorridor, FuelType, PowerHpSource
from apps.core.math_utils import round_half_up_int
from apps.lots.calculator.baseline import (
    DEFAULT_BID_SLIDER_MAX_JPY,
    DEFAULT_BID_SLIDER_MIN_JPY,
    EV_MISSING_POWER_WARNING,
    MAX_DYNAMIC_BID_SLIDER_MAX_JPY,
    _extract_rates,
    _sync_ev_missing_power_warning,
    build_baseline_snapshot,
    compute_bid_slider_max_jpy,
    ensure_dynamic_bid_slider_max,
    ensure_lot_baseline,
    extract_rates,
    is_simulation_modified,
    save_customs_calculation,
    save_wise_ladder,
    to_rates_input,
)
from apps.lots.calculator.customs import (
    DEFAULT_FREIGHT_USD,
    DEFAULT_JAPAN_FOB_JPY,
    CurrencyRatesInput,
    CustomsInput,
    LadderInput,
    StartBidInput,
    build_wise_cost_ladder,
    calculate_customs,
    derive_start_bid_from_market,
)
from apps.lots.models import (
    CustomsCalculation,
    FarpostRepairSummary,
    Lot,
    PastAuctionRecord,
    WiseCostLadder,
)

if TYPE_CHECKING:
    from datetime import date

__all__ = [
    "DEFAULT_BID_SLIDER_MAX_JPY",
    "DEFAULT_BID_SLIDER_MIN_JPY",
    "EV_MISSING_POWER_WARNING",
    "MAX_DYNAMIC_BID_SLIDER_MAX_JPY",
    "_extract_rates",
    "_missing_customs_inputs",
    "_resolve_start_bid_jpy",
    "_sync_ev_missing_power_warning",
    "build_baseline_snapshot",
    "compute_bid_slider_max_jpy",
    "ensure_dynamic_bid_slider_max",
    "ensure_lot_baseline",
    "extract_rates",
    "is_simulation_modified",
    "recompute_lot_economics",
]


def _resolve_calculation_date(on_date: date | None) -> date:
    return on_date if on_date is not None else timezone.localdate()


def _resolve_applied_bid_jpy(
    lot: Lot,
    ladder: WiseCostLadder | None,
    bid_jpy: int | None,
) -> int:
    applied_bid_jpy = bid_jpy
    if applied_bid_jpy is None:
        applied_bid_jpy = lot.auction_bid_jpy
    if applied_bid_jpy is None and ladder is not None:
        applied_bid_jpy = ladder.car_bid_jpy
    if not applied_bid_jpy:
        raise ValueError("Отсутствует ставка на аукционе")
    return applied_bid_jpy


def _resolve_freight_rub(
    customs_model: CustomsCalculation | None,
    rates: CurrencyRatesInput,
    custom_freight_rub: int | None,
) -> int:
    if custom_freight_rub is not None:
        return custom_freight_rub
    if customs_model is not None:
        return customs_model.freight_vladivostok_rub
    return round_half_up_int(DEFAULT_FREIGHT_USD, rates.usd_rub)


def recompute_lot_economics(
    lot: Lot,
    *,
    bid_jpy: int | None = None,
    is_commercial_util: bool | None = None,
    include_repairs: bool | None = None,
    custom_power_hp: int | None = None,
    custom_freight_rub: int | None = None,
    on_date: date | None = None,
) -> None:
    """(Re)compute customs, Wise Cost Ladder and lot totals in one atomic transaction."""
    with transaction.atomic():
        lot = Lot.objects.select_for_update().get(pk=lot.pk)
        calculation_date = _resolve_calculation_date(on_date)
        customs_model = CustomsCalculation.objects.filter(lot=lot).first()
        rates_data, rates_model = extract_rates(lot, customs_model)
        if rates_data is None:
            raise ValueError("Отсутствуют курсы валют для расчёта экономики лота")
        rates = to_rates_input(rates_data)

        ladder = WiseCostLadder.objects.filter(lot=lot).first()
        applied_bid_jpy = _resolve_applied_bid_jpy(lot, ladder, bid_jpy)
        bid_rub = round_half_up_int(applied_bid_jpy, rates.jpy_rub)
        fob_rub = round_half_up_int(DEFAULT_JAPAN_FOB_JPY, rates.jpy_rub)
        freight_rub = _resolve_freight_rub(customs_model, rates, custom_freight_rub)
        selected_commercial = (
            is_commercial_util
            if is_commercial_util is not None
            else bool(customs_model and customs_model.util_mode_selected_commercial)
        )

        lot_update_fields: list[str] = []
        if custom_power_hp is not None:
            lot.power_hp = custom_power_hp
            lot.power_hp_source = PowerHpSource.MANUAL
            lot.is_under_160_hp = custom_power_hp <= 160
            lot_update_fields += ["power_hp", "power_hp_source", "is_under_160_hp"]

        power_hp = custom_power_hp if custom_power_hp is not None else lot.power_hp
        _sync_ev_missing_power_warning(lot, power_hp, lot_update_fields)
        if lot.fuel_type != FuelType.EV and not lot.engine_cc:
            raise ValueError("Отсутствует объём двигателя для расчёта пошлины")
        if not lot.first_reg_year:
            raise ValueError("Отсутствует год первой регистрации для расчёта пошлины")

        result = calculate_customs(
            CustomsInput(
                engine_cc=0 if lot.fuel_type == FuelType.EV else lot.engine_cc,
                fuel_type=lot.fuel_type,
                power_hp=power_hp,
                first_reg_year=lot.first_reg_year,
                first_reg_month=lot.first_reg_month,
                is_commercial_util=selected_commercial,
                customs_value_rub=bid_rub + fob_rub + freight_rub,
                freight_rub=freight_rub,
                broker_rub=customs_model.broker_svh_sbkts_rub if customs_model else None,
                mild_hybrid=lot.is_verified_mild_hybrid,
            ),
            rates,
            on_date=calculation_date,
        )

        repairs_included = (
            include_repairs if include_repairs is not None else lot.is_repairs_included
        )
        repair = FarpostRepairSummary.objects.filter(lot=lot).first()
        repair_total_rub = repair.grand_total_repair_rub if repair else 0
        market_price_rub = lot.market_price_rf_rub
        if market_price_rub is None:
            raise ValueError("Отсутствует рыночная цена РФ для расчёта экономики лота")

        ladder_result = build_wise_cost_ladder(
            LadderInput(
                bid_jpy=applied_bid_jpy,
                rates=rates,
                customs=result,
                market_price_rf_rub=market_price_rub,
                repair_total_rub=repair_total_rub,
                include_repairs=repairs_included,
            )
        )

        save_customs_calculation(
            lot,
            customs_model,
            result=result,
            selected_commercial=selected_commercial,
            rates_data=rates_data,
            rates_model=rates_model,
        )
        save_wise_ladder(lot, ladder, ladder_result)

        target_slider_max = compute_bid_slider_max_jpy(
            market_price_rf_rub=market_price_rub,
            jpy_rub=rates.jpy_rub,
            auction_bid_jpy=max(lot.auction_bid_jpy or 0, applied_bid_jpy),
            current_max_jpy=lot.bid_slider_max_jpy,
        )
        if target_slider_max > (lot.bid_slider_max_jpy or 0):
            lot.bid_slider_max_jpy = target_slider_max
            lot_update_fields.append("bid_slider_max_jpy")

        lot.turnkey_cost_rub = ladder_result.turnkey_cost_rub
        lot.net_benefit_rub = ladder_result.net_benefit_rub
        lot.benefit_percentage = ladder_result.benefit_percentage
        lot.is_repairs_included = repairs_included
        lot.meti_sanction_risk = result.meti_sanction_risk
        lot.is_pass_corridor_3_5 = result.age_corridor == AgeCorridor.THREE_TO_FIVE_YEARS
        lot_update_fields += [
            "turnkey_cost_rub",
            "net_benefit_rub",
            "benefit_percentage",
            "is_repairs_included",
            "meti_sanction_risk",
            "is_pass_corridor_3_5",
            "updated_at",
        ]
        lot.save(update_fields=lot_update_fields)


def _resolve_start_bid_jpy(lot: Lot) -> int | None:
    """Resolve initial bid from sheet -> auction history -> target-margin reverse grid."""
    min_bid = min(lot.bid_slider_min_jpy or DEFAULT_BID_SLIDER_MIN_JPY, DEFAULT_BID_SLIDER_MIN_JPY)
    step_bid = lot.bid_slider_step_jpy or 10_000

    customs_model = CustomsCalculation.objects.filter(lot=lot).first()
    rates_data, _ = extract_rates(lot, customs_model)
    max_bid = compute_bid_slider_max_jpy(
        market_price_rf_rub=lot.market_price_rf_rub,
        jpy_rub=rates_data.jpy_rub_bank if rates_data is not None else None,
        auction_bid_jpy=lot.auction_bid_jpy,
        current_max_jpy=lot.bid_slider_max_jpy,
    )

    def clamp(bid_jpy: int) -> int:
        return max(min_bid, min(max_bid, bid_jpy))

    if lot.auction_bid_jpy:
        return clamp(lot.auction_bid_jpy)

    record = (
        PastAuctionRecord.objects.filter(audit__lot=lot, closing_price_jpy__gt=0)
        .order_by("-auction_date", "-id")
        .first()
    )
    if record is not None:
        return clamp(record.closing_price_jpy)

    if not lot.market_price_rf_rub:
        return None
    if not lot.first_reg_year or (lot.fuel_type != FuelType.EV and not lot.engine_cc):
        return None
    if rates_data is None:
        return None

    repair = FarpostRepairSummary.objects.filter(lot=lot).first()
    result = derive_start_bid_from_market(
        StartBidInput(
            market_price_rf_rub=lot.market_price_rf_rub,
            rates=to_rates_input(rates_data),
            on_date=_resolve_calculation_date(None),
            customs_params=CustomsInput(
                engine_cc=0 if lot.fuel_type == FuelType.EV else lot.engine_cc,
                fuel_type=lot.fuel_type,
                power_hp=lot.power_hp,
                first_reg_year=lot.first_reg_year,
                first_reg_month=lot.first_reg_month,
                is_commercial_util=bool(
                    customs_model and customs_model.util_mode_selected_commercial
                ),
                freight_rub=(customs_model.freight_vladivostok_rub if customs_model else None),
                broker_rub=(customs_model.broker_svh_sbkts_rub if customs_model else None),
                mild_hybrid=lot.is_verified_mild_hybrid,
            ),
            broker_rub=customs_model.broker_svh_sbkts_rub if customs_model else None,
            repair_total_rub=repair.grand_total_repair_rub if repair else 0,
            include_repairs=lot.is_repairs_included,
            step_jpy=step_bid,
            min_bid_jpy=min_bid,
            max_bid_jpy=max_bid,
        )
    )
    return result.bid_jpy


def _missing_customs_inputs(lot: Lot, bid_jpy: int | None) -> list[str]:
    """Mandatory inputs for the customs_calc pipeline step (Russian labels)."""
    missing: list[str] = []
    if lot.fuel_type != FuelType.EV and not lot.engine_cc:
        missing.append("объём двигателя")
    if not lot.first_reg_year:
        missing.append("дата первой регистрации")
    if bid_jpy is None:
        missing.append("ставка на аукционе")
    if lot.market_price_rf_rub is None:
        missing.append("рыночная цена в РФ")
    customs = CustomsCalculation.objects.select_related("rates_snapshot").filter(lot=lot).first()
    if not lot.customs_rates_input and (customs is None or not hasattr(customs, "rates_snapshot")):
        missing.append("снимок курсов валют (шлюз ЦБ РФ)")
    return missing
