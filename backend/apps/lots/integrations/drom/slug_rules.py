"""Static brand/model slug tables, regex rules, and pure normalization helpers for Drom."""

from __future__ import annotations

import re

_CYRILLIC_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

DEFAULT_MODEL_ALIASES: dict[str, tuple[str, str | None]] = {
    "corolla touring": ("corolla", "универсал"),
    "corolla touring hybrid": ("corolla", "универсал"),
    "corolla sport": ("corolla", "хэтчбек 5 дв."),
    "impreza sport": ("impreza", "хэтчбек 5 дв."),
    "impreza g4": ("impreza", "седан"),
    "impreza anesis": ("impreza", "седан"),
    "impreza xv": ("xv", None),
    "note aura": ("aura", None),
    "prius a": ("prius_a", None),
    "prius alpha": ("prius_a", None),
    "prius α": ("prius_a", None),
    "every van": ("every", None),
}

_DEFAULT_FRAME_TYPES: dict[str, int] = {
    "универсал": 3,
    "хэтчбек 5 дв.": 5,
    "седан": 10,
}

_BRAND_ALIASES: dict[str, str] = {
    "mercedes": "mercedes-benz",
    "мерседес": "mercedes-benz",
    "мерседес бенц": "mercedes-benz",
    "мерседес-бенц": "mercedes-benz",
    "vw": "volkswagen",
    "фольксваген": "volkswagen",
    "бмв": "bmw",
    "мини": "mini",
}

_MB_SERIES_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^eq([es])\s*-?\s*\d{2,3}.*\bsuv\b"), r"eq\1_suv"),
    (re.compile(r"^eq([abcesv])\s*-?\s*\d{2,3}(?!\d)"), r"eq\1"),
    (re.compile(r"^cla\s*-?\s*\d{2,3}"), "cla-class"),
    (re.compile(r"^cls\s*-?\s*\d{2,3}"), "cls-class"),
    (re.compile(r"^clc\s*-?\s*\d{2,3}"), "clc-class"),
    (re.compile(r"^clk\s*-?\s*\d{2,3}"), "clk-class"),
    (re.compile(r"^cle\s*-?\s*\d{2,3}"), "cle-class"),
    (re.compile(r"^gla\s*-?\s*\d{2,3}"), "gla-class"),
    (re.compile(r"^glb\s*-?\s*\d{2,3}"), "glb"),
    (re.compile(r"^glc\s*-?\s*\d{2,3}.*coupe"), "glc_coupe"),
    (re.compile(r"^glc\s*-?\s*\d{2,3}"), "glc-class"),
    (re.compile(r"^gle\s*-?\s*\d{2,3}.*coupe"), "gle_coupe"),
    (re.compile(r"^gle\s*-?\s*\d{2,3}"), "gle-class"),
    (re.compile(r"^glk\s*-?\s*\d{2,3}"), "glk-class"),
    (re.compile(r"^gls\s*-?\s*\d{2,3}"), "gls-class"),
    (re.compile(r"^slk\s*-?\s*\d{2,3}"), "slk-class"),
    (re.compile(r"^slc\s*-?\s*\d{2,3}"), "slc-class"),
    (re.compile(r"^ml\s*-?\s*\d{2,3}"), "m-class"),
    (re.compile(r"^gl\s*-?\s*\d{2,3}"), "gl-class"),
    (re.compile(r"^sl\s*-?\s*\d{2,3}"), "sl-class"),
    (re.compile(r"^cl\s*-?\s*\d{2,3}"), "cl-class"),
    (re.compile(r"^([abcegrsvx])\s*-?\s*\d{2,3}(?!\d)"), r"\1-class"),
)

_MAKE_REGEX_RULES: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "mercedes-benz": _MB_SERIES_RULES,
    "bmw": (
        (re.compile(r"^2\d{2}[a-z]*.*active\s*tourer"), "2-series_active_tourer"),
        (re.compile(r"^2\d{2}[a-z]*.*gran\s*tourer"), "2-series_gran_tourer"),
        (re.compile(r"^([356])\d{2}[a-z]*.*gran\s*turismo"), r"\1-series_gran_turismo"),
        (re.compile(r"^m?([1-8])\d{2}(?:[a-z]+)?(?:\b|$)"), r"\1-series"),
    ),
    "mini": (
        (
            re.compile(
                r"^(?:mini\s+)?(?:john\s+cooper\s+works|cooper(?:\s+[sd])?|one(?:\s+d)?|jcw)\b"
            ),
            "hatch",
        ),
    ),
}

_TRIM_NOISE_WORDS = frozenset(
    {"hybrid", "hv", "e-power", "epower", "4wd", "2wd", "turbo", "wxb", "w×b"}
)

# Tokens that denote a distinct model/body line on Drom and must not be dropped
# when collapsing a multi-word model name onto a shorter base model.
_SUBMODEL_CONFLICT_TOKENS = frozenset(
    {
        "cross",
        "type",
        "r",
        "alpha",
        "plus",
        "slash",
        "van",
        "wagon",
        "truck",
        "latio",
        "axio",
        "fielder",
        "rumion",
        "spacio",
        "verso",
        "allroad",
        "shuttle",
        "spike",
        "aria",
        "phv",
        "prime",
        "gr",
        "sti",
        "wrx",
    }
)


def _transliterate_cyrillic(value: str) -> str:
    return "".join(_CYRILLIC_TRANSLIT.get(ch, ch) for ch in value.lower())


def normalize_slug(value: str) -> str:
    """Normalize a brand or model string into a non-empty URL-safe Drom slug."""
    transliterated = _transliterate_cyrillic(value.strip())
    cleaned = re.sub(r"[^a-z0-9\-\s_]+", " ", transliterated)
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_-")
    return cleaned or "auto"


def _alnum_key(value: str) -> str:
    transliterated = _transliterate_cyrillic(value.strip()).replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", "", transliterated)
