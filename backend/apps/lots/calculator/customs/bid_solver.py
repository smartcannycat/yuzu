"""Reverse start-bid solver from target market margin."""

from __future__ import annotations

import dataclasses
import math
from decimal import Decimal

from apps.core.math_utils import round_half_up_int, to_decimal
from apps.lots.calculator.customs.calculator import build_wise_cost_ladder, calculate_customs
from apps.lots.calculator.customs.tariffs import (
    DEFAULT_FREIGHT_USD,
    LadderInput,
    StartBidInput,
    StartBidResult,
    validate_rates,
)

DEFAULT_TARGET_MARGIN_PCT = 15.0
DEFAULT_BID_STEP_JPY = 10_000


def _turnkey_for_bid(
    bid_jpy: int,
    params: StartBidInput,
    fob_rub: int,
    freight_rub: int,
) -> int:
    """Full turnkey cost for a candidate bid (engine grids, exact-sum ladder)."""
    bid_rub = round_half_up_int(bid_jpy, params.rates.jpy_rub)
    customs_value_rub = bid_rub + fob_rub + freight_rub
    customs = calculate_customs(
        dataclasses.replace(
            params.customs_params,
            customs_value_rub=customs_value_rub,
            customs_value_eur=None,
        ),
        params.rates,
        on_date=params.on_date,
    )
    ladder = build_wise_cost_ladder(
        LadderInput(
            bid_jpy=bid_jpy,
            rates=params.rates,
            customs=customs,
            market_price_rf_rub=params.market_price_rf_rub,
            japan_fob_jpy=params.japan_fob_jpy,
            broker_rub=params.broker_rub,
            repair_total_rub=params.repair_total_rub,
            include_repairs=params.include_repairs,
        )
    )
    return ladder.turnkey_cost_rub


def derive_start_bid_from_market(params: StartBidInput) -> StartBidResult:
    """Reverse-calculate the highest slider-grid bid keeping ``target_margin_pct``."""
    if params.min_bid_jpy > params.max_bid_jpy:
        raise ValueError("min_bid_jpy must not exceed max_bid_jpy")
    if params.step_jpy <= 0:
        raise ValueError("step_jpy must be positive")
    if params.market_price_rf_rub < 0:
        raise ValueError("market_price_rf_rub must not be negative")

    rates = params.rates
    validate_rates(rates)
    fob_rub = round_half_up_int(params.japan_fob_jpy, rates.jpy_rub)
    freight_rub = params.customs_params.freight_rub
    if freight_rub is None:
        freight_rub = round_half_up_int(DEFAULT_FREIGHT_USD, rates.usd_rub)

    target_turnkey_rub = math.floor(
        to_decimal(params.market_price_rf_rub) * (1 - Decimal(str(params.target_margin_pct)) / 100)
    )

    def result_for(bid_jpy: int, *, clamped: bool) -> StartBidResult:
        achieved = _turnkey_for_bid(bid_jpy, params, fob_rub, freight_rub)
        return StartBidResult(
            bid_jpy=bid_jpy,
            source="reverse_from_market",
            target_turnkey_rub=target_turnkey_rub,
            achieved_turnkey_rub=achieved,
            achieved_net_benefit_rub=params.market_price_rf_rub - achieved,
            clamped=clamped,
        )

    step_count = (params.max_bid_jpy - params.min_bid_jpy) // params.step_jpy
    max_affordable_bid_jpy = int((target_turnkey_rub + 1) / rates.jpy_rub)
    start_index = min(
        step_count,
        max(0, (max_affordable_bid_jpy - params.min_bid_jpy) // params.step_jpy),
    )
    for index in range(start_index, -1, -1):
        candidate = params.min_bid_jpy + index * params.step_jpy
        if _turnkey_for_bid(candidate, params, fob_rub, freight_rub) <= target_turnkey_rub:
            return result_for(candidate, clamped=False)

    return result_for(params.min_bid_jpy, clamped=True)
