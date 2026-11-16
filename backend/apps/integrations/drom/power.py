"""Drom catalog power_hp lookup service."""

from datetime import timedelta

from apps.core.enums import PowerHpSource
from apps.integrations.drom.cache import fetch_with_drom_cache
from apps.integrations.drom.client import DromHttpClient
from apps.integrations.drom.katashiki import normalize_katashiki_candidates
from apps.integrations.drom.parser import (
    parse_catalog_generations,
    parse_catalog_power_specs,
)
from apps.integrations.drom.power_filters import (
    deserialize_specs,
    select_best_power_hp,
    serialize_spec,
)
from apps.integrations.drom.schemas import (
    DromBlockedError,
    DromCatalogSpec,
    DromFetchError,
    DromNotFoundError,
    DromPowerResult,
)
from apps.integrations.drom.slugs import DromSlugResolver

_select_best_power_hp = select_best_power_hp
_CATALOG_MODEL_URL = "https://www.drom.ru/catalog/{make_slug}/{model_slug}/"
_CATALOG_TTL = timedelta(days=14)
_MAX_GENERATIONS_TO_FETCH = 3

__all__ = [
    "DromPowerResolver",
    "normalize_katashiki_candidates",
]


class DromPowerResolver:
    """Resolve engine power_hp via drom.ru/catalog/ backed by ExternalCache."""

    def __init__(
        self,
        client: DromHttpClient,
        slug_resolver: DromSlugResolver,
    ) -> None:
        self._client = client
        self._slug_resolver = slug_resolver

    def resolve(
        self,
        *,
        make: str,
        model: str,
        model_code: str | None = None,
        engine_cc: int | None = None,
        fuel_type: str | None = None,
        drive_type: str | None = None,
        year: int | None = None,
        trim: str | None = None,
    ) -> DromPowerResult:
        """Resolve power_hp from drom.ru/catalog/ specifications."""
        from_catalog = self._lookup_drom_catalog(
            make=make,
            model=model,
            model_code=model_code,
            engine_cc=engine_cc,
            fuel_type=fuel_type,
            drive_type=drive_type,
            year=year,
            trim=trim,
        )
        if from_catalog is not None:
            return from_catalog

        return DromPowerResult(power_hp=None, power_hp_source=None)

    def _lookup_drom_catalog(
        self,
        *,
        make: str,
        model: str,
        model_code: str | None,
        engine_cc: int | None,
        fuel_type: str | None,
        drive_type: str | None,
        year: int | None,
        trim: str | None = None,
    ) -> DromPowerResult | None:
        resolved = self._slug_resolver.resolve_catalog_slug(make, model)
        specs = self._fetch_catalog_specs(
            make=make,
            model=model,
            make_slug=resolved.make_slug,
            model_slug=resolved.model_slug,
            model_code=model_code,
        )
        if not specs:
            return None

        best_hp = select_best_power_hp(
            specs,
            model=model,
            trim=trim,
            model_code=model_code,
            engine_cc=engine_cc,
            fuel_type=fuel_type,
            drive_type=drive_type,
            year=year,
        )
        if best_hp is None:
            return None
        return DromPowerResult(
            power_hp=best_hp,
            power_hp_source=PowerHpSource.DROM_CATALOG,
        )

    def _fetch_catalog_specs(
        self,
        *,
        make: str,
        model: str,
        make_slug: str,
        model_slug: str,
        model_code: str | None,
    ) -> list[DromCatalogSpec]:
        candidates = normalize_katashiki_candidates(model_code)
        code_key = (
            candidates[1] if len(candidates) > 1 else (candidates[0] if candidates else "all")
        )
        cache_key = f"drom:catalog:{make_slug}:{model_slug}:{code_key}"[:512]
        partial_failure = False

        def _fetch_live() -> list[DromCatalogSpec]:
            nonlocal partial_failure
            model_html = self._fetch_catalog_model_html(
                make=make,
                model=model,
                make_slug=make_slug,
                model_slug=model_slug,
            )
            if model_html is None:
                return []
            gen_urls = parse_catalog_generations(model_html, model_code=model_code)
            specs, complete = self._fetch_generation_specs(gen_urls[:_MAX_GENERATIONS_TO_FETCH])
            partial_failure = not complete
            return specs

        specs, _ = fetch_with_drom_cache(
            cache_key,
            fetcher=_fetch_live,
            serialize=lambda items: {"specs": [serialize_spec(s) for s in items]},
            deserialize=lambda payload: deserialize_specs(payload.get("specs", [])),
            ttl=_CATALOG_TTL,
            is_cacheable=lambda items: bool(items) and not partial_failure,
            fallback_to_stale_on_empty=True,
        )
        return specs or []

    def _fetch_catalog_model_html(
        self,
        *,
        make: str,
        model: str,
        make_slug: str,
        model_slug: str,
    ) -> str | None:
        model_url = _CATALOG_MODEL_URL.format(make_slug=make_slug, model_slug=model_slug)
        try:
            return self._client.get_html(
                model_url,
                expected_path_parts=(
                    "/catalog/",
                    f"/{make_slug.lower()}/",
                    f"/{model_slug.lower()}/",
                ),
            )
        except DromNotFoundError:
            api_slug = self._slug_resolver.resolve_catalog_via_api(make, model)
            if api_slug is None or (
                api_slug.make_slug == make_slug and api_slug.model_slug == model_slug
            ):
                return None
            fallback_url = _CATALOG_MODEL_URL.format(
                make_slug=api_slug.make_slug,
                model_slug=api_slug.model_slug,
            )
            try:
                return self._client.get_html(
                    fallback_url,
                    expected_path_parts=(
                        "/catalog/",
                        f"/{api_slug.make_slug.lower()}/",
                        f"/{api_slug.model_slug.lower()}/",
                    ),
                )
            except DromNotFoundError:
                return None

    def _fetch_generation_specs(self, gen_urls: list[str]) -> tuple[list[DromCatalogSpec], bool]:
        specs: list[DromCatalogSpec] = []
        complete = True
        for gen_url in gen_urls:
            try:
                gen_html = self._client.get_html(gen_url)
            except DromBlockedError:
                raise
            except DromFetchError:
                complete = False
                continue
            specs.extend(parse_catalog_power_specs(gen_html))
        return specs, complete
