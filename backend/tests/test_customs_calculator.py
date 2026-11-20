"""Unit and integration tests for customs tariffs, utilization fees, bid solver, and rounding."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.enums import (
    AgeCorridor,
    DutyCalculationMode,
    FuelType,
    TrafficLightColor,
    UtilFeeType,
)
from apps.core.math_utils import round_half_up_int, to_decimal
from apps.lots.calculator.customs import (
    CurrencyRatesInput,
    CustomsInput,
    DutyBasis,
    StartBidInput,
    calculate_clearance_fee,
    calculate_customs,
    calculate_duty,
    calculate_excise,
    calculate_utilization_fee,
    derive_start_bid_from_market,
    resolve_age_corridor,
)
from apps.lots.calculator.customs.tariffs import validate_rates
from apps.lots.calculator.safety import build_cross_audit_baseline
from apps.lots.calculator.scoring import compute_verdict
from apps.lots.models import CrossAuditReport, Lot, LotRiskFlags, TrafficLightVerdict


def test_round_half_up_int_exact_decimal_behavior() -> None:
    assert round_half_up_int(2.5) == 3
    assert round_half_up_int(2.4999) == 2
    assert round_half_up_int(-2.5) == -3
    assert round_half_up_int(95_000, 0.5293) == 50_284
    assert round_half_up_int(100, 1.005) == 101
    assert round_half_up_int(Decimal("12.5")) == 13
    assert to_decimal(42) == Decimal(42)

    for bad_val in (float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError, match="finite"):
            round_half_up_int(bad_val)
    with pytest.raises(TypeError):
        round_half_up_int(True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"jpy_rub": 0.0, "eur_rub": 95.0, "usd_rub": 85.0},
        {"jpy_rub": -0.5, "eur_rub": 95.0, "usd_rub": 85.0},
        {"jpy_rub": float("nan"), "eur_rub": 95.0, "usd_rub": 85.0},
        {"jpy_rub": 0.55, "eur_rub": float("inf"), "usd_rub": 85.0},
        {"jpy_rub": 0.55, "eur_rub": 95.0, "usd_rub": float("-inf")},
        {"jpy_rub": 0.55, "eur_rub": 95.0, "usd_rub": float("nan")},
    ],
)
def test_validate_rates_rejects_non_positive_nan_and_inf(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        validate_rates(CurrencyRatesInput(**kwargs))


@pytest.mark.parametrize(
    ("value_eur", "cc", "expected_pct", "expected_eur", "expected_basis"),
    [
        (8_000.0, 1_500, 54.0, 4_320.0, DutyBasis.AD_VALOREM),
        (5_000.0, 1_500, 54.0, 3_750.0, DutyBasis.SPECIFIC_MINIMUM),
        (15_000.0, 1_500, 48.0, 7_200.0, DutyBasis.AD_VALOREM),
        (20_000.0, 2_000, 48.0, 11_000.0, DutyBasis.SPECIFIC_MINIMUM),
        (50_000.0, 2_500, 48.0, 24_000.0, DutyBasis.AD_VALOREM),
        (100_000.0, 3_500, 48.0, 52_500.0, DutyBasis.SPECIFIC_MINIMUM),
        (2_000_000_000.0, 3_000, 48.0, 960_000_000.0, DutyBasis.AD_VALOREM),
    ],
)
def test_calculate_duty_under_3_years_including_open_ended_top_band(
    value_eur: float,
    cc: int,
    expected_pct: float,
    expected_eur: float,
    expected_basis: DutyBasis,
) -> None:
    rates = CurrencyRatesInput(jpy_rub=0.55, eur_rub=100.0, usd_rub=90.0)
    res = calculate_duty(AgeCorridor.UNDER_3_YEARS, cc, value_eur, rates)
    assert res.mode == DutyCalculationMode.PCT_OF_VALUE
    assert res.rate_eur_per_cc is None
    assert res.effective_duty_pct == expected_pct
    assert res.duty_eur == expected_eur
    assert res.basis == expected_basis
    assert res.duty_rub == round_half_up_int(expected_eur, 100.0)


@pytest.mark.parametrize(
    ("corridor", "cc", "expected_rate"),
    [
        (AgeCorridor.THREE_TO_FIVE_YEARS, 998, 1.5),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 1_500, 1.7),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 1_800, 2.5),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 2_300, 2.7),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 3_000, 3.0),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 3_500, 3.6),
        (AgeCorridor.THREE_TO_FIVE_YEARS, 2_000_000_000, 3.6),
        (AgeCorridor.OVER_5_YEARS, 998, 3.0),
        (AgeCorridor.OVER_5_YEARS, 1_500, 3.2),
        (AgeCorridor.OVER_5_YEARS, 1_800, 3.5),
        (AgeCorridor.OVER_5_YEARS, 2_300, 4.8),
        (AgeCorridor.OVER_5_YEARS, 3_000, 5.0),
        (AgeCorridor.OVER_5_YEARS, 3_500, 5.7),
        (AgeCorridor.OVER_5_YEARS, 2_000_000_000, 5.7),
    ],
)
def test_calculate_duty_3_to_5_and_over_5_brackets(
    corridor: AgeCorridor,
    cc: int,
    expected_rate: float,
) -> None:
    rates = CurrencyRatesInput(jpy_rub=0.55, eur_rub=100.0, usd_rub=90.0)
    res = calculate_duty(corridor, cc, None, rates)
    assert res.mode == DutyCalculationMode.EUR_PER_CC
    assert res.rate_eur_per_cc == expected_rate
    assert res.duty_eur == round(cc * expected_rate, 2)


def test_calculate_duty_and_clearance_rejects_invalid_inputs_and_handles_large_values() -> None:
    rates = CurrencyRatesInput(jpy_rub=0.55, eur_rub=100.0, usd_rub=90.0)
    with pytest.raises(ValueError, match="engine_cc"):
        calculate_duty(AgeCorridor.THREE_TO_FIVE_YEARS, 0, None, rates)
    for bad_eur in (float("nan"), float("inf"), -10.0):
        with pytest.raises(ValueError, match="customs_value_eur"):
            calculate_duty(AgeCorridor.UNDER_3_YEARS, 1_500, bad_eur, rates)
    assert calculate_clearance_fee(200_000) == 775
    assert calculate_clearance_fee(10**12) == 30_000
    with pytest.raises(ValueError, match="customs_value_rub"):
        calculate_clearance_fee(-1)


def test_utilization_fee_160_161_hp_cutoff_commercial_2026_and_open_ended_cc() -> None:
    p160_new = calculate_utilization_fee(AgeCorridor.UNDER_3_YEARS, 1_500, 160, FuelType.GASOLINE)
    assert p160_new.fee_type == UtilFeeType.PERSONAL
    assert p160_new.fee_rub == 3_400

    p160_old = calculate_utilization_fee(
        AgeCorridor.THREE_TO_FIVE_YEARS, 1_500, 160, FuelType.GASOLINE
    )
    assert p160_old.fee_type == UtilFeeType.PERSONAL
    assert p160_old.fee_rub == 5_200

    c161 = calculate_utilization_fee(AgeCorridor.THREE_TO_FIVE_YEARS, 1_500, 161, FuelType.GASOLINE)
    assert c161.fee_type == UtilFeeType.COMMERCIAL
    assert c161.fee_rub == 1_408_800

    c_none_hp = calculate_utilization_fee(AgeCorridor.UNDER_3_YEARS, 1_000, None, FuelType.GASOLINE)
    assert c_none_hp.fee_type == UtilFeeType.COMMERCIAL
    assert c_none_hp.fee_rub == 216_200

    for cc, expected_new, expected_old in (
        (1_000, 216_200, 557_800),
        (2_000, 800_800, 1_408_800),
        (3_000, 2_250_400, 2_840_400),
        (3_500, 2_576_600, 3_287_800),
        (4_000, 3_290_600, 3_848_400),
        (2_000_000_000, 3_290_600, 3_848_400),
    ):
        res_new = calculate_utilization_fee(
            AgeCorridor.UNDER_3_YEARS, cc, 120, FuelType.GASOLINE, is_commercial_util=True
        )
        res_old = calculate_utilization_fee(
            AgeCorridor.OVER_5_YEARS, cc, 120, FuelType.GASOLINE, is_commercial_util=True
        )
        assert res_new.fee_rub == expected_new
        assert res_old.fee_rub == expected_old

    ev_new = calculate_utilization_fee(AgeCorridor.UNDER_3_YEARS, 0, 150, FuelType.EV, True)
    ev_old = calculate_utilization_fee(AgeCorridor.THREE_TO_FIVE_YEARS, 0, 150, FuelType.EV, True)
    assert ev_new.fee_rub == 800_800
    assert ev_old.fee_rub == 1_408_800


def test_ev_excise_vat_and_age_corridor_boundaries() -> None:
    assert calculate_excise(90) == 0
    assert calculate_excise(150) == 150 * 64
    assert calculate_excise(2_000_000) == 2_000_000 * 1_829

    assert resolve_age_corridor(2023, 5, date(2026, 5, 14)) == AgeCorridor.UNDER_3_YEARS
    assert resolve_age_corridor(2023, 5, date(2026, 5, 15)) == AgeCorridor.THREE_TO_FIVE_YEARS
    assert resolve_age_corridor(2021, 5, date(2026, 5, 15)) == AgeCorridor.THREE_TO_FIVE_YEARS
    assert resolve_age_corridor(2021, 5, date(2026, 5, 16)) == AgeCorridor.OVER_5_YEARS
    assert resolve_age_corridor(2021, None, date(2024, 6, 30)) == AgeCorridor.UNDER_3_YEARS
    assert resolve_age_corridor(2021, None, date(2024, 7, 1)) == AgeCorridor.THREE_TO_FIVE_YEARS

    rates = CurrencyRatesInput(jpy_rub=0.55, eur_rub=100.0, usd_rub=90.0)
    ev_res = calculate_customs(
        CustomsInput(
            engine_cc=0,
            fuel_type=FuelType.EV,
            power_hp=150,
            first_reg_year=2022,
            first_reg_month=2,
            customs_value_rub=2_000_000,
        ),
        rates,
        on_date=date(2026, 5, 1),
    )
    assert ev_res.customs_duty_rub == 300_000
    assert ev_res.excise_rub == 9_600
    assert ev_res.import_vat_rub == round_half_up_int(2_000_000 + 300_000 + 9_600, 0.22)
    assert ev_res.meti_sanction_risk is True


def test_bid_solver_derives_target_margin_and_clamps_floor() -> None:
    rates = CurrencyRatesInput(jpy_rub=0.55, eur_rub=95.0, usd_rub=85.0)
    customs_params = CustomsInput(
        engine_cc=1_500,
        fuel_type=FuelType.GASOLINE,
        power_hp=118,
        first_reg_year=2022,
        first_reg_month=2,
    )
    solved = derive_start_bid_from_market(
        StartBidInput(
            market_price_rf_rub=2_500_000,
            rates=rates,
            on_date=date(2026, 5, 1),
            customs_params=customs_params,
            target_margin_pct=15.0,
        )
    )
    assert solved.clamped is False
    assert 100_000 <= solved.bid_jpy <= 2_500_000
    assert solved.achieved_turnkey_rub <= math.floor(2_500_000 * 0.85)

    clamped = derive_start_bid_from_market(
        StartBidInput(
            market_price_rf_rub=300_000,
            rates=rates,
            on_date=date(2026, 5, 1),
            customs_params=customs_params,
            min_bid_jpy=100_000,
            max_bid_jpy=2_500_000,
        )
    )
    assert clamped.clamped is True
    assert clamped.bid_jpy == 100_000


@pytest.mark.django_db
def test_safety_and_scoring_updates_are_atomic(user_factory) -> None:
    user = user_factory(email="atomic-calc@example.com")
    lot = Lot.objects.create(
        user=user,
        make="Honda",
        model="Vezel",
        net_benefit_rub=200_000,
        benefit_percentage=15.0,
        turnkey_cost_rub=1_500_000,
        market_price_rf_rub=1_700_000,
        verdict=TrafficLightColor.YELLOW,
        verdict_headline="OLD",
        has_anomaly=False,
    )
    LotRiskFlags.objects.create(lot=lot, is_flooded=True)

    orig_save = Lot.save

    def failing_lot_save(self, *args, **kwargs):
        if kwargs.get("update_fields") in (
            ["has_anomaly", "anomaly_text", "updated_at"],
            ["verdict", "verdict_headline", "updated_at"],
        ):
            raise RuntimeError("simulated DB failure on Lot.save")
        return orig_save(self, *args, **kwargs)

    with (
        patch.object(Lot, "save", failing_lot_save),
        pytest.raises(RuntimeError, match="simulated DB failure"),
    ):
        build_cross_audit_baseline(lot)
    assert CrossAuditReport.objects.filter(lot=lot).exists() is False

    with (
        patch.object(Lot, "save", failing_lot_save),
        pytest.raises(RuntimeError, match="simulated DB failure"),
    ):
        compute_verdict(lot)
    assert TrafficLightVerdict.objects.filter(lot=lot).exists() is False
    lot.refresh_from_db()
    assert lot.verdict == TrafficLightColor.YELLOW
    assert lot.verdict_headline == "OLD"
