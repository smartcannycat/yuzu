"""Factories layer: deterministic normalization, markdown rendering, and sheet assembly."""

from ml_service.factories.markdown_renderer import render_markdown
from ml_service.factories.normalizers import (
    AUCTION_STRICTNESS,
    CHASSIS_CANONICAL_RE,
    CHASSIS_RE,
    DEFECT_ITEM_RE,
    EMISSION_PREFIX_RE,
    KANJI_DIGITS,
    KATASHIKI_RE,
    calculate_age_and_corridor,
    clean_code,
    normalize_auction_house,
    parse_japanese_date,
    split_defect_codes,
    synthesize_frame_id,
)
from ml_service.factories.sheet_factory import SheetFactory

__all__ = [
    "AUCTION_STRICTNESS",
    "CHASSIS_CANONICAL_RE",
    "CHASSIS_RE",
    "DEFECT_ITEM_RE",
    "EMISSION_PREFIX_RE",
    "KANJI_DIGITS",
    "KATASHIKI_RE",
    "SheetFactory",
    "calculate_age_and_corridor",
    "clean_code",
    "normalize_auction_house",
    "parse_japanese_date",
    "render_markdown",
    "split_defect_codes",
    "synthesize_frame_id",
]
