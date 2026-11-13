import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from apps.lots.integrations.drom.html_utils import extract_bulls_list_ssr_payload
from apps.lots.integrations.drom.schemas import DromListing

_TRAILING_DECIMAL_RE = re.compile(r"[.,]\d{1,2}\s*(?:₽|руб\.?)?\s*$", re.IGNORECASE)
_PRICE_DIGITS_RE = re.compile(r"\d+")
_GROUP_ORDER_MARKERS = ("под заказ", "на заказ", "в пути")
_HTML_CAR_STATE_MARKERS = ("под заказ", "в пути")


def parse_listings(html: str) -> list[DromListing]:
    """Extract Drom listings from embedded SSR JSON, falling back to DOM parsing."""
    listings = _parse_listings_from_json(html)
    if listings is not None:
        return listings
    return _parse_listings_from_html(html)


def _parse_listings_from_json(html: str) -> list[DromListing] | None:
    payload = extract_bulls_list_ssr_payload(html)
    if payload is None:
        return None
    bull_list = payload.get("bullList")
    if not isinstance(bull_list, dict):
        return None
    bulls_data = bull_list.get("bullsData")
    if not isinstance(bulls_data, list):
        return None
    return _extract_bulls_from_groups(bulls_data)


def _extract_bulls_from_groups(groups: list[Any]) -> list[DromListing]:
    results: list[DromListing] = []
    seen_ids: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_title = str(group.get("title") or "").strip()
        is_nearby_city = "ближайших городах" in group_title.lower()
        bulls = group.get("bulls")
        if not isinstance(bulls, list):
            continue
        for raw in bulls:
            if not isinstance(raw, dict):
                continue
            listing = _raw_bull_to_listing(
                raw,
                group_title=group_title,
                is_nearby_city=is_nearby_city,
            )
            if listing is None:
                continue
            if listing.bull_id and listing.bull_id in seen_ids:
                continue
            if listing.bull_id:
                seen_ids.add(listing.bull_id)
            results.append(listing)
    return results


def _extract_listing_attributes(raw: dict[str, Any]) -> list[str]:
    attributes: list[str] = []
    for attr in raw.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        val = attr.get("payload")
        if isinstance(val, str):
            attributes.append(val)
        elif isinstance(val, dict) and isinstance(val.get("text"), str):
            attributes.append(val["text"])
    return attributes


def _extract_car_state(raw: dict[str, Any]) -> list[str]:
    raw_car_state = raw.get("carState")
    if isinstance(raw_car_state, list):
        return [str(item) for item in raw_car_state if item is not None and str(item).strip()]
    if isinstance(raw_car_state, str) and raw_car_state.strip():
        return [raw_car_state.strip()]
    return []


def _extract_listing_badges(raw: dict[str, Any], group_title: str) -> list[str]:
    badges: list[str] = []
    if raw.get("info"):
        badges.append(str(raw["info"]))
    if group_title and any(marker in group_title.lower() for marker in _GROUP_ORDER_MARKERS):
        badges.append(group_title)
    if raw.get("locationFrom"):
        badges.append(str(raw["locationFrom"]))
    for mark in raw.get("marks") or []:
        if isinstance(mark, dict) and mark.get("locationCountryFrom"):
            badges.append(str(mark["locationCountryFrom"]))
    return badges


def _raw_bull_to_listing(
    raw: dict[str, Any],
    *,
    group_title: str = "",
    is_nearby_city: bool = False,
) -> DromListing | None:
    price = _parse_int(raw.get("price"))
    if price is None or price <= 0:
        return None
    bull_id = str(raw["bullId"]) if raw.get("bullId") is not None else None
    return DromListing(
        bull_id=bull_id,
        title=str(raw.get("title") or "").strip(),
        price_rub=price,
        url=str(raw["url"]) if raw.get("url") else None,
        description=str(raw.get("description") or "").strip(),
        location=str(raw.get("location") or "").strip(),
        sold=bool(raw.get("sold", False)),
        car_state=_extract_car_state(raw),
        attributes=_extract_listing_attributes(raw),
        badges=_extract_listing_badges(raw, group_title),
        is_nearby_city=is_nearby_city,
    )


def _parse_listings_from_html(html: str) -> list[DromListing]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[DromListing] = []
    for card in soup.find_all(attrs={"data-ftid": "bulls-list_bull"}):
        listing = _card_to_listing(card)
        if listing is not None:
            results.append(listing)
    return results


def _card_to_listing(card: Tag) -> DromListing | None:
    price_el = card.find(attrs={"data-ftid": "bull_price"})
    if price_el is None:
        return None
    price = _parse_int(price_el.get_text(" ", strip=True))
    if price is None or price <= 0:
        return None
    title_el = card.find(attrs={"data-ftid": "bull_title"})
    title = title_el.get_text(" ", strip=True) if title_el else ""
    link_el = (title_el.find("a", href=True) if title_el else None) or card.find("a", href=True)
    url = str(link_el["href"]) if link_el and link_el.has_attr("href") else None
    location_el = card.find(attrs={"data-ftid": "bull_location"})
    location = location_el.get_text(" ", strip=True) if location_el else ""
    attrs = [
        el.get_text(" ", strip=True)
        for el in card.find_all(attrs={"data-ftid": "bull_description-item"})
    ]
    card_text = card.get_text(" ", strip=True)
    card_lower = card_text.lower()
    sold = "снято с продажи" in card_lower or "продано" in card_lower
    car_state = [marker for marker in _HTML_CAR_STATE_MARKERS if marker in card_lower]
    return DromListing(
        bull_id=None,
        title=title,
        price_rub=price,
        url=url,
        description=card_text,
        location=location,
        sold=sold,
        car_state=car_state,
        attributes=attrs,
        badges=[],
    )


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.startswith("-"):
            return None
        cleaned = _TRAILING_DECIMAL_RE.sub("", stripped)
        if re.search(r"[-–—]", cleaned):
            return None
        digits = "".join(_PRICE_DIGITS_RE.findall(cleaned))
        return int(digits) if digits else None
    return None
