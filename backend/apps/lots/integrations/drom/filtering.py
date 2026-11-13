import json
import re
import statistics
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlencode

from apps.lots.integrations.drom.schemas import DromListing, DromSearchCriteria

_MAX_URL_LENGTH = 500
_SCHEMA_PATH = Path(__file__).resolve().parent / "data" / "drom_schema.json"
_DEFAULT_DRIVE_UNITS: dict[str, str] = {"4WD": "3", "FWD": "1", "RWD": "2"}
_DEFAULT_FUEL_TYPES: dict[str, str] = {
    "gasoline": "1",
    "diesel": "2",
    "ev": "4",
    "hybrid": "5",
}


@lru_cache(maxsize=1)
def _load_filter_schema() -> dict[str, dict[str, str]]:
    if _SCHEMA_PATH.exists():
        try:
            payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            schema = payload.get("filter_schema") or {}
            if isinstance(schema, dict):
                return {
                    "drive_units": dict(schema.get("drive_units") or _DEFAULT_DRIVE_UNITS),
                    "fuel_types": dict(schema.get("fuel_types") or _DEFAULT_FUEL_TYPES),
                }
        except (OSError, ValueError):
            pass
    return {"drive_units": dict(_DEFAULT_DRIVE_UNITS), "fuel_types": dict(_DEFAULT_FUEL_TYPES)}


_ORDER_STOP_PHRASES: tuple[str, ...] = (
    "под заказ",
    "на заказ",
    "под привоз",
    "в пути",
    "привезем",
    "привезём",
    "под полную пошлину из",
    "под птс",
    "в наличии в китае",
    "в наличии в японии",
    "в наличии в корее",
)

_NEGATIVE_VEHICLE_TYPE_RE = re.compile(
    r"(?<![а-яё])(?<!не\s)(?:конструктор|распил)(?![а-яё])",
    re.IGNORECASE,
)

_FOREIGN_LOCATION_RE = re.compile(
    r"\b(?:япония|японии|китай|китая|корея|кореи)\b",
    re.IGNORECASE,
)

