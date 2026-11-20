"""Pure currency fallback validation and rate-rounding helpers shared across core/config."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_RATE_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class BaseRates:
    """Normalized CBRF rates in rubles per one unit of each currency."""

    eur_rub: float
    usd_rub: float
    jpy_rub: float
    cbrf_date: str  # DD.MM.YYYY as published by the source


def round_rate(value: Decimal) -> Decimal:
    """Round a rate to four decimal places, half up."""
    return value.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


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
