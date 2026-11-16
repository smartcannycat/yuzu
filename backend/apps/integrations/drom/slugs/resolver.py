"""Dynamic Drom brand/model slug resolver backed by HTML directories and ExternalCache."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

from apps.integrations.drom.cache import fetch_with_drom_cache
from apps.integrations.drom.parser import (
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)
from apps.integrations.drom.schemas import DromBlockedError
from apps.integrations.drom.slug_rules import _TRIM_NOISE_WORDS, normalize_slug
from apps.integrations.drom.slugs.aliases import (
    ResolvedDromSlug,
    _extract_trivial_models,
    _load_drom_schema,
    _pick_best_brand_slug,
    _pick_best_model_slug,
    _resolve_alias,
    _resolve_make_aware_alias,
    _resolve_make_from_schema,
    _resolve_model_from_schema_dict,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from apps.integrations.drom.client import DromHttpClient

_BRAND_PAGE_URL = "https://auto.drom.ru/{make_slug}/"
_CATALOG_BRANDS_URL = "https://www.drom.ru/catalog/"
_CATALOG_MODEL_LIST_URL = "https://www.drom.ru/catalog/{make_slug}/"
_CATALOG_TTL = timedelta(days=14)


def _unpack_directory_cache(payload: dict | None) -> tuple[list[str], dict[str, str]] | None:
    if payload is None or not isinstance(payload.get("models"), list):
        return None
    raw_slug_map = payload.get("slug_map")
    slug_map = (
        {str(k): str(v) for k, v in raw_slug_map.items()} if isinstance(raw_slug_map, dict) else {}
    )
    return [str(n) for n in payload["models"]], slug_map


class DromSlugResolver:
    """Dynamic Drom brand and model slug resolver backed by Drom HTML catalogs and ExternalCache."""

    def __init__(self, client: DromHttpClient) -> None:
        self._client = client

    def _resolve_from_sales_or_rules(
        self,
        model: str,
        make_slug: str,
        schema: dict[str, Any],
        brand_entry: object,
    ) -> ResolvedDromSlug:
        aliased = _resolve_alias(model, make_slug, schema)
        if aliased is not None:
            return aliased

        if isinstance(brand_entry, dict):
            trivial = _extract_trivial_models(brand_entry)
            from_schema = _resolve_model_from_schema_dict(
                model,
                brand_entry.get("sales_models"),
                make_slug,
                trivial_models=trivial,
            )
            if from_schema is not None:
                return from_schema

        make_aliased = _resolve_make_aware_alias(make_slug, model)
        if make_aliased is not None:
            return make_aliased

        return self._fallback_normalized_slug(make_slug, model)

    def resolve(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve sales brand and model from compact Drom schema and structural aliases."""
        schema = _load_drom_schema()
        brands: dict = schema.get("brands") or {}
        make_slug = _resolve_make_from_schema(make, brands)
        return self._resolve_from_sales_or_rules(model, make_slug, schema, brands.get(make_slug))

    def resolve_via_api(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Resolve exact Drom brand and model URL slugs dynamically from live sales pages."""
        return self._resolve_via_directory(make, model, self._get_sales_models)

    def resolve_catalog_slug(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve canonical Drom catalog slug from compact schema."""
        schema = _load_drom_schema()
        brands: dict = schema.get("brands") or {}
        make_slug = _resolve_make_from_schema(make, brands)
        brand_entry = brands.get(make_slug)

        if isinstance(brand_entry, dict):
            from_cat = _resolve_model_from_schema_dict(
                model,
                brand_entry.get("catalog_models"),
                make_slug,
            )
            if from_cat is not None:
                return from_cat

        resolved = self._resolve_from_sales_or_rules(model, make_slug, schema, brand_entry)
        return ResolvedDromSlug(
            make_slug=resolved.make_slug,
            model_slug=resolved.model_slug,
            frame_type_id=None,
            is_fallback_guess=resolved.is_fallback_guess,
        )

    def resolve_catalog_via_api(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Resolve canonical Drom catalog slug dynamically from live drom.ru/catalog/ pages."""
        return self._resolve_via_directory(make, model, self._get_catalog_models)

    @staticmethod
    def _fallback_normalized_slug(make_slug: str, model: str) -> ResolvedDromSlug:
        model_key = re.sub(r"\s+", " ", model.strip().lower())
        words = [w for w in re.split(r"[\s/]+", model_key) if w and w not in _TRIM_NOISE_WORDS]
        stripped_key = " ".join(words)
        return ResolvedDromSlug(
            make_slug=make_slug,
            model_slug=normalize_slug(stripped_key or model_key),
            frame_type_id=None,
            is_fallback_guess=True,
        )

    def _resolve_via_directory(
        self,
        make: str,
        model: str,
        loader: Callable[[str], tuple[list[str], dict[str, str]]],
    ) -> ResolvedDromSlug | None:
        make_slug = _resolve_make_from_schema(make, _load_drom_schema().get("brands") or {})
        names, slug_map = loader(make_slug)

        if not names:
            resolved_make = self._resolve_brand_slug(make)
            if resolved_make and resolved_make != make_slug:
                make_slug = resolved_make
                names, slug_map = loader(make_slug)

        if not names:
            return None

        best_slug = _pick_best_model_slug(model, names, slug_map)
        if best_slug is None:
            return None
        return ResolvedDromSlug(make_slug=make_slug, model_slug=best_slug, frame_type_id=None)

    def _resolve_brand_slug(self, make: str) -> str | None:
        names, slug_map = self._load_or_fetch_directory(
            cache_key="drom:catalog:brands",
            url=_CATALOG_BRANDS_URL,
            expected_path_parts=("/catalog/",),
            extractor=parse_catalog_brands_from_html,
        )
        if not names:
            return None
        return _pick_best_brand_slug(make, names, slug_map)

    def _get_sales_models(self, make_slug: str) -> tuple[list[str], dict[str, str]]:
        return self._load_or_fetch_directory(
            cache_key=f"drom:models:{make_slug}",
            url=_BRAND_PAGE_URL.format(make_slug=make_slug),
            expected_path_parts=(f"/{make_slug.lower()}/",),
            extractor=lambda html: parse_brand_models_from_html(html, make_slug),
            reraise_blocked=True,
        )

    def _get_catalog_models(self, make_slug: str) -> tuple[list[str], dict[str, str]]:
        return self._load_or_fetch_directory(
            cache_key=f"drom:catalog:models:{make_slug}",
            url=_CATALOG_MODEL_LIST_URL.format(make_slug=make_slug),
            expected_path_parts=("/catalog/", f"/{make_slug.lower()}/"),
            extractor=lambda html: parse_catalog_models_from_html(html, make_slug),
        )

    def _load_or_fetch_directory(
        self,
        *,
        cache_key: str,
        url: str,
        expected_path_parts: tuple[str, ...],
        extractor: Callable[[str], tuple[list[str], dict[str, str]]],
        reraise_blocked: bool = False,
    ) -> tuple[list[str], dict[str, str]]:
        result, _ = fetch_with_drom_cache(
            cache_key,
            fetcher=lambda: extractor(
                self._client.get_html(url, expected_path_parts=expected_path_parts)
            ),
            serialize=lambda data: {"models": data[0], "slug_map": data[1]},
            deserialize=_unpack_directory_cache,
            ttl=_CATALOG_TTL,
            is_cacheable=lambda data: bool(data[0]),
            fallback_to_stale_on_empty=False,
            reraise=(DromBlockedError,) if reraise_blocked else (),
        )
        return result if result is not None else ([], {})
