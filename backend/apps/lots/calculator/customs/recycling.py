"""Age corridor, METI sanctions, utilization fee, and excise calculations."""

from __future__ import annotations

from datetime import date

from apps.core.enums import AgeCorridor, FuelType, UtilFeeType
from apps.lots.calculator.customs.tariffs import (
    EXCISE_2026_RUB_PER_HP,
    METI_ICE_MAX_ENGINE_CC,
    UTIL_COMMERCIAL_2026_RUB,
    UTIL_COMMERCIAL_EV_2026_RUB,
    UTIL_PERSONAL_RUB,
    UTIL_PRIVILEGED_MAX_HP,
    UtilizationFeeResult,
)


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
    """Age corridor relative to the declaration date."""
    if first_reg_year is None:
        raise ValueError("first_reg_year is required for age corridor resolution")
    manufactured = resolve_manufacture_date(first_reg_year, first_reg_month)

    def shifted_by(threshold_years: int) -> date:
        try:
            return manufactured.replace(year=manufactured.year + threshold_years)
        except ValueError:  # pragma: no cover - Feb 29 manufacture date
            return manufactured.replace(year=manufactured.year + threshold_years, day=28)

    # "3 to 5 years" ends one day after turning 5 ("5 years and 1 day" is over 5).
    if on_date > shifted_by(5):
        return AgeCorridor.OVER_5_YEARS
    if on_date >= shifted_by(3):
        return AgeCorridor.THREE_TO_FIVE_YEARS
    return AgeCorridor.UNDER_3_YEARS


def meti_sanction_risk(
    fuel_type: FuelType | str,
    engine_cc: int | None,
    *,
    mild_hybrid: bool = False,
) -> bool:
    """METI export restriction: hybrids, EVs and ICE over 1900 cc."""
    fuel = str(fuel_type or "")
    if fuel == FuelType.EV:
        return True
    if fuel == FuelType.HYBRID:
        return not mild_hybrid
    return engine_cc is not None and engine_cc > METI_ICE_MAX_ENGINE_CC


def is_under_160_hp(power_hp: int | None) -> bool | None:
    """None when power is unknown, so the privilege cannot be confirmed."""
    if power_hp is None:
        return None
    return power_hp <= UTIL_PRIVILEGED_MAX_HP


def calculate_utilization_fee(
    age_corridor: AgeCorridor,
    engine_cc: int,
    power_hp: int | None,
    fuel_type: FuelType | str,
    is_commercial_util: bool = False,
) -> UtilizationFeeResult:
    """Utilization fee: privileged for individuals <=160 hp, commercial otherwise."""
    under_160 = is_under_160_hp(power_hp)
    privileged = not is_commercial_util and under_160 is True
    if privileged:
        return UtilizationFeeResult(
            fee_rub=UTIL_PERSONAL_RUB[age_corridor],
            fee_type=UtilFeeType.PERSONAL,
        )

    is_three_years_or_older = age_corridor != AgeCorridor.UNDER_3_YEARS
    fuel = str(fuel_type)
    if fuel == FuelType.EV:
        fee = UTIL_COMMERCIAL_EV_2026_RUB[1 if is_three_years_or_older else 0]
    else:
        if engine_cc <= 0:
            raise ValueError("engine_cc must be positive for the utilization fee")
        fee = 0
        for upper_bound, under_3_fee, older_fee in UTIL_COMMERCIAL_2026_RUB:
            if engine_cc <= upper_bound:
                fee = older_fee if is_three_years_or_older else under_3_fee
                break
    return UtilizationFeeResult(fee_rub=int(fee), fee_type=UtilFeeType.COMMERCIAL)


def calculate_excise(power_hp: int) -> int:
    """Import excise for cars taxed outside the unified EAEU rates (EVs)."""
    if power_hp < 0:
        raise ValueError("power_hp must not be negative")
    for upper_bound, rate in EXCISE_2026_RUB_PER_HP:
        if power_hp <= upper_bound:
            return power_hp * rate
    raise ValueError("unreachable excise bracket")  # pragma: no cover
