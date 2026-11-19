"""Domain types and normalization for the CBRF currency rates gateway."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from apps.core.currency_config import (
    BaseRates,
    parse_fallback_config,
    parse_positive_rate,
    round_rate,
    validate_rate_date,
)
from apps.core.schemas import StrictBaseModel


class RatesOrigin(StrEnum):
    LIVE = "live"
    CACHE = "cache"
    STALE = "stale"
    CONFIG = "config"


@dataclass(frozen=True)
class CurrencyRatesResult:
    """Resolved rates with provenance metadata for a single calculation."""

    base: BaseRates
    commercial_jpy_rub: float
    jpy_rate_source: str
    origin: RatesOrigin
    fetched_at: datetime
    is_fallback: bool
    fallback_reason: str | None = None

    @property
    def eur_rub(self) -> float:
        return self.base.eur_rub

    @property
    def usd_rub(self) -> float:
        return self.base.usd_rub

    @property
    def jpy_rub(self) -> float:
        return self.base.jpy_rub

    @property
    def cbrf_date(self) -> str:
        return self.base.cbrf_date


def normalize_unit_rate(value: Decimal, nominal: Decimal) -> Decimal:
    """Convert a CBRF `Value / Nominal` quote into rubles per one unit."""
    return round_rate(value / nominal)


def compute_commercial_jpy(base_jpy_rub: Decimal, spread: Decimal) -> Decimal:
    """Apply the Far East commercial spread on top of the CBRF JPY rate."""
    return round_rate(base_jpy_rub * (Decimal(1) + spread))


__all__ = [
    "JPY_RATE_SOURCE_TEMPLATE",
    "BaseRates",
    "CurrencyRates",
    "CurrencyRatesResult",
    "RatesOrigin",
    "compute_commercial_jpy",
    "normalize_unit_rate",
    "parse_fallback_config",
    "parse_positive_rate",
    "round_rate",
    "validate_rate_date",
]


JPY_RATE_SOURCE_TEMPLATE = "Расчётный ориентир: ЦБ РФ + {pct}%"


class CurrencyRates(StrictBaseModel):
    """Public snapshot contract for resolved CBRF / commercial JPY rates."""

    jpy_rub_bank: float = Field(..., description="Commercial JPY/RUB rate (Far East bank)")
    jpy_rate_source: str = Field("ДВ-банк (ориентир)", description="Source of JPY/RUB rate")
    eur_rub_cbrf: float = Field(..., description="Official EUR/RUB rate from CBRF")
    usd_rub_cbrf: float = Field(..., description="Official USD/RUB rate from CBRF")
    cbrf_date: str = Field(..., description="CBRF rate fixation date (DD.MM.YYYY)")
