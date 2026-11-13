import re
import statistics
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from apps.lots.integrations.drom.schemas import DromListing, DromSearchCriteria

_MAX_URL_LENGTH = 500

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

_FOREIGN_LOCATION_RE = re.compile(r"\b(?:япония|китай|корея)\b", re.IGNORECASE)

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
    if region_scope == "dfo":
        base = f"https://auto.drom.ru/region25/{safe_make}/{safe_model}/bez-probega/"
    else:
        base = f"https://auto.drom.ru/{safe_make}/{safe_model}/bez-probega/"

    params: list[tuple[str, str]] = [
        ("unsold", "1"),
        ("damaged", "2"),
        ("whereabouts[]", "0"),
    ]

    if criteria.year is not None:
        min_year = criteria.year - year_tolerance
        max_year = criteria.year + year_tolerance
        params.append(("minyear", str(min_year)))
        params.append(("maxyear", str(max_year)))

    if criteria.engine_cc and criteria.engine_cc > 0:
        liters = criteria.engine_cc / 1000.0
        delta = 0.2 if relax_specs else 0.1
        min_v = max(0.6, round(liters - delta, 1))
        max_v = round(liters + delta, 1)
        params.append(("mv", f"{min_v:.1f}"))
        params.append(("xv", f"{max_v:.1f}"))

    if frame_type_id is not None and not relax_specs:
        params.append(("frametype[]", str(frame_type_id)))

    if not relax_specs:
        if criteria.drive_type == "4WD":
            params.append(("privod[]", "3"))
        if is_manual_transmission(criteria.transmission):
            params.append(("transmission[]", "1"))

    url = f"{base}?{urlencode(params)}"
    if len(url) <= _MAX_URL_LENGTH:
        return url

    # Keep query parameters intact while bounding slug segments to DB URLField(max_length=500).
    query = urlencode(params)
    prefix = "https://auto.drom.ru/region25/" if region_scope == "dfo" else "https://auto.drom.ru/"
    suffix = f"/bez-probega/?{query}"
    available = max(2, _MAX_URL_LENGTH - len(prefix) - len(suffix) - 1)
    half = max(1, available // 2)
    bounded_make = safe_make[:half]
    bounded_model = safe_model[: available - len(bounded_make)]
    return f"{prefix}{bounded_make}/{bounded_model}{suffix}"[:_MAX_URL_LENGTH]


def is_under_order_or_unavailable(listing: DromListing) -> bool:
    """Return True if a Drom listing is sold, on order, in transit, or non-standard."""
    if listing.sold:
        return True
    if listing.location and _FOREIGN_LOCATION_RE.search(listing.location):
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


def filter_and_aggregate(listings: list[DromListing]) -> FilteredMarketStats | None:
    """Filter under-order listings and price outliers, returning median/min/max stats."""
    in_stock: list[DromListing] = []
    rejected_count = 0

    for listing in listings:
        if listing.price_rub <= 0:
            continue
        if is_under_order_or_unavailable(listing):
            rejected_count += 1
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
