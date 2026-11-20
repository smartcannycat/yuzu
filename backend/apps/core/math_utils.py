"""Exact decimal rounding utilities."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal


def to_decimal(value: Decimal | int | float) -> Decimal:
    """Convert a finite numeric value into an exact ``Decimal`` instance."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Decimal value must be finite")
        return value
    if isinstance(value, bool):
        raise TypeError("Boolean value is not supported")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Float value must be finite")
        return Decimal(str(value))
    raise TypeError(f"Unsupported numeric type: {type(value).__name__}")


def round_half_up_int(
    value: Decimal | int | float,
    multiplier: Decimal | int | float | None = None,
) -> int:
    """Round ``value`` (or ``value * multiplier``) to integer using ``ROUND_HALF_UP``."""
    dec = to_decimal(value)
    if multiplier is not None:
        dec = dec * to_decimal(multiplier)
    return int(dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
