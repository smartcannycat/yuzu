"""HTML parsers for Aleado search results and lot detail pages.

Pure functions over the HTML returned by auc.aleado.com (UTF-8). The
structure is based on the live protocol research (findlots result table
with ``id="cell_N"`` rows and ``priceLotS{N}`` price hints, and the lot
detail page built from ``ColorCell_1`` / ``ColorCell_2`` label-value
cells). Only stdlib ``re`` is used so the parsers stay dependency free.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class AleadoParseError(RuntimeError):
    """Aleado markup changed or an expected element is missing."""


@dataclass(frozen=True)
class AleadoLotRow:
    """One row of the Aleado findlots result table."""

    trading_date: datetime | None
    lot_number: str
    auction_house: str
    model_name: str
    grade: str | None
    year: int | None
    mileage_km: int | None
    displacement_cc: int | None
    transmission: str | None
    color: str | None
    model_type: str | None
    start_price_jpy: int | None
    result: str | None
    internal_id: str | None
    photo_url: str | None


@dataclass(frozen=True)
class AleadoLotDetail:
    """Parsed fields of the Aleado lot detail page."""

    scores: str | None
    start_price_jpy: int | None
    mileage_km: int | None
    chassis_image_url: str | None
    model_type: str | None
    year: int | None
    auction_house: str | None
    lot_number: str | None
    trading_datetime: datetime | None
    result: str | None
    equipment: str | None
    condition: str | None


def _strip_tags(fragment: str) -> str:
    text = html_lib.unescape(_TAG_RE.sub("", fragment))
    return _WHITESPACE_RE.sub(" ", text).strip()


def _parse_int(value: str) -> int | None:
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, _DATETIME_FORMAT)
    except ValueError:
        return None


def _cell(row_html: str, cell_id: str) -> str:
    match = re.search(
        r'id="' + re.escape(cell_id) + r'"[^>]*>(.*?)</td>',
        row_html,
        re.S,
    )
    return _strip_tags(match.group(1)) if match else ""


_TOTAL_LOTS_RE = re.compile(r"Found total lots:\s*(?:<[^>]+>\s*)*(\d+)")
_ROW_RE = re.compile(r'<tr class="ColorGreed\d"[^>]*id="cell_(\d+)".*?</tr>', re.S)
_PRICE_HINT_RE = r'<div id="priceLotS{n}"[^>]*>([^<]*)</div>'
_INTERNAL_ID_RE = re.compile(r"p=project/lot&(?:amp;)?id=(\d+)")
_PHOTO_URL_RE = re.compile(r'load_src="([^"]+)"')


def parse_search_results(html: str) -> tuple[int, list[AleadoLotRow]]:
    """Parse the findlots page into (total lots, result rows).

    Raises AleadoParseError when the page does not carry the results
    table at all (session loss, markup change), so callers can treat it
    as a source-level failure.
    """
    total_match = _TOTAL_LOTS_RE.search(html)
    if total_match is None:
        raise AleadoParseError("Aleado search page is missing 'Found total lots' marker")
    total = int(total_match.group(1))

    rows: list[AleadoLotRow] = []
    for row_match in _ROW_RE.finditer(html):
        cell_index = row_match.group(1)
        row_html = row_match.group(0)

        def field(name: str, *, _row: str = row_html, _index: str = cell_index) -> str:
            return _cell(_row, f"{name}_{_index}")

        price_hint = re.search(_PRICE_HINT_RE.format(n=cell_index), html)
        start_price_jpy = None
        if price_hint is not None:
            thousands = _parse_int(price_hint.group(1))
            if thousands is not None and thousands > 0:
                start_price_jpy = thousands * 1000

        internal_id_match = _INTERNAL_ID_RE.search(row_html)
        photo_match = _PHOTO_URL_RE.search(row_html)
        grade = field("scores")
        rows.append(
            AleadoLotRow(
                trading_date=_parse_datetime(field("date")),
                lot_number=field("bid_number"),
                auction_house=field("auction"),
                model_name=field("model"),
                grade=grade or None,
                year=_parse_int(field("year")),
                mileage_km=_parse_int(field("mileage")),
                displacement_cc=_parse_int(field("displacement")),
                transmission=field("transmission") or None,
                color=field("color") or None,
                model_type=field("model_type") or None,
                start_price_jpy=start_price_jpy,
                result=field("result") or None,
                internal_id=internal_id_match.group(1) if internal_id_match else None,
                photo_url=photo_match.group(1) if photo_match else None,
            )
        )
    return total, rows


_DETAIL_CELL_RE = re.compile(
    r'<td class="ColorCell_1"[^>]*>(.*?)</td>\s*<td class="ColorCell_2"[^>]*>(.*?)</td>',
    re.S,
)
_BREADCRUMB_RE = re.compile(r"<strong>([^<]*&gt;[^<]*)</strong>")
_CHASSIS_IMG_RE = re.compile(r'<img[^>]+src="([^"]*chassis[^"]*)"')


def _detail_fields(html: str) -> dict[str, str]:
    # First occurrence wins: the main info table is authoritative, while
    # the translated "additional data" table repeats labels with
    # localized values (e.g. year "H29 year", result "temporary
    # exhibition").
    fields: dict[str, str] = {}
    for label_match, value_match in _DETAIL_CELL_RE.findall(html):
        label = _strip_tags(label_match).lower()
        if not label or label in fields:
            continue
        value_html = value_match
        if "chassis" in label:
            img = _CHASSIS_IMG_RE.search(value_html)
            if img is not None:
                fields[label] = html_lib.unescape(img.group(1))
                continue
        fields[label] = _strip_tags(value_html)
    return fields


def parse_lot_detail(html: str) -> AleadoLotDetail:
    """Parse the lot detail page into structured fields."""
    fields = _detail_fields(html)
    breadcrumb = _BREADCRUMB_RE.search(html)
    auction_house = None
    lot_number = None
    trading_datetime = None
    if breadcrumb is not None:
        parts = [part.strip() for part in _strip_tags(breadcrumb.group(1)).split(">")]
        parts = [part for part in parts if part]
        if len(parts) >= 3:
            trading_datetime = _parse_datetime(parts[0])
            auction_house = parts[1]
            lot_number = parts[2]
    time_cell = fields.get("time", "")
    if time_cell:
        trading_datetime = _parse_datetime(time_cell) or trading_datetime

    grade = fields.get("scores") or fields.get("appraisal point") or None
    year_value = fields.get("year", "")
    year = None
    if re.fullmatch(r"\d{4}", year_value.strip()):
        year = int(year_value.strip())
    return AleadoLotDetail(
        scores=grade,
        start_price_jpy=_parse_int(fields.get("start price", "")),
        mileage_km=_parse_int(fields.get("mileage, km.", "")),
        chassis_image_url=fields.get("chassis number"),
        model_type=fields.get("type") or None,
        year=year,
        auction_house=auction_house,
        lot_number=lot_number,
        trading_datetime=trading_datetime,
        result=fields.get("result") or None,
        equipment=fields.get("equipment") or None,
        condition=fields.get("condition") or None,
    )
