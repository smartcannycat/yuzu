"""Deterministic normalizers for Japanese auction sheet codes, dates, and defects."""

import re
import unicodedata

from ml_service.domains.enums import AuctionHouse, FrameIdConfidence
from ml_service.factories.date_normalizer import (
    KANJI_DIGITS,
    calculate_age_and_corridor,
    parse_japanese_date,
)
from ml_service.factories.defect_normalizer import (
    DEFECT_ITEM_RE,
    build_defect_description_ru,
    derive_structural_risk_flags,
    normalize_body_panel,
    parse_defect_codes_with_warnings,
    split_defect_codes,
)

CHASSIS_RE = re.compile(r"^(?:[A-Z0-9]{2,7}-\d{4,8}|\d{6,8}|[A-HJ-NPR-Z0-9]{17})$")
KATASHIKI_RE = re.compile(r"^(?:[A-Z0-9]{1,4}-)?[A-Z0-9]{2,8}(?:-[A-Z0-9]{1,5})?$")
EMISSION_PREFIX_RE = re.compile(r"^[0-9A-Z]{1,4}-")
CHASSIS_CANONICAL_RE = re.compile(r"^[A-Z0-9]{2,8}-\d{4,8}$")

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
        if phrase_upper in compact_jp.upper() or re.search(
            rf"(?<![A-Z0-9]){re.escape(phrase_upper)}(?![A-Z0-9])", upper_spaced
        ):
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

    if c.isdigit() and m:
        parts = [part for part in m.split("-") if part]
        base = ""
        if len(parts) >= 2:
            for part in parts[1:]:
                if re.fullmatch(r"[A-Z]{1,5}\d{1,4}[A-Z]{0,2}", part):
                    base = part
                    break
        if not base and parts:
            base = (
                parts[0]
                if len(parts) >= 2 and re.fullmatch(r"[A-Z]{1,5}\d{1,4}[A-Z]{0,2}", parts[0])
                else EMISSION_PREFIX_RE.sub("", m)
            )
        core_code = re.sub(r"(?<=\d)[A-Z]$", "", base)
        if core_code:
            return f"{core_code}-{c}", FrameIdConfidence.SYNTHESIZED

    return c, FrameIdConfidence.RAW


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


__all__ = [
    "AUCTION_STRICTNESS",
    "CHASSIS_CANONICAL_RE",
    "CHASSIS_RE",
    "DEFECT_ITEM_RE",
    "EMISSION_PREFIX_RE",
    "KANJI_DIGITS",
    "KATASHIKI_RE",
    "build_defect_description_ru",
    "calculate_age_and_corridor",
    "clean_code",
    "clean_color_ru",
    "derive_structural_risk_flags",
    "normalize_auction_house",
    "normalize_body_panel",
    "normalize_transmission_ru",
    "parse_defect_codes_with_warnings",
    "parse_japanese_date",
    "split_defect_codes",
    "synthesize_frame_id",
]
