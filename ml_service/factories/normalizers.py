"""Deterministic normalizers for Japanese auction sheet codes, dates, and defects."""

import datetime
import re
import unicodedata

from app.domains.enums import AuctionHouse, BodyPanel, DefectCode, FrameIdConfidence

CHASSIS_RE = re.compile(r"^(?:[A-Z0-9]{2,7}-\d{4,8}|\d{6,8}|[A-HJ-NPR-Z0-9]{17})$")
KATASHIKI_RE = re.compile(r"^(?:[A-Z0-9]{1,4}-)?[A-Z0-9]{2,8}(?:-[A-Z0-9]{1,5})?$")
EMISSION_PREFIX_RE = re.compile(r"^[0-9A-Z]{1,4}-")
CHASSIS_CANONICAL_RE = re.compile(r"^[A-Z0-9]{2,8}-\d{4,8}$")
DEFECT_ITEM_RE = re.compile(r"^([A-Z]{1,2})([1-3])?$")
_VALID_SINGLE_DEFECT_LETTERS = frozenset({"A", "U", "W", "S", "C", "P", "G"})

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

# Canonical inspection strictness index (I_strict) aligned with API contracts (Decision D1).
AUCTION_STRICTNESS: dict[AuctionHouse, float] = {
    AuctionHouse.TAA: 1.00,
    AuctionHouse.HONDA: 0.90,
    AuctionHouse.ORIX: 0.80,
    AuctionHouse.USS: 0.75,
    AuctionHouse.ZIP: 0.75,
    AuctionHouse.CAA: 0.70,
    AuctionHouse.MIRIVE: 0.70,
    AuctionHouse.ARAI: 0.65,
    AuctionHouse.AUCNET: 0.65,
    AuctionHouse.LAA: 0.65,
    AuctionHouse.JU: 0.60,
    AuctionHouse.KCAA: 0.60,
    AuctionHouse.OTHER: 0.65,
}

_AUCTION_PHRASE_ALIASES: tuple[tuple[str, AuctionHouse], ...] = (
    ("トヨタオートオークション", AuctionHouse.TAA),
    ("TOYOTA AUTO AUCTION", AuctionHouse.TAA),
    ("TOYOTA AA", AuctionHouse.TAA),
    ("中部オートオークション", AuctionHouse.CAA),
    ("CHUBU AUTO AUCTION", AuctionHouse.CAA),
    ("ホンダオートオークション", AuctionHouse.HONDA),
    ("HONDA AUTO AUCTION", AuctionHouse.HONDA),
    ("ホンダ", AuctionHouse.HONDA),
    ("アライオートオークション", AuctionHouse.ARAI),
    ("ARAI AUTO AUCTION", AuctionHouse.ARAI),
    ("アライ", AuctionHouse.ARAI),
    ("ユーエスエス", AuctionHouse.USS),
    ("ジェイユー", AuctionHouse.JU),
    ("オークネット", AuctionHouse.AUCNET),
    ("オリックス", AuctionHouse.ORIX),
    ("ミライブ", AuctionHouse.MIRIVE),
    ("ジップ", AuctionHouse.ZIP),
    ("ケーシーエーエー", AuctionHouse.KCAA),
    ("エルエーエー", AuctionHouse.LAA),
)

_AUCTION_TOKEN_ALIASES: dict[str, AuctionHouse] = {
    "TAA": AuctionHouse.TAA,
    "USS": AuctionHouse.USS,
    "CAA": AuctionHouse.CAA,
    "HONDA": AuctionHouse.HONDA,
    "HAA": AuctionHouse.HONDA,
    "ARAI": AuctionHouse.ARAI,
    "AUCNET": AuctionHouse.AUCNET,
    "ORIX": AuctionHouse.ORIX,
    "ZIP": AuctionHouse.ZIP,
    "JU": AuctionHouse.JU,
    "MIRIVE": AuctionHouse.MIRIVE,
    "KCAA": AuctionHouse.KCAA,
    "LAA": AuctionHouse.LAA,
}

