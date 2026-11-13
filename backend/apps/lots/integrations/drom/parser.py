import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from apps.lots.integrations.drom.schemas import DromCatalogSpec, DromListing

_DROM_CATALOG_BASE = "https://www.drom.ru"
_TRAILING_DECIMAL_RE = re.compile(r"[.,]\d{1,2}\s*(?:₽|руб\.?)?\s*$", re.IGNORECASE)
_PRICE_DIGITS_RE = re.compile(r"\d+")
_HP_RE = re.compile(r"(\d{2,3})\s*л\.с\.", re.IGNORECASE)
_ENGINE_CC_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*л(?![.\w]|с\b)", re.IGNORECASE)
_YEARS_RE = re.compile(r"(\d{2})\.(\d{4})\s*[-–—]\s*(?:(\d{2})\.(\d{4})|(н\.в\.))")
_CHASSIS_BLOCK_RE = re.compile(r"Кузов\s*:\s*([^\n|]+)", re.IGNORECASE)
_CHASSIS_TOKEN_RE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", re.IGNORECASE)


def parse_listings(html: str) -> list[DromListing]:
    """Extract Drom listings from embedded SSR JSON, falling back to DOM parsing."""
    listings = _parse_listings_from_json(html)
    if listings is not None:
        return listings
    return _parse_listings_from_html(html)


def _parse_listings_from_json(html: str) -> list[DromListing] | None:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        text = script.string or ""
        if '"__slug":"bulls-list-auto"' not in text and '"__slug": "bulls-list-auto"' not in text:
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        bull_list = payload.get("bullList")
        if not isinstance(bull_list, dict):
            continue
        bulls_data = bull_list.get("bullsData")
        if not isinstance(bulls_data, list):
            continue
        return _extract_bulls_from_groups(bulls_data)
    return None


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
    attributes: list[str] = []
    for attr in raw.get("attributes") or []:
        if isinstance(attr, dict):
            val = attr.get("payload")
            if isinstance(val, str):
                attributes.append(val)
            elif isinstance(val, dict) and isinstance(val.get("text"), str):
                attributes.append(val["text"])

    raw_car_state = raw.get("carState")
    if isinstance(raw_car_state, list):
        car_state = [str(item) for item in raw_car_state if item is not None and str(item).strip()]
    elif isinstance(raw_car_state, str) and raw_car_state.strip():
        car_state = [raw_car_state.strip()]
    else:
        car_state = []

    badges: list[str] = []
    if raw.get("info"):
        badges.append(str(raw["info"]))
    if group_title and any(
        marker in group_title.lower() for marker in ("под заказ", "на заказ", "в пути")
    ):
        badges.append(group_title)
    if raw.get("locationFrom"):
        badges.append(str(raw["locationFrom"]))
    for mark in raw.get("marks") or []:
        if isinstance(mark, dict) and mark.get("locationCountryFrom"):
            badges.append(str(mark["locationCountryFrom"]))

    return DromListing(
        bull_id=bull_id,
        title=str(raw.get("title") or "").strip(),
        price_rub=price,
        url=str(raw["url"]) if raw.get("url") else None,
        description=str(raw.get("description") or "").strip(),
        location=str(raw.get("location") or "").strip(),
        sold=bool(raw.get("sold", False)),
        car_state=car_state,
        attributes=attributes,
        badges=badges,
        is_nearby_city=is_nearby_city,
    )


