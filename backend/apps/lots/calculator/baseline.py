"""Baseline snapshot capture, bid slider bounds, and stored currency-rate extraction."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from apps.core.enums import FuelType
from apps.lots.calculator.customs import CurrencyRatesInput
from apps.lots.models import (
    CurrencyRatesSnapshot,
    CustomsCalculation,
    Lot,
    WiseCostLadder,
    WiseCostStep,
)

DEFAULT_BID_SLIDER_MIN_JPY = 100_000
DEFAULT_BID_SLIDER_MAX_JPY = 2_500_000
MAX_DYNAMIC_BID_SLIDER_MAX_JPY = 50_000_000
_SLIDER_MAX_STEP_JPY = 100_000
EV_MISSING_POWER_WARNING = (
    "Мощность (л.с.) для электромобиля не найдена — акциз принят равным 0 ₽, "
    "укажите мощность вручную в симуляторе"
)


@dataclass(frozen=True)
class StoredRatesSnapshot:
    """Internal representation of CurrencyRatesSnapshot / lot.customs_rates_input."""

    jpy_rub_bank: float
    eur_rub_cbrf: float
    usd_rub_cbrf: float
    cbrf_date: str
    jpy_rate_source: str = "ДВ-банк (ориентир)"

    @classmethod
    def from_raw(cls, raw: CurrencyRatesSnapshot | dict[str, Any]) -> StoredRatesSnapshot:
        if isinstance(raw, dict):
            return cls(
                jpy_rub_bank=float(raw["jpy_rub_bank"]),
                jpy_rate_source=str(raw.get("jpy_rate_source", "ДВ-банк (ориентир)")),
                eur_rub_cbrf=float(raw["eur_rub_cbrf"]),
                usd_rub_cbrf=float(raw["usd_rub_cbrf"]),
                cbrf_date=str(raw["cbrf_date"]),
            )
        return cls(
            jpy_rub_bank=float(raw.jpy_rub_bank),
            jpy_rate_source=str(raw.jpy_rate_source),
            eur_rub_cbrf=float(raw.eur_rub_cbrf),
            usd_rub_cbrf=float(raw.usd_rub_cbrf),
            cbrf_date=str(raw.cbrf_date),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_rates(
    lot: Lot, customs_model: CustomsCalculation | None
) -> tuple[StoredRatesSnapshot | None, CurrencyRatesSnapshot | None]:
    rates_model = (
        CurrencyRatesSnapshot.objects.filter(customs=customs_model).first()
        if customs_model is not None
        else None
    )
    raw_rates = rates_model if rates_model is not None else lot.customs_rates_input
    if raw_rates is None:
        return None, rates_model
    return StoredRatesSnapshot.from_raw(raw_rates), rates_model


_extract_rates = extract_rates


def to_rates_input(rates_data: StoredRatesSnapshot) -> CurrencyRatesInput:
    return CurrencyRatesInput(
        jpy_rub=rates_data.jpy_rub_bank,
        eur_rub=rates_data.eur_rub_cbrf,
        usd_rub=rates_data.usd_rub_cbrf,
    )


def compute_bid_slider_max_jpy(
    *,
    market_price_rf_rub: int | None,
    jpy_rub: float | None,
    auction_bid_jpy: int | None = None,
    current_max_jpy: int | None = None,
) -> int:
    """Compute a bid slider upper bound (JPY) scaled for high-value vehicles."""
    candidates = [
        DEFAULT_BID_SLIDER_MAX_JPY,
        current_max_jpy or 0,
        auction_bid_jpy or 0,
    ]
    if market_price_rf_rub and market_price_rf_rub > 0 and jpy_rub and jpy_rub > 0:
        estimated_jpy = (
            math.ceil((market_price_rf_rub / jpy_rub) / _SLIDER_MAX_STEP_JPY) * _SLIDER_MAX_STEP_JPY
        )
        candidates.append(estimated_jpy)
    return min(MAX_DYNAMIC_BID_SLIDER_MAX_JPY, max(candidates))


def _sync_ev_missing_power_warning(
    lot: Lot,
    power_hp: int | None,
    lot_update_fields: list[str],
) -> None:
    """Keep EV missing-power warning aligned with current ``power_hp`` state."""
    warnings = list(lot.ocr_warnings or [])
    if lot.fuel_type == FuelType.EV and power_hp is None:
        if EV_MISSING_POWER_WARNING not in warnings:
            warnings.append(EV_MISSING_POWER_WARNING)
            lot.ocr_warnings = warnings
            lot_update_fields.append("ocr_warnings")
    elif EV_MISSING_POWER_WARNING in warnings:
        lot.ocr_warnings = [w for w in warnings if w != EV_MISSING_POWER_WARNING]
        lot_update_fields.append("ocr_warnings")


def ensure_dynamic_bid_slider_max(lot: Lot, jpy_rub: float | None = None) -> int:
    """Ensure ``lot.bid_slider_max_jpy`` fits the car's estimated JPY value."""
    if jpy_rub is None:
        rates_data, _ = extract_rates(lot, None)
        if rates_data is not None:
            jpy_rub = rates_data.jpy_rub_bank
    target_max = compute_bid_slider_max_jpy(
        market_price_rf_rub=lot.market_price_rf_rub,
        jpy_rub=jpy_rub,
        auction_bid_jpy=lot.auction_bid_jpy,
        current_max_jpy=lot.bid_slider_max_jpy,
    )
    if target_max != (lot.bid_slider_max_jpy or 0):
        lot.bid_slider_max_jpy = target_max
        if lot.pk is not None:
            lot.save(update_fields=["bid_slider_max_jpy", "updated_at"])
    return target_max


