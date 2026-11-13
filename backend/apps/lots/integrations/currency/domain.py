"""Domain types and normalization for the CBRF currency rates gateway."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

_RATE_QUANT = Decimal("0.0001")


class RatesOrigin(StrEnum):
    LIVE = "live"
    CACHE = "cache"
    STALE = "stale"
    CONFIG = "config"


@dataclass(frozen=True)
class BaseRates:
    """Normalized CBRF rates in rubles per one unit of each currency."""

    eur_rub: float
    usd_rub: float
    jpy_rub: float
    cbrf_date: str  # DD.MM.YYYY as published by the source


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


def round_rate(value: Decimal) -> Decimal:
    """Round a rate to four decimal places, half up."""
    return value.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


def normalize_unit_rate(value: Decimal, nominal: Decimal) -> Decimal:
    """Convert a CBRF `Value / Nominal` quote into rubles per one unit."""
    return round_rate(value / nominal)


def compute_commercial_jpy(base_jpy_rub: Decimal, spread: Decimal) -> Decimal:
    """Apply the Far East commercial spread on top of the CBRF JPY rate."""
    return round_rate(base_jpy_rub * (Decimal(1) + spread))


def parse_positive_rate(raw: object) -> Decimal:
    """Validate a finite positive rate representable at the supported precision."""
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or value <= 0 or round_rate(value) <= 0:
            raise ValueError("Currency rates must be finite and positive")
        return value
    except InvalidOperation as exc:
        raise ValueError("Invalid currency rate") from exc


def validate_rate_date(value: str) -> str:
    """Require an actual date in the public DD.MM.YYYY format."""
    if datetime.strptime(value, "%d.%m.%Y").strftime("%d.%m.%Y") != value:
        raise ValueError("Currency rate date must use DD.MM.YYYY")
    return value


def parse_fallback_config(raw: dict[str, str | float] | None) -> BaseRates | None:
    """Validate the complete reserve set independently of Django initialization."""
    if raw is None:
        return None
    try:
        return BaseRates(
            eur_rub=float(parse_positive_rate(raw["eur_rub"])),
            usd_rub=float(parse_positive_rate(raw["usd_rub"])),
            jpy_rub=float(parse_positive_rate(raw["jpy_rub"])),
            cbrf_date=validate_rate_date(str(raw["cbrf_date"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "CBRF_FALLBACK_RATES must contain positive finite rates and a valid date"
        ) from exc


JPY_RATE_SOURCE_TEMPLATE = "Расчётный ориентир: ЦБ РФ + {pct}%"
