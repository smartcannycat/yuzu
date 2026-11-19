"""Deterministic Japanese era and Gregorian date normalizers."""

import re
import unicodedata

from ml_service.config import resolve_reference_date

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

_ERA_OFFSETS: dict[str, int] = {
    "R": 2018,
    "令和": 2018,
    "H": 1988,
    "平成": 1988,
    "S": 1925,
    "昭和": 1925,
}
_KANJI_NUM_RE = re.compile(r"[〇零一二三四五六七八九十]+")
_ERA_DATE_RE = re.compile(
    r"(?<![A-Za-z])(R|令和|H|平成|S|昭和)\s*(\d{1,2})"
    r"(?:\s*[./年-]\s*(\d{1,2})(?!\d)|\s+(\d{1,2})(?=\s*(?:月|$)))?",
    re.IGNORECASE,
)
_MM_YYYY_RE = re.compile(r"\b(\d{1,2})[./](19\d{2}|20\d{2})\b")
_GREGORIAN_DATE_RE = re.compile(r"(19\d{2}|20\d{2})(?:\D+(\d{1,2}))?")
_BARE_DATE_RE = re.compile(r"^(\d{1,2})(?:\D+(\d{1,2}))?")
_MONTH_KANJI_RE = re.compile(r"(\d{1,2})\s*月")


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


def _resolve_bare_year_date(
    raw: str,
    num: int,
    month: str | None,
    *,
    is_future_date: bool,
    cur_reiwa: int,
) -> tuple[int | None, int | None, str | None, bool]:
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


def parse_japanese_date(
    raw: str | None,
    *,
    is_future_date: bool = False,
    current_year: int | None = None,
) -> tuple[int | None, int | None, str | None, bool]:
    """Parse Japanese era or Gregorian date into (year, month, formatted_str, is_ambiguous)."""
    if not raw:
        return None, None, None, False

    cur_year, _ = resolve_reference_date(current_year, None)
    cur_reiwa = cur_year - 2018

    normalized = re.sub(
        r"(R|令和|H|平成|S|昭和)元",
        r"\g<1>1",
        unicodedata.normalize("NFKC", raw).strip(),
    )
    normalized = _replace_kanji_numbers(normalized)

    era_match = _ERA_DATE_RE.search(normalized)
    if era_match:
        era = era_match.group(1).upper()
        year = _ERA_OFFSETS[era] + int(era_match.group(2))
        month = _extract_month(normalized, era_match.group(3) or era_match.group(4))
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

    return _resolve_bare_year_date(
        raw,
        int(bare_match.group(1)),
        bare_match.group(2),
        is_future_date=is_future_date,
        cur_reiwa=cur_reiwa,
    )


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
    reference_year: int | None = None,
    reference_month: int | None = None,
) -> tuple[str | None, bool]:
    """Format registration age string and check whether vehicle is in the 3-5 year duty corridor."""
    if reg_year is None:
        return None, False

    ref_year, ref_month = resolve_reference_date(reference_year, reference_month)
    effective_month = reg_month if reg_month is not None else 7
    total_months = (ref_year - reg_year) * 12 + (ref_month - effective_month)
    is_pass_corridor = 36 <= total_months <= 60

    display_months = max(total_months, 0)
    years, months = divmod(display_months, 12)
    date_part = f"{reg_month:02d}.{reg_year}" if reg_month is not None else str(reg_year)
    formatted = f"{date_part} (Возраст {years} {_pluralize_years_ru(years)} {months} мес.)"
    return formatted, is_pass_corridor
