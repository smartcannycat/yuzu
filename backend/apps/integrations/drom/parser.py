"""Public facade re-exporting Drom HTML/SSR parsers."""

from apps.integrations.drom.catalog_parser import (
    parse_catalog_generations,
    parse_catalog_power_specs,
)
from apps.integrations.drom.directory_parser import (
    extract_bulls_list_ssr_payload,
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)
from apps.integrations.drom.listings_parser import (
    is_antibot_challenge_html,
    parse_listings,
)

__all__ = [
    "extract_bulls_list_ssr_payload",
    "is_antibot_challenge_html",
    "parse_brand_models_from_html",
    "parse_catalog_brands_from_html",
    "parse_catalog_generations",
    "parse_catalog_models_from_html",
    "parse_catalog_power_specs",
    "parse_listings",
]