def _parse_listings_from_html(html: str) -> list[DromListing]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all(attrs={"data-ftid": "bulls-list_bull"})
    results: list[DromListing] = []
    for card in cards:
        price_el = card.find(attrs={"data-ftid": "bull_price"})
        if price_el is None:
            continue
        price = _parse_int(price_el.get_text(" ", strip=True))
        if price is None or price <= 0:
            continue
        title_el = card.find(attrs={"data-ftid": "bull_title"})
        title = title_el.get_text(" ", strip=True) if title_el else ""
        link_el = (title_el.find("a", href=True) if title_el else None) or card.find("a", href=True)
        url = link_el["href"] if link_el and link_el.has_attr("href") else None
        location_el = card.find(attrs={"data-ftid": "bull_location"})
        location = location_el.get_text(" ", strip=True) if location_el else ""
        attrs = [
            el.get_text(" ", strip=True)
            for el in card.find_all(attrs={"data-ftid": "bull_description-item"})
        ]
        card_text = card.get_text(" ", strip=True)
        card_lower = card_text.lower()
        sold = "снято с продажи" in card_lower or "продано" in card_lower
        car_state = [marker for marker in ("под заказ", "в пути") if marker in card_lower]
        results.append(
            DromListing(
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
        )
    return results


def parse_catalog_generations(html: str, *, model_code: str | None = None) -> list[str]:
    """Extract generation page URLs from a Drom catalog model page, prioritizing matching codes."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = _katashiki_tokens(model_code)
    prioritized: list[str] = []
    fallback: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/g_" not in href:
            continue
        full_url = urljoin(_DROM_CATALOG_BASE, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        text = link.get_text(" ", strip=True).upper()
        if candidates and any(
            re.search(rf"(?<![A-Z0-9]){re.escape(cand)}(?![A-Z0-9])", text) for cand in candidates
        ):
            prioritized.append(full_url)
        else:
            fallback.append(full_url)

    return prioritized if prioritized else fallback


def parse_catalog_power_specs(html: str) -> list[DromCatalogSpec]:
    """Extract model_code and engine power specs from a Drom catalog generation page."""
    soup = BeautifulSoup(html, "html.parser")
    specs: list[DromCatalogSpec] = []
    for row in soup.find_all("tr"):
        row_text = row.get_text(" ", strip=True)
        hp_match = _HP_RE.search(row_text)
        chassis_codes = _extract_chassis_codes(row_text)
        if not hp_match or not chassis_codes:
            continue
        power_hp = int(hp_match.group(1))
        engine_cc = _extract_engine_cc(row_text)
        fuel_type = _extract_fuel_type(row_text)
        drive_type = _extract_drive_type(row_text)
        year_start, year_end = _extract_row_years(row, row_text)
        for chassis_code in chassis_codes:
            specs.append(
                DromCatalogSpec(
                    model_code=chassis_code,
                    power_hp=power_hp,
                    engine_cc=engine_cc,
                    fuel_type=fuel_type,
                    drive_type=drive_type,
                    year_start=year_start,
                    year_end=year_end,
                )
            )
    return specs


def _extract_chassis_codes(row_text: str) -> list[str]:
    block_match = _CHASSIS_BLOCK_RE.search(row_text)
    if not block_match:
        return []
    raw_block = block_match.group(1)
    # Stop before next labeled field if present in flattened row text.
    raw_block = re.split(r"\b(?:Двигатель|Мощность|Цена|Период)\b", raw_block, maxsplit=1)[0]
    codes: list[str] = []
    for token in _CHASSIS_TOKEN_RE.findall(raw_block):
        upper = token.upper()
        if any(ch.isalpha() for ch in upper) and any(ch.isdigit() for ch in upper):
            codes.append(upper)
    return codes


def _extract_row_years(header_row: Any, header_text: str) -> tuple[int | None, int | None]:
    years: list[int] = []
    is_ongoing = False

    def _scan_text(text: str) -> None:
        nonlocal is_ongoing
        for match in _YEARS_RE.finditer(text):
            years.append(int(match.group(2)))
            if match.group(4):
                years.append(int(match.group(4)))
            if match.group(5):
                is_ongoing = True

    _scan_text(header_text)
    sibling = header_row.find_next_sibling("tr")
    steps = 0
    while sibling is not None and steps < 8:
        text = sibling.get_text(" ", strip=True)
        if _CHASSIS_BLOCK_RE.search(text):
            break
        _scan_text(text)
        sibling = sibling.find_next_sibling("tr")
        steps += 1
    if not years:
        return None, None
    return min(years), (None if is_ongoing else max(years))


def _extract_engine_cc(text: str) -> int | None:
    match = _ENGINE_CC_RE.search(text)
    if not match:
        return None
    try:
        liters = float(match.group(1).replace(",", "."))
        return round(liters * 1000)
    except ValueError:
        return None


def _extract_fuel_type(text: str) -> str | None:
    lower = text.lower()
    if "гибрид" in lower:
        return "hybrid"
    if "дизел" in lower:
        return "diesel"
    if "электро" in lower:
        return "ev"
    if "бензин" in lower:
        return "gasoline"
    return None


def _extract_drive_type(text: str) -> str | None:
    lower = text.lower()
    if "4wd" in lower or "полный" in lower:
        return "4WD"
    if "передний" in lower or "задний" in lower or "2wd" in lower:
        return "2WD"
    return None


def _katashiki_tokens(model_code: str | None) -> list[str]:
    if not model_code:
        return []
    raw = model_code.strip().upper()
    if not raw:
        return []
    tokens = [raw]
    parts = [p for p in raw.split("-") if p]
    if len(parts) >= 2:
        core = parts[1] if len(parts[0]) <= 3 else parts[0]
        if core not in tokens:
            tokens.append(core)
        base = re.sub(r"[A-Z]$", "", core)
        if base and len(base) >= 3 and base not in tokens:
            tokens.append(base)
    return tokens


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


def parse_brand_models_from_html(html: str, make_slug: str) -> tuple[list[str], dict[str, str]]:
    """Extract model names and slug map from a Drom brand page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    seen_names: set[str] = set()
    slug_map: dict[str, str] = {}

    for script in soup.find_all("script"):
        text = script.string or ""
        if '"__slug":"bulls-list-auto"' not in text and '"__slug": "bulls-list-auto"' not in text:
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        models_groups = (payload.get("filter") or {}).get("models")
        if not isinstance(models_groups, list):
            continue
        for group in models_groups:
            if not isinstance(group, dict):
                continue
            for item in (group.get("top") or []) + (group.get("regular") or []):
                if isinstance(item, dict) and item.get("name"):
                    name = str(item["name"]).strip()
                    if name and name not in seen_names:
                        seen_names.add(name)
                        names.append(name)
        break

    escaped_make = re.escape(make_slug.strip("/").lower())
    link_re = re.compile(rf"^https://auto\.drom\.ru/{escaped_make}/([a-z0-9_-]+)/$", re.IGNORECASE)
    for link in soup.find_all("a", href=True):
        match = link_re.match(str(link["href"]))
        if not match:
            continue
        model_slug = match.group(1).lower()
        if model_slug in {
            "bez-probega",
            "benzin",
            "diesel",
            "gibrid",
            "electro",
            "all",
            "new",
        } or model_slug.startswith(("color-", "do-", "ot-", "year-", "page")):
            continue
        label = link.get_text(" ", strip=True)
        if not label or len(label) > 60:
            continue
        slug_map.setdefault(label.lower(), model_slug)
        if label not in seen_names:
            seen_names.add(label)
            names.append(label)

    return names, slug_map


def parse_catalog_brands_from_html(html: str) -> tuple[list[str], dict[str, str]]:
    """Extract brand names and catalog URL slugs from https://www.drom.ru/catalog/."""
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    seen_names: set[str] = set()
    slug_map: dict[str, str] = {}
    ignored = frozenset({"chinese", "lcv", "all", "search"})
    link_re = re.compile(r"^(?:https://www\.drom\.ru)?/catalog/([a-z0-9_-]+)/$", re.IGNORECASE)

    for link in soup.find_all("a", href=True):
        match = link_re.match(str(link["href"]))
        if not match:
            continue
        brand_slug = match.group(1).lower()
        if brand_slug in ignored:
            continue
        label = link.get_text(" ", strip=True)
        if not label or len(label) > 60:
            continue
        slug_map.setdefault(label.lower(), brand_slug)
        if label not in seen_names:
            seen_names.add(label)
            names.append(label)

    return names, slug_map


def parse_catalog_models_from_html(html: str, make_slug: str) -> tuple[list[str], dict[str, str]]:
    """Extract model names and catalog URL slugs from https://www.drom.ru/catalog/{make_slug}/."""
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    seen_names: set[str] = set()
    slug_map: dict[str, str] = {}
    escaped_make = re.escape(make_slug.strip("/").lower())
    link_re = re.compile(
        rf"^(?:https://www\.drom\.ru)?/catalog/{escaped_make}/([a-z0-9_-]+)/$",
        re.IGNORECASE,
    )

    for link in soup.find_all("a", href=True):
        match = link_re.match(str(link["href"]))
        if not match:
            continue
        model_slug = match.group(1).lower()
        label = link.get_text(" ", strip=True)
        if not label or len(label) > 60:
            continue
        slug_map.setdefault(label.lower(), model_slug)
        if label not in seen_names:
            seen_names.add(label)
            names.append(label)

    return names, slug_map
