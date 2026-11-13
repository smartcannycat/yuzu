"""EAEU customs, utilization fee and turnkey cost calculation engine (BE-09).

Pure calculation domain: no Django models or IO, so it can be reused by the
batch pipeline ``customs_calc`` step, the ``recalculate`` endpoint and tests.

Normative sources (research/02_REGULATORY_CUSTOMS_AND_SANCTIONS_FRAMEWORK.md):
- EAEU duty rates: Decision of the Eurasian Economic Commission No. 107.
- Customs clearance fee grid: Government Decree No. 342 (26.03.2020).
- Utilization fee: Federal Law 89, Decrees No. 1291 / No. 1255 / No. 1713.
- Export sanctions: METI directive 750 (09.08.2023, MHEV amendment 11.2024).

All RUB/JPY amounts are integers (zero-float currency rule); EUR duty amounts
are floats rounded to 2 decimal places per API_DATA_CONTRACTS.md.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from apps.core.enums import (
    AgeCorridor,
    DutyCalculationMode,
    FuelType,
    UtilFeeType,
)

# Sentinel upper bounds for the last (unbounded) tier of each grid.
_UNBOUNDED_CC = 10**9
_UNBOUNDED_HP = 10**6
_UNBOUNDED_VALUE_EUR = 10**9
_UNBOUNDED_VALUE_RUB = 10**11

# Engine-specific constant defaults aligned with the benchmark case
# (docs/BENCHMARK_CASE_COROLLA_TOURING.md and canonical API contract JSON).
DEFAULT_JAPAN_FOB_JPY = 95_000
DEFAULT_FREIGHT_USD = 1_150
DEFAULT_BROKER_SVH_SBKTS_RUB = 99_000

# EAEU unified duty per cc (EUR) for the 3-to-5-years corridor.
# (upper cc bound inclusive, EUR per 1 cc)
_DUTY_EUR_PER_CC_3_5_YEARS: tuple[tuple[int, float], ...] = (
    (1_000, 1.5),
    (1_500, 1.7),
    (1_800, 2.5),
    (2_300, 2.7),
    (3_000, 3.0),
    (_UNBOUNDED_CC, 3.6),
)

# EAEU unified duty per cc (EUR) for the over-5-years corridor.
_DUTY_EUR_PER_CC_OVER_5_YEARS: tuple[tuple[int, float], ...] = (
    (1_000, 3.0),
    (1_500, 3.2),
    (1_800, 3.5),
    (2_300, 4.8),
    (3_000, 5.0),
    (_UNBOUNDED_CC, 5.7),
)

# Combined duty for the under-3-years corridor: percentage of customs value
# or a minimum specific rate per cc, whichever is greater (Decision No. 107).
# (upper customs value bound inclusive in EUR, pct, min EUR per cc)
_DUTY_COMBINED_UNDER_3_YEARS: tuple[tuple[int, float, float], ...] = (
    (8_500, 0.54, 2.5),
    (16_700, 0.48, 3.5),
    (42_300, 0.48, 5.5),
    (84_500, 0.48, 7.5),
    (169_000, 0.48, 15.0),
    (_UNBOUNDED_VALUE_EUR, 0.48, 20.0),
)

# Customs clearance fee grid (Government Decree No. 342). The 450k-1.2M band
# follows the canonical API contract examples (3120 RUB, see
# docs/API_DATA_CONTRACTS.md benchmark snippets and BENCHMARK_CASE doc).
# (upper customs value bound inclusive in RUB, fee in RUB)
_CLEARANCE_FEE_GRID_RUB: tuple[tuple[int, int], ...] = (
    (200_000, 775),
    (450_000, 1_550),
    (1_200_000, 3_120),
    (2_700_000, 8_530),
    (4_200_000, 12_000),
    (5_500_000, 15_500),
    (7_000_000, 20_000),
    (8_000_000, 23_000),
    (9_000_000, 25_000),
    (10_000_000, 27_000),
    (_UNBOUNDED_VALUE_RUB, 30_000),
)

# Personal (privileged) utilization fee for individuals (Decree No. 1713):
# base rate 20,000 RUB x coefficient. Requires engine power <= 160 hp.
_UTIL_PERSONAL_RUB = {
    AgeCorridor.UNDER_3_YEARS: 3_400,
    AgeCorridor.THREE_TO_FIVE_YEARS: 5_200,
    AgeCorridor.OVER_5_YEARS: 5_200,
}

# Commercial utilization fee grid, 2026 rates (Decree No. 1255).
# (upper cc bound inclusive, fee for cars under 3 years, fee for cars 3+ years)
_UTIL_COMMERCIAL_2026_RUB: tuple[tuple[int, int, int], ...] = (
    (1_000, 216_200, 557_800),
    (2_000, 800_800, 1_408_800),
    (3_000, 2_250_400, 2_840_400),
    (3_500, 2_576_600, 3_287_800),
    (_UNBOUNDED_CC, 3_290_600, 3_848_400),
)

# Battery electric vehicles are subject to a dedicated commercial grid row.
_UTIL_COMMERCIAL_EV_2026_RUB = (800_800, 1_408_800)

# METI sanction threshold for ICE vehicles (directive 750).
_METI_ICE_MAX_ENGINE_CC = 1_900

# BEV import duty share of the aggregate customs payment (research/02, 1.5).
_EV_DUTY_PCT = 0.15

# Import excise on passenger cars by engine power, 2026 rates per 1 hp
# (Tax Code art. 193 as amended by Federal Law No. 425-FZ of 28.11.2025).
# (upper hp bound inclusive, RUB per 1 hp)
_EXCISE_2026_RUB_PER_HP: tuple[tuple[int, int], ...] = (
    (90, 0),
    (150, 64),
    (200, 613),
    (300, 1_004),
    (400, 1_711),
    (500, 1_771),
    (_UNBOUNDED_HP, 1_829),
)

# Import VAT rate. research/02 (section 1.5) names 20%, but Federal Law
# No. 425-FZ raised import VAT to 22% from 01.01.2026; the legal rate wins.
_IMPORT_VAT_PCT = 0.22

# Utilization fee privilege power threshold (Decree No. 1713).
_UTIL_PRIVILEGED_MAX_HP = 160

# Canonical Wise Cost Ladder step names (Screen 6, API contract).
_STEP_BID = "Ставка на аукционе"
_STEP_JAPAN = "Расходы в Японии (FOB и сбор)"
_STEP_FREIGHT = "Фрахт Тояма-ВЛК"
_STEP_DUTY = "Таможенная пошлина ЕАЭС и сбор"
_STEP_DUTY_EV = "Таможня ЕАЭС (пошлина, акциз, НДС, сбор)"
_STEP_UTIL = "Утилизационный сбор РФ"
_STEP_BROKER = "СВХ, брокер, СБКТС, ЭПТС"
_STEP_REPAIR = "Запчасти Farpost и ремонт"


class DutyBasis(StrEnum):
    """Which side of a combined duty rate determined the final amount."""

    AD_VALOREM = "ad_valorem"
    SPECIFIC_MINIMUM = "specific_minimum"


@dataclass(frozen=True)
class CurrencyRatesInput:
    """Exchange rates snapshot used by a single calculation."""

    jpy_rub: float
    eur_rub: float
    usd_rub: float


@dataclass(frozen=True)
class DutyResult:
    """EAEU import duty for one vehicle."""

    mode: DutyCalculationMode
    rate_eur_per_cc: float | None
    effective_duty_pct: float | None
    basis: DutyBasis | None
    duty_eur: float
    duty_rub: int


@dataclass(frozen=True)
class UtilizationFeeResult:
    """RF utilization fee for one vehicle."""

    fee_rub: int
    fee_type: UtilFeeType


@dataclass(frozen=True)
class CustomsInput:
    """Vehicle and import parameters for the customs calculation."""

    engine_cc: int
    fuel_type: FuelType | str
    power_hp: int | None
    first_reg_year: int | None
    first_reg_month: int | None
    age_corridor: AgeCorridor | None = None
    is_commercial_util: bool = False
    customs_value_eur: float | None = None
    customs_value_rub: int | None = None
    freight_rub: int | None = None
    broker_rub: int | None = None
    mild_hybrid: bool = False


@dataclass(frozen=True)
class CustomsResult:
    """Full customs and logistics calculation (maps to CustomsCalculation)."""

    age_corridor: AgeCorridor
    duty_calculation_mode: DutyCalculationMode
    engine_cc: int
    duty_rate_eur_per_cc: float | None
    effective_duty_pct: float | None
    customs_duty_eur: float
    customs_duty_rub: int
    is_under_160_hp: bool | None
    is_commercial_util: bool
    utilization_fee_rub: int
    utilization_fee_type: UtilFeeType
    customs_clearance_fee_rub: int
    freight_vladivostok_rub: int
    broker_svh_sbkts_rub: int
    meti_sanction_risk: bool
    excise_rub: int = 0
    import_vat_rub: int = 0


@dataclass(frozen=True)
class WiseCostStepResult:
    """Single expense row of the Wise Cost Ladder."""

    step_number: int
    name_ru: str
    amount_rub: int
    original_currency: str | None
    original_amount: float | None
    is_optional: bool


@dataclass(frozen=True)
class LadderInput:
    """Parameters for assembling the 7-step Wise Cost Ladder.

    ``broker_rub`` overrides the broker/SVH/SBKTS amount carried by
    ``customs`` (falls back to it when None).
    """

    bid_jpy: int
    rates: CurrencyRatesInput
    customs: CustomsResult
    market_price_rf_rub: int
    japan_fob_jpy: int = DEFAULT_JAPAN_FOB_JPY
    broker_rub: int | None = None
    repair_total_rub: int = 0
    include_repairs: bool = True


@dataclass(frozen=True)
class LadderResult:
    """Wise Cost Ladder with the exact-sum guarantee."""

    car_bid_jpy: int
    car_bid_rub: int
    turnkey_cost_rub: int
    market_price_rf_rub: int
    net_benefit_rub: int
    benefit_percentage: float
    steps: list[WiseCostStepResult] = field(default_factory=list)


def resolve_manufacture_date(year: int, month: int | None) -> date:
    """Manufacture date per EAEU rules: 15th if month is known, July 1st otherwise."""
    if month:
        return date(year, month, 15)
    return date(year, 7, 1)


def resolve_age_corridor(
    first_reg_year: int | None,
    first_reg_month: int | None,
    on_date: date,
) -> AgeCorridor:
    """Age corridor relative to the declaration date.

    A car qualifies for the 3-to-5 corridor while it is older than 3 but not
    older than 5 full years; past the 5-year mark the prohibitive rates apply.
    """
    if first_reg_year is None:
        raise ValueError("first_reg_year is required for age corridor resolution")
    manufactured = resolve_manufacture_date(first_reg_year, first_reg_month)

    def shifted_by(threshold_years: int) -> date:
        try:
            return manufactured.replace(year=manufactured.year + threshold_years)
        except ValueError:  # pragma: no cover - Feb 29 manufacture date
            return manufactured.replace(year=manufactured.year + threshold_years, day=28)

    # "3 to 5 years" starts the day the vehicle turns 3 full years old and
    # ends one day after it turns 5 ("5 years and 1 day" is already over 5).
    if on_date > shifted_by(5):
        return AgeCorridor.OVER_5_YEARS
    if on_date >= shifted_by(3):
        return AgeCorridor.THREE_TO_FIVE_YEARS
    return AgeCorridor.UNDER_3_YEARS


def _tier_rate(grid: tuple[tuple[int, float], ...], engine_cc: int) -> float:
    for upper_bound, rate in grid:
        if engine_cc <= upper_bound:
            return rate
    raise ValueError("unreachable duty grid tier")  # pragma: no cover


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
        for upper_bound, pct, min_eur_per_cc in _DUTY_COMBINED_UNDER_3_YEARS:
            if customs_value_eur <= upper_bound:
                ad_valorem = customs_value_eur * pct
                specific = float(engine_cc) * min_eur_per_cc
                duty_eur = round(max(ad_valorem, specific), 2)
                basis = (
                    DutyBasis.AD_VALOREM if ad_valorem >= specific else DutyBasis.SPECIFIC_MINIMUM
                )
                return DutyResult(
                    mode=DutyCalculationMode.PCT_OF_VALUE,
                    rate_eur_per_cc=None,
                    effective_duty_pct=pct * 100,
                    basis=basis,
                    duty_eur=duty_eur,
                    duty_rub=round_eur_to_rub(duty_eur, rates.eur_rub),
                )

    if age_corridor == AgeCorridor.OVER_5_YEARS:
        rate = _tier_rate(_DUTY_EUR_PER_CC_OVER_5_YEARS, engine_cc)
    else:
        rate = _tier_rate(_DUTY_EUR_PER_CC_3_5_YEARS, engine_cc)

    duty_eur = round(float(engine_cc) * rate, 2)
    return DutyResult(
        mode=DutyCalculationMode.EUR_PER_CC,
        rate_eur_per_cc=rate,
        effective_duty_pct=None,
        basis=None,
        duty_eur=duty_eur,
        duty_rub=round_eur_to_rub(duty_eur, rates.eur_rub),
    )


def round_eur_to_rub(amount_eur: float, eur_rub: float) -> int:
    """Convert EUR to integer RUB (half-up, zero-float currency rule)."""
    return math.floor(amount_eur * eur_rub + 0.5)


def meti_sanction_risk(
    fuel_type: FuelType | str,
    engine_cc: int | None,
    *,
    mild_hybrid: bool = False,
) -> bool:
    """METI export restriction: hybrids, EVs and ICE over 1900 cc.

    ``mild_hybrid`` implements the METI MHEV exemption (directive 750 as
    amended 11.2024): a hybrid is directly exportable when the confirmation
    data proves an integrated 12/48V starter-generator, no pure EV traction
    mode and no high-voltage traction battery. The flag must only be set by
    the data source that verified those characteristics (catalog/OCR);
    by default every hybrid is treated as sanctioned.
    """
    fuel = str(fuel_type)
    if fuel == FuelType.EV:
        return True
    if fuel == FuelType.HYBRID:
        return not mild_hybrid
    if fuel in (FuelType.GASOLINE, FuelType.DIESEL):
        return engine_cc is not None and engine_cc > _METI_ICE_MAX_ENGINE_CC
    return False


def is_under_160_hp(power_hp: int | None) -> bool | None:
    """None when power is unknown, so the privilege cannot be confirmed."""
    if power_hp is None:
        return None
    return power_hp <= _UTIL_PRIVILEGED_MAX_HP


def calculate_utilization_fee(
    age_corridor: AgeCorridor,
    engine_cc: int,
    power_hp: int | None,
    fuel_type: FuelType | str,
    is_commercial_util: bool = False,
) -> UtilizationFeeResult:
    """Utilization fee: privileged for individuals <=160 hp, commercial otherwise.

    Decree No. 1713: privileged coefficients (3,400 / 5,200 RUB) are legally
    forbidden when power exceeds 160 hp or is unconfirmed, so the commercial
    grid (Decree No. 1255) applies in that case as well.
    """
    under_160 = is_under_160_hp(power_hp)
    privileged = not is_commercial_util and under_160 is True
    if privileged:
        return UtilizationFeeResult(
            fee_rub=_UTIL_PERSONAL_RUB[age_corridor],
            fee_type=UtilFeeType.PERSONAL,
        )

    is_three_years_or_older = age_corridor != AgeCorridor.UNDER_3_YEARS
    fuel = str(fuel_type)
    if fuel == FuelType.EV:
        fee = _UTIL_COMMERCIAL_EV_2026_RUB[1 if is_three_years_or_older else 0]
    else:
        if engine_cc <= 0:
            raise ValueError("engine_cc must be positive for the utilization fee")
        fee = 0
        for upper_bound, under_3_fee, older_fee in _UTIL_COMMERCIAL_2026_RUB:
            if engine_cc <= upper_bound:
                fee = older_fee if is_three_years_or_older else under_3_fee
                break
    return UtilizationFeeResult(fee_rub=int(fee), fee_type=UtilFeeType.COMMERCIAL)


def calculate_excise(power_hp: int) -> int:
    """Import excise for cars taxed outside the unified EAEU rates (EVs).

    2026 grid per 1 hp by engine power (Tax Code art. 193, Law No. 425-FZ);
    the bracket rate applies to the whole power figure, not just the excess.
    """
    if power_hp < 0:
        raise ValueError("power_hp must not be negative")
    for upper_bound, rate in _EXCISE_2026_RUB_PER_HP:
        if power_hp <= upper_bound:
            return power_hp * rate
    raise ValueError("unreachable excise bracket")  # pragma: no cover


def calculate_clearance_fee(customs_value_rub: int) -> int:
    """Customs clearance fee by declared value (Decree No. 342 grid)."""
    if customs_value_rub < 0:
        raise ValueError("customs_value_rub must not be negative")
    for upper_bound, fee in _CLEARANCE_FEE_GRID_RUB:
        if customs_value_rub <= upper_bound:
            return fee
    raise ValueError("unreachable clearance fee band")  # pragma: no cover


def _validate_rates(rates: CurrencyRatesInput) -> None:
    if rates.jpy_rub <= 0:
        raise ValueError("jpy_rub must be positive")
    if rates.eur_rub <= 0:
        raise ValueError("eur_rub must be positive")
    if rates.usd_rub <= 0:
        raise ValueError("usd_rub must be positive")


def calculate_customs(
    params: CustomsInput,
    rates: CurrencyRatesInput,
    on_date: date,
) -> CustomsResult:
    """Full customs and logistics calculation for a single vehicle."""
    _validate_rates(rates)
    age_corridor = params.age_corridor or resolve_age_corridor(
        params.first_reg_year, params.first_reg_month, on_date
    )

    freight_rub = params.freight_rub
    if freight_rub is None:
        freight_rub = math.floor(DEFAULT_FREIGHT_USD * rates.usd_rub + 0.5)

    if params.customs_value_eur is None:
        if params.customs_value_rub is None:
            raise ValueError("customs_value_eur or customs_value_rub is required for the duty")
        customs_value_eur = round(params.customs_value_rub / rates.eur_rub, 2)
    else:
        customs_value_eur = params.customs_value_eur

    if params.customs_value_rub is None:
        customs_value_rub = math.floor(customs_value_eur * rates.eur_rub + 0.5)
    else:
        customs_value_rub = params.customs_value_rub

    fuel = str(params.fuel_type)
    excise_rub = 0
    import_vat_rub = 0
    if fuel == FuelType.EV:
        # Battery electric vehicles fall outside the unified EEC No. 107
        # rates and pay the aggregate customs payment (research/02, 1.5):
        # duty 15% + excise (Tax Code art. 193, per 1 hp) + VAT.
        if params.power_hp is None:
            raise ValueError("power_hp is required for the EV excise calculation")
        duty_eur = round(customs_value_eur * _EV_DUTY_PCT, 2)
        duty_rub = round_eur_to_rub(duty_eur, rates.eur_rub)
        duty = DutyResult(
            mode=DutyCalculationMode.PCT_OF_VALUE,
            rate_eur_per_cc=None,
            effective_duty_pct=_EV_DUTY_PCT * 100,
            basis=DutyBasis.AD_VALOREM,
            duty_eur=duty_eur,
            duty_rub=duty_rub,
        )
        excise_rub = calculate_excise(params.power_hp)
        import_vat_rub = math.floor(
            (customs_value_rub + duty_rub + excise_rub) * _IMPORT_VAT_PCT + 0.5
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
    """Assemble the 7-step Wise Cost Ladder (Screen 6).

    The turnkey cost is the exact sum of step amounts (invariant:
    ``sum(steps.amount_rub) == turnkey_cost_rub`` to the ruble).
    """
    rates = params.rates
    _validate_rates(rates)
    customs = params.customs

    bid_rub = math.floor(params.bid_jpy * rates.jpy_rub + 0.5)
    fob_rub = math.floor(params.japan_fob_jpy * rates.jpy_rub + 0.5)
    freight_rub = customs.freight_vladivostok_rub
    # Step 4 carries all state import taxes plus the clearance fee so that
    # every mandatory payment lands in the turnkey total (EVs additionally
    # carry the excise and import VAT of the aggregate payment).
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
    duty_step_name = _STEP_DUTY_EV if is_ev_aggregate else _STEP_DUTY
    duty_original_currency = None if is_ev_aggregate else "EUR"
    duty_original_amount = None if is_ev_aggregate else customs.customs_duty_eur

    steps = [
        WiseCostStepResult(1, _STEP_BID, bid_rub, "JPY", float(params.bid_jpy), False),
        WiseCostStepResult(2, _STEP_JAPAN, fob_rub, "JPY", float(params.japan_fob_jpy), False),
        WiseCostStepResult(
            3,
            _STEP_FREIGHT,
            freight_rub,
            "USD",
            round(freight_rub / rates.usd_rub, 2),
            False,
        ),
        WiseCostStepResult(
            4,
            duty_step_name,
            duty_step_rub,
            duty_original_currency,
            duty_original_amount,
            False,
        ),
        WiseCostStepResult(5, _STEP_UTIL, util_rub, "RUB", float(util_rub), False),
        WiseCostStepResult(6, _STEP_BROKER, broker_rub, "RUB", float(broker_rub), False),
    ]
    # Step 7 is always present (is_optional): it is zeroed out when the
    # repair estimate is excluded, matching the 7-row domain ladder layout.
    steps.append(WiseCostStepResult(7, _STEP_REPAIR, repair_rub, "RUB", float(repair_rub), True))

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


# --- Start bid derivation (reverse calculation from the RF market price) ---

# Target margin of the reverse calculation: the start bid must leave at least
# 15% of the Drom market price as the buyer's net benefit.
DEFAULT_TARGET_MARGIN_PCT = 15.0

# Slider step from the API contract (EconomicsDetail.bid_slider_step_jpy).
DEFAULT_BID_STEP_JPY = 10_000


@dataclass(frozen=True)
class StartBidInput:
    """Parameters for deriving a new lot's start bid from the market price."""

    market_price_rf_rub: int
    rates: CurrencyRatesInput
    on_date: date
    customs_params: CustomsInput
    japan_fob_jpy: int = DEFAULT_JAPAN_FOB_JPY
    broker_rub: int | None = None
    repair_total_rub: int = 0
    include_repairs: bool = True
    target_margin_pct: float = DEFAULT_TARGET_MARGIN_PCT
    step_jpy: int = DEFAULT_BID_STEP_JPY
    min_bid_jpy: int = 300_000
    max_bid_jpy: int = 2_500_000


