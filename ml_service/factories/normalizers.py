"""Deterministic normalizers for Japanese auction sheet codes, dates, and defects."""

import datetime
import re
import unicodedata

from app.domains.enums import FrameIdConfidence

CHASSIS_RE = re.compile(r"^(?:[A-Z0-9]{2,7}-\d{4,8}|\d{6,8}|[A-HJ-NPR-Z0-9]{17})$")
KATASHIKI_RE = re.compile(r"^(?:[A-Z0-9]{1,4}-)?[A-Z0-9]{2,8}(?:-[A-Z0-9]{1,5})?$")
EMISSION_PREFIX_RE = re.compile(r"^[0-9A-Z]{1,4}-")
CHASSIS_CANONICAL_RE = re.compile(r"^[A-Z0-9]{2,8}-\d{4,8}$")
DEFECT_ITEM_RE = re.compile(r"^([A-Z]{1,2})(\d)?$")

KANJI_DIGITS: dict[str, int] = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

# Inspection strictness index (I_strict) for Japanese auto auctions.
AUCTION_STRICTNESS: dict[str, float] = {
    "TAA": 1.00,
    "HONDA": 0.95,
    "HAA": 0.95,
    "CAA": 0.90,
    "USS": 0.75,
    "ORIX": 0.75,
    "ARAI": 0.75,
    "AUCNET": 0.70,
    "JU": 0.60,
    "MIRIVE": 0.55,
    "KCAA": 0.55,
    "LAA": 0.55,
    "ZIP": 0.75,
}

_ERA_OFFSETS: dict[str, int] = {
    "R": 2018,
    "令和": 2018,
    "H": 1988,
    "平成": 1988,
    "S": 1925,
    "昭和": 1925,
}
_KANJI_NUM_RE = re.compile(r"[〇零一二三四五六七八九十]+")
_ERA_DATE_RE = re.compile(r"(?<![A-Za-z])(R|令和|H|平成|S|昭和)\s*(\d{1,2})(?:\D+(\d{1,2}))?", re.I)
_MM_YYYY_RE = re.compile(r"\b(\d{1,2})[./](19\d{2}|20\d{2})\b")
_GREGORIAN_DATE_RE = re.compile(r"(19\d{2}|20\d{2})(?:\D+(\d{1,2}))?")
_BARE_DATE_RE = re.compile(r"^(\d{1,2})(?:\D+(\d{1,2}))?")
_MONTH_KANJI_RE = re.compile(r"(\d{1,2})\s*月")


def clean_code(raw: str | None) -> str:
    """Normalize Unicode width, trim whitespace, and strip inner spaces."""
    if not raw:
        return ""
    return unicodedata.normalize("NFKC", raw).strip().replace(" ", "")


def normalize_auction_house(raw: str | None) -> tuple[str | None, float | None]:
    """Normalize an auction house name and return its strictness index."""
    if not raw:
        return None, None
    cleaned = raw.strip()
    if not cleaned:
        return None, None
    upper = cleaned.upper()
    for key, strictness in AUCTION_STRICTNESS.items():
        if key in upper:
            return key, strictness
    return cleaned, None


def synthesize_frame_id(model_code: str, chassis_number: str) -> tuple[str, FrameIdConfidence]:
    """Build canonical Frame ID (e.g. RV5-1356915) and its confidence level."""
    c = clean_code(chassis_number).upper()
    m = clean_code(model_code).upper()

    if "-" in c and CHASSIS_CANONICAL_RE.match(c):
        return c, FrameIdConfidence.EXACT

    if c.isdigit():
        clean_model = EMISSION_PREFIX_RE.sub("", m)
        core_code = re.sub(r"(?<=\d)[A-Z]$", "", clean_model)
        if core_code:
            return f"{core_code}-{c}", FrameIdConfidence.SYNTHESIZED

    return c, FrameIdConfidence.RAW


def split_defect_codes(raw_code: str) -> list[tuple[str, int | None]]:
    """Split composite body diagram defect codes into (code, severity) pairs."""
    norm = unicodedata.normalize("NFKC", raw_code).strip().upper()
    parts = re.split(r"[/,\s]+", norm)
    results: list[tuple[str, int | None]] = []

    for part in parts:
        p = part.strip()
        if not p:
            continue
        if p in {"XX", "X"}:
            results.append((p, None))
            continue
        match = DEFECT_ITEM_RE.match(p)
        if not match:
            results.append((p, None))
            continue

        letters = match.group(1)
        severity = int(match.group(2)) if match.group(2) else None
        # Paired single-letter defect codes like AU3 represent A3 and U3.
        if len(letters) == 2 and letters not in {"XX", "FW"}:
            results.append((letters[0], severity))
            results.append((letters[1], severity))
        else:
            results.append((letters, severity))

    return results or [(norm, None)]


