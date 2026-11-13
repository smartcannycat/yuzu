import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from apps.lots.integrations.drom.katashiki import (
    matches_katashiki_token,
    normalize_katashiki_candidates,
)
from apps.lots.integrations.drom.schemas import DromCatalogSpec

_DROM_CATALOG_BASE = "https://www.drom.ru"
_HP_RE = re.compile(r"(\d{2,3})\s*л\.с\.", re.IGNORECASE)
_ENGINE_CC_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*л(?![.\w]|с\b)", re.IGNORECASE)
_YEARS_RE = re.compile(r"(\d{2})\.(\d{4})\s*[-–—]\s*(?:(\d{2})\.(\d{4})|(н\.в\.))")
_CHASSIS_BLOCK_RE = re.compile(r"Кузов\s*:\s*([^\n|]+)", re.IGNORECASE)
_CHASSIS_TOKEN_RE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", re.IGNORECASE)

_FUEL_MARKERS: tuple[tuple[str, str], ...] = (
    ("гибрид", "hybrid"),
    ("дизел", "diesel"),
    ("электро", "ev"),
    ("бензин", "gasoline"),
)


def parse_catalog_generations(html: str, *, model_code: str | None = None) -> list[str]:
    """Extract generation page URLs from a Drom catalog model page, prioritizing matching codes."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = normalize_katashiki_candidates(model_code)
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
        text = link.get_text(" ", strip=True)
        if candidates and any(matches_katashiki_token(text, cand) for cand in candidates):
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
    for marker, fuel_key in _FUEL_MARKERS:
        if marker in lower:
            return fuel_key
    return None


def _extract_drive_type(text: str) -> str | None:
    lower = text.lower()
    if "4wd" in lower or "полный" in lower:
        return "4WD"
    if "передний" in lower or "задний" in lower or "2wd" in lower:
        return "2WD"
    return None
