"""Static brand/model slug tables, regex rules, and pure normalization helpers for Drom."""

from __future__ import annotations

import re

from apps.integrations.shared import aliases as _shared_aliases

_BRAND_ALIASES = _shared_aliases.CANONICAL_BRAND_SLUGS
_CYRILLIC_TRANSLIT = _shared_aliases.CYRILLIC_TRANSLIT
_TRIM_NOISE_WORDS = _shared_aliases.TRIM_NOISE_WORDS
_transliterate_cyrillic = _shared_aliases.transliterate_cyrillic

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


def normalize_slug(value: str) -> str:
    """Normalize a brand or model string into a non-empty URL-safe Drom slug."""
    transliterated = _transliterate_cyrillic(value.strip())
    cleaned = re.sub(r"[^a-z0-9\-\s_]+", " ", transliterated)
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_-")
    return cleaned or "auto"


def _alnum_key(value: str) -> str:
    transliterated = _transliterate_cyrillic(value.strip()).replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", "", transliterated)


__all__ = [
    "DEFAULT_MODEL_ALIASES",
    "_BRAND_ALIASES",
    "_CYRILLIC_TRANSLIT",
    "_DEFAULT_FRAME_TYPES",
    "_MAKE_REGEX_RULES",
    "_SUBMODEL_CONFLICT_TOKENS",
    "_TRIM_NOISE_WORDS",
    "_alnum_key",
    "_transliterate_cyrillic",
    "normalize_slug",
]