def _replace_kanji_numbers(text: str) -> str:
    """Convert Japanese kanji numerals (0..99) in text to ASCII digits."""

    def _convert(match: re.Match[str]) -> str:
        token = match.group(0)
        if "十" not in token:
            return "".join(str(KANJI_DIGITS[ch]) for ch in token)
        tens_part, ones_part = token.split("十", 1)
        tens = KANJI_DIGITS.get(tens_part, 1) if tens_part else 1
        ones = KANJI_DIGITS.get(ones_part, 0) if ones_part else 0
        return str(tens * 10 + ones)

    return _KANJI_NUM_RE.sub(_convert, text)


def _format_parsed_date(
    year: int,
    month_str: str | None,
    *,
    ambiguous: bool = False,
) -> tuple[int, int | None, str, bool]:
    if month_str and 1 <= int(month_str) <= 12:
        month = int(month_str)
        return year, month, f"{month:02d}.{year}", ambiguous
    return year, None, str(year), ambiguous


def _extract_month(text: str, captured_month: str | None) -> str | None:
    if captured_month:
        return captured_month
    month_match = _MONTH_KANJI_RE.search(text)
    return month_match.group(1) if month_match else None


def parse_japanese_date(
    raw: str | None,
    *,
    is_future_date: bool = False,
    current_year: int = 2026,
) -> tuple[int | None, int | None, str | None, bool]:
    """Parse Japanese era or Gregorian date into (year, month, formatted_str, is_ambiguous)."""
    if not raw:
        return None, None, None, False

    cur_year = current_year or datetime.date.today().year
    cur_reiwa = cur_year - 2018

    normalized = unicodedata.normalize("NFKC", raw).strip().replace("元年", "1年")
    normalized = _replace_kanji_numbers(normalized)

    era_match = _ERA_DATE_RE.search(normalized)
    if era_match:
        era = era_match.group(1).upper()
        year = _ERA_OFFSETS[era] + int(era_match.group(2))
        month = _extract_month(normalized, era_match.group(3))
        return _format_parsed_date(year, month)

    mm_yyyy_match = _MM_YYYY_RE.search(normalized)
    if mm_yyyy_match and 1 <= int(mm_yyyy_match.group(1)) <= 12:
        return _format_parsed_date(int(mm_yyyy_match.group(2)), mm_yyyy_match.group(1))

    greg_match = _GREGORIAN_DATE_RE.search(normalized)
    if greg_match:
        month = _extract_month(normalized, greg_match.group(2))
        return _format_parsed_date(int(greg_match.group(1)), month)

    bare_match = _BARE_DATE_RE.search(normalized)
    if not bare_match:
        return None, None, raw, True

    num = int(bare_match.group(1))
    month = bare_match.group(2)

    if is_future_date:
        if 1 <= num <= 18:
            return _format_parsed_date(2018 + num, month)
        if 19 <= num <= 32:
            return _format_parsed_date(1988 + num, month)
        return None, None, raw, True

    if 1 <= num <= cur_reiwa:
        # Bare years 1..cur_reiwa overlap theoretically with Heisei 1..cur_reiwa.
        return _format_parsed_date(2018 + num, month, ambiguous=True)
    if (cur_reiwa + 1) <= num <= 32:
        # Includes transitional Heisei 31 (2019) and Heisei 32 (2020) sheets.
        return _format_parsed_date(1988 + num, month)
    if 33 <= num <= 64:
        return _format_parsed_date(1925 + num, month)

    return None, None, raw, True


def _pluralize_years_ru(years: int) -> str:
    mod100 = years % 100
    if 11 <= mod100 <= 19:
        return "лет"
    mod10 = years % 10
    if mod10 == 1:
        return "год"
    if 2 <= mod10 <= 4:
        return "года"
    return "лет"


def calculate_age_and_corridor(
    reg_year: int | None,
    reg_month: int | None,
    *,
    reference_year: int = 2026,
    reference_month: int = 11,
) -> tuple[str | None, bool]:
    """Format registration age string and check whether vehicle is in the 3-5 year duty corridor."""
    if reg_year is None:
        return None, False

    effective_month = reg_month if reg_month is not None else 7
    total_months = (reference_year - reg_year) * 12 + (reference_month - effective_month)
    is_pass_corridor = 36 <= total_months <= 60

    display_months = max(total_months, 0)
    years, months = divmod(display_months, 12)
    date_part = f"{reg_month:02d}.{reg_year}" if reg_month is not None else str(reg_year)
    formatted = f"{date_part} (Возраст {years} {_pluralize_years_ru(years)} {months} мес.)"
    return formatted, is_pass_corridor