_EMPTY_AUCTION_MARKERS = frozenset({"", "UNKNOWN", "NONE", "NULL", "N/A", "NA", "-"})

_DEFECT_LABELS_RU: dict[str, str] = {
    "A": "царапина",
    "U": "вмятина",
    "W": "ремонт/волна окраса",
    "S": "ржавчина",
    "C": "коррозия",
    "P": "нарушение ЛКП",
    "G": "скол стекла",
    "XX": "замена детали",
    "X": "требуется замена",
    "R": "следы ремонта",
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
_ERA_DATE_RE = re.compile(r"(?<![A-Za-z])(R|令和|H|平成|S|昭和)\s*(\d{1,2})(?:\D+(\d{1,2}))?", re.IGNORECASE)
_MM_YYYY_RE = re.compile(r"\b(\d{1,2})[./](19\d{2}|20\d{2})\b")
_GREGORIAN_DATE_RE = re.compile(r"(19\d{2}|20\d{2})(?:\D+(\d{1,2}))?")
_BARE_DATE_RE = re.compile(r"^(\d{1,2})(?:\D+(\d{1,2}))?")
_MONTH_KANJI_RE = re.compile(r"(\d{1,2})\s*月")


def clean_code(raw: str | None) -> str:
    """Normalize Unicode width, trim whitespace, and strip inner spaces."""
    if not raw:
        return ""
    return unicodedata.normalize("NFKC", raw).strip().replace(" ", "")


def normalize_auction_house(
    raw: str | None,
    *,
    default_strictness: float = AUCTION_STRICTNESS[AuctionHouse.OTHER],
) -> tuple[str | None, float | None]:
    """Normalize an auction house name by exact phrase/token aliases without substring traps."""
    if not raw:
        return None, None
    normalized = unicodedata.normalize("NFKC", raw).strip()
    upper_clean = normalized.upper()
    if upper_clean in _EMPTY_AUCTION_MARKERS:
        return None, None

    compact_jp = re.sub(r"\s+", "", normalized)
    upper_spaced = re.sub(r"\s+", " ", upper_clean)
    for phrase, house in _AUCTION_PHRASE_ALIASES:
        phrase_upper = phrase.upper()
        if phrase_upper in compact_jp.upper() or re.search(rf"(?<![A-Z0-9]){re.escape(phrase_upper)}(?![A-Z0-9])", upper_spaced):
            return house.value, AUCTION_STRICTNESS[house]

    tokens = re.findall(r"[A-Z0-9]+", upper_spaced)
    for token in tokens:
        matched_house = _AUCTION_TOKEN_ALIASES.get(token)
        if matched_house is not None:
            return matched_house.value, AUCTION_STRICTNESS[matched_house]

    return AuctionHouse.OTHER.value, default_strictness


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


def parse_defect_codes_with_warnings(
    raw_code: str,
) -> tuple[list[tuple[DefectCode, int | None]], list[str]]:
    """Parse composite defect code into validated (DefectCode, severity) pairs and warnings."""
    norm = unicodedata.normalize("NFKC", raw_code).strip()
    parts = re.split(r"[/,\s]+", norm)
    results: list[tuple[DefectCode, int | None]] = []
    warnings: list[str] = []

    for part in parts:
        raw_part = part.strip()
        if not raw_part:
            continue
        upper_part = raw_part.upper()

        if upper_part in {"S小", "S(小)"}:
            results.append((DefectCode.S, 1))
            continue
        if upper_part in {"C小", "C(小)"}:
            results.append((DefectCode.C, 1))
            continue
        if upper_part in {"XX", "X", "R"}:
            results.append((DefectCode(upper_part), None))
            continue

        match = DEFECT_ITEM_RE.match(upper_part)
        if not match:
            warnings.append(f"unknown_defect_code:{raw_part}")
            continue

        letters = match.group(1)
        severity = int(match.group(2)) if match.group(2) else None
        if all(ch in _VALID_SINGLE_DEFECT_LETTERS for ch in letters):
            for ch in letters:
                results.append((DefectCode(ch), severity))
        else:
            warnings.append(f"unknown_defect_code:{raw_part}")

    return results, warnings


def split_defect_codes(raw_code: str) -> list[tuple[str, int | None]]:
    """Split composite body diagram defect codes into validated (code, severity) pairs."""
    parsed, _ = parse_defect_codes_with_warnings(raw_code)
    return [(code.value, severity) for code, severity in parsed]


def build_defect_description_ru(
    panel_ru: str,
    defect_code: DefectCode | str,
    severity: int | None,
) -> str:
    """Build deterministic Russian human-readable description for a normalized defect."""
    code_str = defect_code.value if isinstance(defect_code, DefectCode) else str(defect_code)
    label = _DEFECT_LABELS_RU.get(code_str, code_str.lower())
    panel = panel_ru.strip() or "Кузов"
    if severity is not None:
        return f"{panel} — {label}, степень {severity}"
    return f"{panel} — {label}"


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


_PANEL_ZONE_KEYWORDS: tuple[tuple[str, BodyPanel, str], ...] = (
    ("コアサポート", BodyPanel.OTHER, "Рамка радиатора (Core Support)"),
    ("クロスメンバー", BodyPanel.OTHER, "Поперечина кузова (Crossmember)"),
    ("インパネ", BodyPanel.OTHER, "Брызговик/внутреннее крыло"),
    ("インサイドパネル", BodyPanel.OTHER, "Брызговик/внутреннее крыло"),
    ("ピラー", BodyPanel.OTHER, "Стойка кузова"),
    ("サイドメンバー", BodyPanel.OTHER, "Лонжерон"),
    ("フレーム", BodyPanel.OTHER, "Рама / силовой лонжерон"),
    ("フェンダー左前", BodyPanel.FRONT_LEFT_FENDER, "Переднее левое крыло"),
    ("左Fフェンダー", BodyPanel.FRONT_LEFT_FENDER, "Переднее левое крыло"),
    ("右Fフェンダー", BodyPanel.FRONT_RIGHT_FENDER, "Переднее правое крыло"),
    ("左Fドア", BodyPanel.FRONT_LEFT_DOOR, "Передняя левая дверь"),
    ("右Fドア", BodyPanel.FRONT_RIGHT_DOOR, "Передняя правая дверь"),
    ("左Rドア", BodyPanel.REAR_LEFT_DOOR, "Задняя левая дверь"),
    ("右Rドア", BodyPanel.REAR_RIGHT_DOOR, "Задняя правая дверь"),
    ("Fバンパー", BodyPanel.FRONT_BUMPER, "Передний бампер"),
    ("Rバンパー", BodyPanel.REAR_BUMPER, "Задний бампер"),
    ("ボンネット", BodyPanel.HOOD, "Капот"),
    ("ルーフ", BodyPanel.ROOF, "Крыша"),
    ("トランク", BodyPanel.TAILGATE, "Крышка багажника / пятая дверь"),
    ("バックドア", BodyPanel.TAILGATE, "Пятая дверь"),
    ("フロントガラス", BodyPanel.WINDSHIELD, "Лобовое стекло"),
)

_REPAIR_ACTION_RE = re.compile(r"(XX|\bX\b|\bR\b|W\d?|交換|修理|鈑金|歪|曲|凹|修復|замен|ремонт|деформац)", re.IGNORECASE)
_PILLAR_OR_FRAME_RE = re.compile(r"(ピラー|サイドメンバー|フレーム|クロスメンバー|修復歴|骨格|стойк|лонжерон)", re.IGNORECASE)
_INSIDE_PANEL_ONLY_RE = re.compile(r"(インパネ|インサイドパネル)", re.IGNORECASE)
_CORE_SUPPORT_RE = re.compile(r"(コアサポート|рамк[аи]\s+радиатора|телевизор)", re.IGNORECASE)
_NO_ANOMALY_RE = re.compile(r"(異常なし|問題なし|исправн|в\s+норме)", re.IGNORECASE)


def normalize_body_panel(
    panel_id: BodyPanel,
    panel_ru: str,
    visual_location: str = "",
) -> tuple[BodyPanel, str]:
    """Ensure body panel maps cleanly into canonical 16 panels or BodyPanel.OTHER with Russian name."""
    combined = f"{visual_location} {panel_ru}"
    for keyword, mapped_panel, default_ru in _PANEL_ZONE_KEYWORDS:
        if keyword in combined:
            clean_ru = panel_ru.strip() or default_ru
            if mapped_panel == BodyPanel.OTHER:
                return BodyPanel.OTHER, clean_ru
            return mapped_panel if panel_id == BodyPanel.OTHER else panel_id, clean_ru
    return panel_id, (panel_ru.strip() or "Другая зона кузова")


def normalize_transmission_ru(raw: str | None, ru: str | None) -> str:
    """Normalize transmission codes/descriptions to canonical Russian labels."""
    candidates = [
        unicodedata.normalize("NFKC", raw or "").strip().upper(),
        unicodedata.normalize("NFKC", ru or "").strip().upper(),
    ]
    joined = " ".join(c for c in candidates if c)
    if not joined:
        return "не указано"

    if any(tok in joined for tok in ("CVT", "IAT", "ECVT", "無段", "ВАРИАТОР")):
        return "вариатор (CVT)"
    if any(tok in joined for tok in ("DCT", "DSG", "AMT", "РОБОТ", "デュアルクラッチ")):
        return "робот"
    if re.search(r"(?<![A-Z])(MT|[4567]MT|[456]F|F[456]|МКПП|МЕХАНИК)(?![A-Z])", joined):
        return "МКПП"
    if re.search(r"(?<![A-Z])(AT|FAT|SAT|DAT|CAT|[4-9]AT|АКПП|АВТОМАТ)(?![A-Z])", joined):
        return "АКПП"
    return (ru or "").strip() or (raw or "").strip() or "не указано"


def clean_color_ru(color_ru: str | None, paint_code: str | None) -> str | None:
    """Remove embedded paint codes from Russian color text."""
    if not color_ru:
        return None
    cleaned = color_ru.strip()
    if paint_code:
        escaped = re.escape(paint_code.strip())
        cleaned = re.sub(rf"\s*[\(\[]?\s*{escaped}\s*[\)\]]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\([A-Z0-9]{2,5}\)\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ,-/")
    return cleaned or None


def derive_structural_risk_flags(
    *,
    llm_pillar_or_frame: bool,
    llm_core_support: bool,
    inspector_notes_raw: list[str],
    inspector_notes_ru: list[str],
    defect_texts: list[str],
) -> tuple[bool, bool]:
    """Deterministically refine structural risk flags based on Japanese notes and repair codes."""
    all_raw = " | ".join(inspector_notes_raw)
    all_text = " | ".join([*inspector_notes_raw, *inspector_notes_ru, *defect_texts])

    has_pillar_keyword = bool(_PILLAR_OR_FRAME_RE.search(all_text))
    has_inside_panel_only = bool(_INSIDE_PANEL_ONLY_RE.search(all_raw)) and not has_pillar_keyword

    if has_pillar_keyword and not _NO_ANOMALY_RE.search(all_text):
        pillar_or_frame = True
    elif has_inside_panel_only:
        pillar_or_frame = False
    else:
        pillar_or_frame = llm_pillar_or_frame and not _NO_ANOMALY_RE.search(all_raw)

    core_lines = [line for line in [*inspector_notes_raw, *inspector_notes_ru, *defect_texts] if _CORE_SUPPORT_RE.search(line)]
    if core_lines:
        core_support = any(_REPAIR_ACTION_RE.search(line) and not _NO_ANOMALY_RE.search(line) for line in core_lines)
    else:
        core_support = False if _NO_ANOMALY_RE.search(all_raw) else llm_core_support

    return pillar_or_frame, core_support
