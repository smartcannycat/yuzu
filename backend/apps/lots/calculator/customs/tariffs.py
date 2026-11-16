"""Customs tariff grids, normative constants, and calculation dataclasses (BE-09)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from apps.core.enums import (
    AgeCorridor,
    DutyCalculationMode,
    FuelType,
    UtilFeeType,
)

if TYPE_CHECKING:
    from datetime import date

# Sentinel upper bounds for the last (unbounded) tier of each grid.
_UNBOUNDED_CC = 10**9
_UNBOUNDED_HP = 10**6
_UNBOUNDED_VALUE_EUR = 10**9
_UNBOUNDED_VALUE_RUB = 10**11

# Engine-specific constant defaults aligned with the benchmark case.
DEFAULT_JAPAN_FOB_JPY = 95_000
DEFAULT_FREIGHT_USD = 1_150
DEFAULT_BROKER_SVH_SBKTS_RUB = 99_000

# EAEU unified duty per cc (EUR) for the 3-to-5-years corridor.
DUTY_EUR_PER_CC_3_5_YEARS: tuple[tuple[int, float], ...] = (
    (1_000, 1.5),
    (1_500, 1.7),
    (1_800, 2.5),
    (2_300, 2.7),
    (3_000, 3.0),
    (_UNBOUNDED_CC, 3.6),
)

# EAEU unified duty per cc (EUR) for the over-5-years corridor.
DUTY_EUR_PER_CC_OVER_5_YEARS: tuple[tuple[int, float], ...] = (
    (1_000, 3.0),
    (1_500, 3.2),
    (1_800, 3.5),
    (2_300, 4.8),
    (3_000, 5.0),
    (_UNBOUNDED_CC, 5.7),
)

# Combined duty for under-3-years corridor: (upper EUR bound, pct, min EUR/cc).
DUTY_COMBINED_UNDER_3_YEARS: tuple[tuple[int, float, float], ...] = (
    (8_500, 0.54, 2.5),
    (16_700, 0.48, 3.5),
    (42_300, 0.48, 5.5),
    (84_500, 0.48, 7.5),
    (169_000, 0.48, 15.0),
    (_UNBOUNDED_VALUE_EUR, 0.48, 20.0),
)

# Customs clearance fee grid (Government Decree No. 342).
CLEARANCE_FEE_GRID_RUB: tuple[tuple[int, int], ...] = (
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

# Personal (privileged) utilization fee for individuals (Decree No. 1713, <= 160 hp).
UTIL_PERSONAL_RUB = {
    AgeCorridor.UNDER_3_YEARS: 3_400,
    AgeCorridor.THREE_TO_FIVE_YEARS: 5_200,
    AgeCorridor.OVER_5_YEARS: 5_200,
}

# Commercial utilization fee grid, 2026 rates (Decree No. 1255).
UTIL_COMMERCIAL_2026_RUB: tuple[tuple[int, int, int], ...] = (
    (1_000, 216_200, 557_800),
    (2_000, 800_800, 1_408_800),
    (3_000, 2_250_400, 2_840_400),
    (3_500, 2_576_600, 3_287_800),
    (_UNBOUNDED_CC, 3_290_600, 3_848_400),
)

UTIL_COMMERCIAL_EV_2026_RUB = (800_800, 1_408_800)
METI_ICE_MAX_ENGINE_CC = 1_900
EV_DUTY_PCT = 0.15

# Import excise on passenger cars by engine power, 2026 rates per 1 hp.
EXCISE_2026_RUB_PER_HP: tuple[tuple[int, int], ...] = (
    (90, 0),
    (150, 64),
    (200, 613),
    (300, 1_004),
    (400, 1_711),
    (500, 1_771),
    (_UNBOUNDED_HP, 1_829),
)

IMPORT_VAT_PCT = 0.22
UTIL_PRIVILEGED_MAX_HP = 160

# Canonical Wise Cost Ladder step names.
STEP_BID = "Ставка на аукционе"
STEP_JAPAN = "Расходы в Японии (FOB и сбор)"
STEP_FREIGHT = "Фрахт Тояма-ВЛК"
STEP_DUTY = "Таможенная пошлина ЕАЭС и сбор"
STEP_DUTY_EV = "Таможня ЕАЭС (пошлина, акциз, НДС, сбор)"
STEP_UTIL = "Утилизационный сбор РФ"
STEP_BROKER = "СВХ, брокер, СБКТС, ЭПТС"
STEP_REPAIR = "Запчасти Farpost и ремонт"


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
    """Parameters for assembling the 7-step Wise Cost Ladder."""

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
    target_margin_pct: float = 15.0
    step_jpy: int = 10_000
    min_bid_jpy: int = 100_000
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


def validate_rates(rates: CurrencyRatesInput) -> None:
    if rates.jpy_rub <= 0:
        raise ValueError("jpy_rub must be positive")
    if rates.eur_rub <= 0:
        raise ValueError("eur_rub must be positive")
    if rates.usd_rub <= 0:
        raise ValueError("usd_rub must be positive")
