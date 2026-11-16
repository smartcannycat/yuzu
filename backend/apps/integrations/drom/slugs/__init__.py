"""Drom brand and model slug resolution package."""

from apps.integrations.drom.slug_rules import DEFAULT_MODEL_ALIASES, normalize_slug
from apps.integrations.drom.slugs.aliases import (
    ResolvedDromSlug,
    _load_drom_schema,
    _pick_best_brand_slug,
    _pick_best_model_name,
    _pick_best_model_slug,
    load_drom_schema,
)
from apps.integrations.drom.slugs.resolver import DromSlugResolver

__all__ = [
    "DEFAULT_MODEL_ALIASES",
    "DromSlugResolver",
    "ResolvedDromSlug",
    "_load_drom_schema",
    "_pick_best_brand_slug",
    "_pick_best_model_name",
    "_pick_best_model_slug",
    "load_drom_schema",
    "normalize_slug",
]