def build_baseline_snapshot(
    lot: Lot,
    customs_model: CustomsCalculation,
    ladder: WiseCostLadder,
) -> dict[str, Any]:
    """Build an immutable JSON snapshot of the lot's initial economics parameters."""
    return {
        "bid_jpy": int(lot.auction_bid_jpy or ladder.car_bid_jpy),
        "is_commercial_util": bool(customs_model.util_mode_selected_commercial),
        "include_repairs": bool(lot.is_repairs_included),
        "power_hp": lot.power_hp,
        "power_hp_source": lot.power_hp_source,
        "freight_rub": int(customs_model.freight_vladivostok_rub),
    }


def ensure_lot_baseline(
    lot: Lot,
    customs_model: CustomsCalculation,
    ladder: WiseCostLadder,
) -> dict[str, Any]:
    """Persist ``baseline_economics`` on ``lot`` if not captured yet and return it."""
    if isinstance(lot.baseline_economics, dict) and "bid_jpy" in lot.baseline_economics:
        return dict(lot.baseline_economics)
    snapshot = build_baseline_snapshot(lot, customs_model, ladder)
    lot.baseline_economics = snapshot
    lot.save(update_fields=["baseline_economics", "updated_at"])
    return snapshot


def is_simulation_modified(
    lot: Lot,
    customs_model: CustomsCalculation,
    ladder: WiseCostLadder,
) -> bool:
    """Return True when the current persisted simulation differs from baseline."""
    base = lot.baseline_economics
    if not isinstance(base, dict) or "bid_jpy" not in base:
        return False
    freight_base = base.get("freight_rub")
    return (
        int(ladder.car_bid_jpy) != int(base["bid_jpy"])
        or bool(customs_model.util_mode_selected_commercial)
        != bool(base.get("is_commercial_util", False))
        or bool(lot.is_repairs_included) != bool(base.get("include_repairs", True))
        or lot.power_hp != base.get("power_hp")
        or (
            freight_base is not None
            and int(customs_model.freight_vladivostok_rub) != int(freight_base)
        )
    )


def save_customs_calculation(
    lot: Lot,
    customs_model: CustomsCalculation | None,
    *,
    result: Any,
    selected_commercial: bool,
    rates_data: StoredRatesSnapshot,
    rates_model: CurrencyRatesSnapshot | None,
) -> CustomsCalculation:
    if customs_model is None:
        customs_model = CustomsCalculation(lot=lot)
    customs_model.age_corridor = result.age_corridor
    customs_model.duty_calculation_mode = result.duty_calculation_mode
    customs_model.engine_cc = result.engine_cc
    customs_model.duty_rate_eur_per_cc = result.duty_rate_eur_per_cc
    customs_model.effective_duty_pct = result.effective_duty_pct
    customs_model.customs_duty_eur = result.customs_duty_eur
    customs_model.customs_duty_rub = result.customs_duty_rub
    customs_model.excise_rub = result.excise_rub
    customs_model.import_vat_rub = result.import_vat_rub
    customs_model.is_under_160_hp = result.is_under_160_hp
    customs_model.util_mode_selected_commercial = selected_commercial
    customs_model.is_commercial_util = result.is_commercial_util
    customs_model.utilization_fee_rub = result.utilization_fee_rub
    customs_model.customs_clearance_fee_rub = result.customs_clearance_fee_rub
    customs_model.freight_vladivostok_rub = result.freight_vladivostok_rub
    customs_model.broker_svh_sbkts_rub = result.broker_svh_sbkts_rub
    customs_model.meti_sanction_risk = result.meti_sanction_risk
    customs_model.save()
    if rates_model is None:
        CurrencyRatesSnapshot.objects.create(customs=customs_model, **rates_data.to_dict())
    return customs_model


def save_wise_ladder(
    lot: Lot,
    ladder: WiseCostLadder | None,
    ladder_result: Any,
) -> WiseCostLadder:
    if ladder is None:
        ladder = WiseCostLadder(lot=lot)
    ladder.car_bid_jpy = ladder_result.car_bid_jpy
    ladder.car_bid_rub = ladder_result.car_bid_rub
    ladder.turnkey_cost_rub = ladder_result.turnkey_cost_rub
    ladder.market_price_rf_rub = ladder_result.market_price_rf_rub
    ladder.net_benefit_rub = ladder_result.net_benefit_rub
    ladder.benefit_percentage = ladder_result.benefit_percentage
    ladder.save()
    WiseCostStep.objects.filter(ladder=ladder).delete()
    WiseCostStep.objects.bulk_create(
        WiseCostStep(
            ladder=ladder,
            step_number=step.step_number,
            name_ru=step.name_ru,
            amount_rub=step.amount_rub,
            original_currency=step.original_currency,
            original_amount=step.original_amount,
            is_optional=step.is_optional,
        )
        for step in ladder_result.steps
    )
    return ladder
