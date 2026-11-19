"""EAEU duty, customs clearance fee, and Wise Cost Ladder assembly."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from apps.core.enums import AgeCorridor, DutyCalculationMode, FuelType, UtilFeeType
from apps.core.math_utils import round_half_up_int
from apps.lots.calculator.customs.recycling import (
    calculate_excise,
    calculate_utilization_fee,
    is_under_160_hp,
    meti_sanction_risk,
    resolve_age_corridor,
)
from apps.lots.calculator.customs.tariffs import (
    CLEARANCE_FEE_GRID_RUB,
    DEFAULT_BROKER_SVH_SBKTS_RUB,
    DEFAULT_FREIGHT_USD,
    DUTY_COMBINED_UNDER_3_YEARS,
    DUTY_EUR_PER_CC_3_5_YEARS,
    DUTY_EUR_PER_CC_OVER_5_YEARS,
    EV_DUTY_PCT,
    IMPORT_VAT_PCT,
    STEP_BID,
    STEP_BROKER,
    STEP_DUTY,
    STEP_DUTY_EV,
    STEP_FREIGHT,
    STEP_JAPAN,
    STEP_REPAIR,
    STEP_UTIL,
    CurrencyRatesInput,
    CustomsInput,
    CustomsResult,
    DutyBasis,
    DutyResult,
    LadderInput,
    LadderResult,
    WiseCostStepResult,
    validate_rates,
)

if TYPE_CHECKING:
    from datetime import date


def round_eur_to_rub(amount_eur: float, eur_rub: float) -> int:
    """Convert EUR to integer RUB (half-up, zero-float currency rule)."""
    return round_half_up_int(amount_eur, eur_rub)


def _tier_rate(grid: tuple[tuple[int, float], ...], engine_cc: int) -> float:
    for upper_bound, rate in grid:
        if engine_cc <= upper_bound:
            return rate
    return grid[-1][1]


def _resolve_under_3_band(customs_value_eur: float) -> tuple[float, float]:
    if not math.isfinite(customs_value_eur) or customs_value_eur < 0:
        raise ValueError("customs_value_eur must be non-negative and finite")
    for upper_bound, pct, min_eur_per_cc in DUTY_COMBINED_UNDER_3_YEARS:
        if customs_value_eur <= upper_bound:
            return pct, min_eur_per_cc
    _, pct, min_eur_per_cc = DUTY_COMBINED_UNDER_3_YEARS[-1]
    return pct, min_eur_per_cc


def calculate_duty(
    age_corridor: AgeCorridor,
    engine_cc: int,
    customs_value_eur: float | None,
    rates: CurrencyRatesInput,
) -> DutyResult:
    """EAEU import duty: EUR/cc for 3-5 and 5+ corridors, combined for <3 years."""
    if engine_cc <= 0:
        raise ValueError("engine_cc must be positive")

    if age_corridor == AgeCorridor.UNDER_3_YEARS:
        if customs_value_eur is None:
            raise ValueError("customs_value_eur is required for the under-3-years corridor")
        pct, min_eur_per_cc = _resolve_under_3_band(customs_value_eur)
        ad_valorem = customs_value_eur * pct
        specific = float(engine_cc) * min_eur_per_cc
        duty_eur = round(max(ad_valorem, specific), 2)
        basis = DutyBasis.AD_VALOREM if ad_valorem >= specific else DutyBasis.SPECIFIC_MINIMUM
        return DutyResult(
            mode=DutyCalculationMode.PCT_OF_VALUE,
            rate_eur_per_cc=None,
            effective_duty_pct=pct * 100,
            basis=basis,
            duty_eur=duty_eur,
            duty_rub=round_eur_to_rub(duty_eur, rates.eur_rub),
        )

    grid = (
        DUTY_EUR_PER_CC_OVER_5_YEARS
        if age_corridor == AgeCorridor.OVER_5_YEARS
        else DUTY_EUR_PER_CC_3_5_YEARS
    )
    rate = _tier_rate(grid, engine_cc)
    duty_eur = round(float(engine_cc) * rate, 2)
    return DutyResult(
        mode=DutyCalculationMode.EUR_PER_CC,
        rate_eur_per_cc=rate,
        effective_duty_pct=None,
        basis=None,
        duty_eur=duty_eur,
        duty_rub=round_eur_to_rub(duty_eur, rates.eur_rub),
    )


def calculate_clearance_fee(customs_value_rub: int) -> int:
    """Customs clearance fee by declared value (Decree No. 342 grid)."""
    if customs_value_rub < 0:
        raise ValueError("customs_value_rub must not be negative")
    for upper_bound, fee in CLEARANCE_FEE_GRID_RUB:
        if customs_value_rub <= upper_bound:
            return fee
    return CLEARANCE_FEE_GRID_RUB[-1][1]


def _resolve_customs_values(params: CustomsInput, rates: CurrencyRatesInput) -> tuple[float, int]:
    if params.customs_value_eur is not None and (
        not math.isfinite(params.customs_value_eur) or params.customs_value_eur < 0
    ):
        raise ValueError("customs_value_eur must be non-negative and finite")
    if params.customs_value_rub is not None and params.customs_value_rub < 0:
        raise ValueError("customs_value_rub must not be negative")

    if params.customs_value_eur is None:
        if params.customs_value_rub is None:
            raise ValueError("customs_value_eur or customs_value_rub is required for the duty")
        customs_value_eur = round(params.customs_value_rub / rates.eur_rub, 2)
    else:
        customs_value_eur = params.customs_value_eur

    if params.customs_value_rub is None:
        customs_value_rub = round_half_up_int(customs_value_eur, rates.eur_rub)
    else:
        customs_value_rub = params.customs_value_rub
    return customs_value_eur, customs_value_rub


def calculate_customs(
    params: CustomsInput,
    rates: CurrencyRatesInput,
    on_date: date,
) -> CustomsResult:
    """Full customs and logistics calculation for a single vehicle."""
    validate_rates(rates)
    age_corridor = params.age_corridor or resolve_age_corridor(
        params.first_reg_year, params.first_reg_month, on_date
    )
    freight_rub = (
        params.freight_rub
        if params.freight_rub is not None
        else round_half_up_int(DEFAULT_FREIGHT_USD, rates.usd_rub)
    )
    customs_value_eur, customs_value_rub = _resolve_customs_values(params, rates)

    fuel = str(params.fuel_type)
    excise_rub = 0
    import_vat_rub = 0
    if fuel == FuelType.EV:
        duty_eur = round(customs_value_eur * EV_DUTY_PCT, 2)
        duty_rub = round_eur_to_rub(duty_eur, rates.eur_rub)
        duty = DutyResult(
            mode=DutyCalculationMode.PCT_OF_VALUE,
            rate_eur_per_cc=None,
            effective_duty_pct=EV_DUTY_PCT * 100,
            basis=DutyBasis.AD_VALOREM,
            duty_eur=duty_eur,
            duty_rub=duty_rub,
        )
        excise_rub = calculate_excise(params.power_hp) if params.power_hp is not None else 0
        import_vat_rub = round_half_up_int(
            customs_value_rub + duty_rub + excise_rub,
            IMPORT_VAT_PCT,
        )
    else:
        duty = calculate_duty(age_corridor, params.engine_cc, customs_value_eur, rates)
    util = calculate_utilization_fee(
        age_corridor,
        params.engine_cc,
        params.power_hp,
        params.fuel_type,
        params.is_commercial_util,
    )
    return CustomsResult(
        age_corridor=age_corridor,
        duty_calculation_mode=duty.mode,
        engine_cc=params.engine_cc,
        duty_rate_eur_per_cc=duty.rate_eur_per_cc,
        effective_duty_pct=duty.effective_duty_pct,
        customs_duty_eur=duty.duty_eur,
        customs_duty_rub=duty.duty_rub,
        excise_rub=excise_rub,
        import_vat_rub=import_vat_rub,
        is_under_160_hp=is_under_160_hp(params.power_hp),
        is_commercial_util=params.is_commercial_util or util.fee_type == UtilFeeType.COMMERCIAL,
        utilization_fee_rub=util.fee_rub,
        utilization_fee_type=util.fee_type,
        customs_clearance_fee_rub=calculate_clearance_fee(customs_value_rub),
        freight_vladivostok_rub=freight_rub,
        broker_svh_sbkts_rub=(
            params.broker_rub if params.broker_rub is not None else DEFAULT_BROKER_SVH_SBKTS_RUB
        ),
        meti_sanction_risk=meti_sanction_risk(
            params.fuel_type,
            params.engine_cc,
            mild_hybrid=params.mild_hybrid,
        ),
    )


def build_wise_cost_ladder(params: LadderInput) -> LadderResult:
    """Assemble the 7-step Wise Cost Ladder with exact-sum guarantee."""
    rates = params.rates
    validate_rates(rates)
    customs = params.customs

    bid_rub = round_half_up_int(params.bid_jpy, rates.jpy_rub)
    fob_rub = round_half_up_int(params.japan_fob_jpy, rates.jpy_rub)
    freight_rub = customs.freight_vladivostok_rub
    duty_step_rub = (
        customs.customs_duty_rub
        + customs.excise_rub
        + customs.import_vat_rub
        + customs.customs_clearance_fee_rub
    )
    util_rub = customs.utilization_fee_rub
    broker_rub = (
        params.broker_rub if params.broker_rub is not None else customs.broker_svh_sbkts_rub
    )
    repair_rub = params.repair_total_rub if params.include_repairs else 0

    is_ev_aggregate = customs.excise_rub > 0 or customs.import_vat_rub > 0
    duty_step_name = STEP_DUTY_EV if is_ev_aggregate else STEP_DUTY
    duty_original_currency = None if is_ev_aggregate else "EUR"
    duty_original_amount = None if is_ev_aggregate else customs.customs_duty_eur

    steps = [
        WiseCostStepResult(1, STEP_BID, bid_rub, "JPY", float(params.bid_jpy), False),
        WiseCostStepResult(2, STEP_JAPAN, fob_rub, "JPY", float(params.japan_fob_jpy), False),
        WiseCostStepResult(
            3, STEP_FREIGHT, freight_rub, "USD", round(freight_rub / rates.usd_rub, 2), False
        ),
        WiseCostStepResult(
            4, duty_step_name, duty_step_rub, duty_original_currency, duty_original_amount, False
        ),
        WiseCostStepResult(5, STEP_UTIL, util_rub, "RUB", float(util_rub), False),
        WiseCostStepResult(6, STEP_BROKER, broker_rub, "RUB", float(broker_rub), False),
        WiseCostStepResult(7, STEP_REPAIR, repair_rub, "RUB", float(repair_rub), True),
    ]

    turnkey_cost_rub = sum(step.amount_rub for step in steps)
    if turnkey_cost_rub <= 0:
        raise ValueError("turnkey_cost_rub must be positive")
    net_benefit_rub = params.market_price_rf_rub - turnkey_cost_rub
    benefit_percentage = round(net_benefit_rub / turnkey_cost_rub * 100, 1)

    return LadderResult(
        car_bid_jpy=params.bid_jpy,
        car_bid_rub=bid_rub,
        turnkey_cost_rub=turnkey_cost_rub,
        market_price_rf_rub=params.market_price_rf_rub,
        net_benefit_rub=net_benefit_rub,
        benefit_percentage=benefit_percentage,
        steps=steps,
    )