@dataclass(frozen=True)
class StartBidResult:
    """Derived start bid with the numbers it was based on."""

    bid_jpy: int
    source: str
    target_turnkey_rub: int
    achieved_turnkey_rub: int
    achieved_net_benefit_rub: int
    clamped: bool


def _turnkey_for_bid(
    bid_jpy: int,
    params: StartBidInput,
    fob_rub: int,
    freight_rub: int,
) -> int:
    """Full turnkey cost for a candidate bid (engine grids, exact-sum ladder)."""
    bid_rub = math.floor(bid_jpy * params.rates.jpy_rub + 0.5)
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
    """Reverse-calculate the start bid from the Drom market price.

    Finds the highest slider-grid bid whose turnkey cost still leaves at
    least ``target_margin_pct`` of the market price as net benefit. Grid
    candidates are ``min_bid_jpy + k * step_jpy`` (the actual slider
    positions), scanned from the top down. A descending scan is used
    instead of a binary search because the turnkey cost is NOT strictly
    monotonic in the bid: crossing a combined-duty value bracket (under-3
    corridor, e.g. 54% -> 48% at 8,500 EUR) can lower the duty when the bid
    grows, so a binary search may stop on a suboptimal bid.
    """
    if params.min_bid_jpy > params.max_bid_jpy:
        raise ValueError("min_bid_jpy must not exceed max_bid_jpy")
    if params.step_jpy <= 0:
        raise ValueError("step_jpy must be positive")
    if params.market_price_rf_rub < 0:
        raise ValueError("market_price_rf_rub must not be negative")

    rates = params.rates
    _validate_rates(rates)
    fob_rub = math.floor(params.japan_fob_jpy * rates.jpy_rub + 0.5)
    freight_rub = params.customs_params.freight_rub
    if freight_rub is None:
        freight_rub = math.floor(DEFAULT_FREIGHT_USD * rates.usd_rub + 0.5)

    target_turnkey_rub = math.floor(
        params.market_price_rf_rub * (1 - Decimal(str(params.target_margin_pct)) / 100)
    )

    def turnkey_for(bid_jpy: int) -> int:
        return _turnkey_for_bid(bid_jpy, params, fob_rub, freight_rub)

    def result_for(bid_jpy: int, *, clamped: bool) -> StartBidResult:
        achieved = turnkey_for(bid_jpy)
        return StartBidResult(
            bid_jpy=bid_jpy,
            source="reverse_from_market",
            target_turnkey_rub=target_turnkey_rub,
            achieved_turnkey_rub=achieved,
            achieved_net_benefit_rub=params.market_price_rf_rub - achieved,
            clamped=clamped,
        )

    # Slider grid candidates, from the highest position down to the minimum.
    step_count = (params.max_bid_jpy - params.min_bid_jpy) // params.step_jpy
    for index in range(step_count, -1, -1):
        candidate = params.min_bid_jpy + index * params.step_jpy
        if turnkey_for(candidate) <= target_turnkey_rub:
            return result_for(candidate, clamped=False)

    # No slider position keeps the target margin: clamp to the lowest
    # available bid and report the shortfall.
    return result_for(params.min_bid_jpy, clamped=True)