_MANUAL_TRANSMISSION_RE = re.compile(
    r"(?:^|[\d\s/\-_])(?:mt|мт|мкпп|manual|мех(?:аника)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FilteredMarketStats:
    market_price_rf_rub: int
    analogs_count: int
    price_min_rub: int
    price_max_rub: int
    filtered_out_under_order_count: int


def compute_engine_volume_bounds(engine_cc: int, *, delta: float = 0.1) -> tuple[float, float]:
    """Convert engine displacement in cc into Drom (min_liters, max_liters) filter bounds."""
    liters = engine_cc / 1000.0
    min_v = max(0.6, round(liters - delta, 1))
    max_v = round(liters + delta, 1)
    return min_v, max_v


def _build_search_query_params(
    criteria: DromSearchCriteria,
    *,
    frame_type_id: int | None,
    year_tolerance: int,
    relax_specs: bool,
) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [
        ("unsold", "1"),
        ("damaged", "2"),
        ("whereabouts[]", "0"),
    ]

    if criteria.year is not None:
        params.append(("minyear", str(criteria.year - year_tolerance)))
        params.append(("maxyear", str(criteria.year + year_tolerance)))

    if criteria.engine_cc and criteria.engine_cc > 0:
        delta = 0.2 if relax_specs else 0.1
        min_v, max_v = compute_engine_volume_bounds(criteria.engine_cc, delta=delta)
        params.append(("mv", f"{min_v:.1f}"))
        params.append(("xv", f"{max_v:.1f}"))

    if relax_specs:
        return params

    if frame_type_id is not None:
        params.append(("frametype[]", str(frame_type_id)))

    filter_schema = _load_filter_schema()
    if criteria.drive_type == "4WD":
        params.append(("privod[]", filter_schema["drive_units"].get("4WD", "3")))
    if criteria.fuel_type:
        fuel_code = filter_schema["fuel_types"].get(criteria.fuel_type.strip().lower())
        if fuel_code:
            params.append(("fueltype", fuel_code))
    if is_manual_transmission(criteria.transmission):
        params.append(("transmission[]", "1"))

    return params


def _truncate_drom_url(
    prefix: str,
    safe_make: str,
    safe_model: str,
    query: str,
) -> str:
    # Keep query parameters intact while bounding slug segments to DB URLField(max_length=500).
    suffix = f"/bez-probega/?{query}"
    available = max(2, _MAX_URL_LENGTH - len(prefix) - len(suffix) - 1)
    half = max(1, available // 2)
    bounded_make = safe_make[:half]
    bounded_model = safe_model[: available - len(bounded_make)]
    return f"{prefix}{bounded_make}/{bounded_model}{suffix}"[:_MAX_URL_LENGTH]


def build_drom_search_url(
    criteria: DromSearchCriteria,
    *,
    make_slug: str,
    model_slug: str,
    frame_type_id: int | None = None,
    region_scope: str = "dfo",
    year_tolerance: int = 0,
    relax_specs: bool = False,
) -> str:
    """Build a Drom search URL filtered for unsold, undamaged, in-stock, non-RF-mileage cars."""
    safe_make = quote(make_slug.strip("/"), safe="-_")
    safe_model = quote(model_slug.strip("/"), safe="-_")
    prefix = "https://auto.drom.ru/region25/" if region_scope == "dfo" else "https://auto.drom.ru/"
    params = _build_search_query_params(
        criteria,
        frame_type_id=frame_type_id,
        year_tolerance=year_tolerance,
        relax_specs=relax_specs,
    )
    query = urlencode(params)
    url = f"{prefix}{safe_make}/{safe_model}/bez-probega/?{query}"
    if len(url) <= _MAX_URL_LENGTH:
        return url
    return _truncate_drom_url(prefix, safe_make, safe_model, query)


def is_under_order_or_unavailable(listing: DromListing) -> bool:
    """Return True if a Drom listing is sold, on order, in transit, or non-standard."""
    if listing.sold:
        return True
    meta_text = " ".join(
        part for part in [listing.location, *listing.car_state, *listing.badges] if part
    )
    if meta_text and _FOREIGN_LOCATION_RE.search(meta_text):
        return True

    combined_parts = [
        listing.title,
        listing.description,
        *listing.car_state,
        *listing.badges,
        *listing.attributes,
    ]
    haystack = " ".join(part for part in combined_parts if part).lower()
    if any(phrase in haystack for phrase in _ORDER_STOP_PHRASES):
        return True
    return bool(_NEGATIVE_VEHICLE_TYPE_RE.search(haystack))


def filter_and_aggregate(
    listings: list[DromListing],
    *,
    exclude_nearby_cities: bool = False,
) -> FilteredMarketStats | None:
    """Filter under-order listings and price outliers, returning median/min/max stats."""
    in_stock: list[DromListing] = []
    rejected_count = 0

    for listing in listings:
        if listing.price_rub <= 0:
            continue
        if is_under_order_or_unavailable(listing):
            rejected_count += 1
            continue
        if exclude_nearby_cities and listing.is_nearby_city:
            continue
        in_stock.append(listing)

    if not in_stock:
        return None

    prices = sorted(item.price_rub for item in in_stock)
    clean_prices, outlier_count = _remove_price_outliers(prices)
    rejected_count += outlier_count

    return FilteredMarketStats(
        market_price_rf_rub=round(statistics.median(clean_prices)),
        analogs_count=len(clean_prices),
        price_min_rub=min(clean_prices),
        price_max_rub=max(clean_prices),
        filtered_out_under_order_count=rejected_count,
    )


def _remove_price_outliers(sorted_prices: list[int]) -> tuple[list[int], int]:
    if len(sorted_prices) < 4:
        return sorted_prices, 0

    prelim_median = statistics.median(sorted_prices)
    decoy_floor = prelim_median * 0.55

    q1, _, q3 = statistics.quantiles(sorted_prices, n=4, method="inclusive")
    iqr = q3 - q1
    if iqr > 0:
        lower_fence = max(decoy_floor, q1 - 1.5 * iqr)
        upper_fence = q3 + 1.5 * iqr
    else:
        lower_fence = decoy_floor
        upper_fence = prelim_median * 2.5

    kept = [p for p in sorted_prices if lower_fence <= p <= upper_fence]
    if not kept:
        return sorted_prices, 0
    return kept, len(sorted_prices) - len(kept)


def is_manual_transmission(transmission: str | None) -> bool:
    """Return True for manual transmission markers (6MT, manual gearbox), excluding AMT/CVT/AT."""
    if not transmission:
        return False
    cleaned = transmission.strip()
    if "amt" in cleaned.lower() or "амт" in cleaned.lower():
        return False
    return bool(_MANUAL_TRANSMISSION_RE.search(cleaned))
