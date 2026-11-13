import json
from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.core.enums import PowerHpSource
from apps.lots.integrations.drom.cache import fetch_with_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.katashiki import (
    matches_katashiki_token,
    normalize_katashiki_candidates,
)
from apps.lots.integrations.drom.parser import (
    parse_catalog_generations,
    parse_catalog_power_specs,
)
from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromCatalogSpec,
    DromFetchError,
    DromNotFoundError,
    DromPowerResult,
)
from apps.lots.integrations.drom.slugs import DromSlugResolver

_KATASHIKI_PATH = Path(__file__).resolve().parent / "data" / "katashiki_power.json"
_CATALOG_MODEL_URL = "https://www.drom.ru/catalog/{make_slug}/{model_slug}/"
_CATALOG_TTL = timedelta(days=14)
_MAX_GENERATIONS_TO_FETCH = 3
_MAX_ENGINE_CC_DELTA = 250


@lru_cache(maxsize=1)
def _load_katashiki_table() -> dict[str, dict[str, Any]]:
    with _KATASHIKI_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {str(k).upper(): v for k, v in data.items() if isinstance(v, dict)}


class DromPowerResolver:
    """Resolve engine power_hp via katashiki_cache first, then drom.ru/catalog/."""

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
    ) -> DromPowerResult:
        """Resolve power_hp from katashiki_cache, falling back to drom.ru/catalog/."""
        from_cache = self._lookup_katashiki_cache(
            model_code=model_code,
            engine_cc=engine_cc,
            fuel_type=fuel_type,
        )
        if from_cache is not None:
            return from_cache

        from_catalog = self._lookup_drom_catalog(
            make=make,
            model=model,
            model_code=model_code,
            engine_cc=engine_cc,
            fuel_type=fuel_type,
            drive_type=drive_type,
            year=year,
        )
        if from_catalog is not None:
            return from_catalog

        return DromPowerResult(power_hp=None, power_hp_source=None)

    def _lookup_katashiki_cache(
        self,
        *,
        model_code: str | None,
        engine_cc: int | None,
        fuel_type: str | None,
    ) -> DromPowerResult | None:
        table = _load_katashiki_table()
        for candidate in normalize_katashiki_candidates(model_code):
            entry = table.get(candidate)
            if not entry or "power_hp" not in entry:
                continue
            if not _katashiki_entry_matches(entry, engine_cc=engine_cc, fuel_type=fuel_type):
                continue
            return DromPowerResult(
                power_hp=int(entry["power_hp"]),
                power_hp_source=PowerHpSource.KATASHIKI_CACHE,
            )
        return None

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
    ) -> DromPowerResult | None:
        resolved = self._slug_resolver.resolve(make, model)
        specs = self._fetch_catalog_specs(
            make=make,
            model=model,
            make_slug=resolved.make_slug,
            model_slug=resolved.model_slug,
            model_code=model_code,
        )
        if not specs:
            return None

        best_hp = _select_best_power_hp(
            specs,
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
        code_key = candidates[-1] if candidates else "all"
        cache_key = f"drom:catalog:{make_slug}:{model_slug}:{code_key}"[:512]

        def _fetch_live() -> list[DromCatalogSpec]:
            model_html = self._fetch_catalog_model_html(
                make=make,
                model=model,
                make_slug=make_slug,
                model_slug=model_slug,
            )
            if model_html is None:
                return []
            gen_urls = parse_catalog_generations(model_html, model_code=model_code)
            return self._fetch_generation_specs(gen_urls[:_MAX_GENERATIONS_TO_FETCH])

        specs, _ = fetch_with_drom_cache(
            cache_key,
            fetcher=_fetch_live,
            serialize=lambda items: {"specs": [_serialize_spec(s) for s in items]},
            deserialize=lambda payload: _deserialize_specs(payload.get("specs", [])),
            ttl=_CATALOG_TTL,
            is_cacheable=bool,
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
            catalog_slug = self._slug_resolver.resolve_catalog_slug(make, model)
            if catalog_slug is None or (
                catalog_slug.make_slug == make_slug and catalog_slug.model_slug == model_slug
            ):
                return None
            fallback_url = _CATALOG_MODEL_URL.format(
                make_slug=catalog_slug.make_slug,
                model_slug=catalog_slug.model_slug,
            )
            return self._client.get_html(
                fallback_url,
                expected_path_parts=(
                    "/catalog/",
                    f"/{catalog_slug.make_slug.lower()}/",
                    f"/{catalog_slug.model_slug.lower()}/",
                ),
            )

    def _fetch_generation_specs(self, gen_urls: list[str]) -> list[DromCatalogSpec]:
        specs: list[DromCatalogSpec] = []
        for gen_url in gen_urls:
            try:
                gen_html = self._client.get_html(gen_url)
            except DromBlockedError:
                break
            except DromFetchError:
                continue
            specs.extend(parse_catalog_power_specs(gen_html))
        return specs


def _katashiki_entry_matches(
    entry: dict[str, Any],
    *,
    engine_cc: int | None,
    fuel_type: str | None,
) -> bool:
    entry_cc = entry.get("engine_cc")
    if (
        engine_cc is not None
        and engine_cc > 0
        and entry_cc is not None
        and abs(int(entry_cc) - engine_cc) > _MAX_ENGINE_CC_DELTA
    ):
        return False
    entry_fuel = entry.get("fuel_type")
    return not (fuel_type and entry_fuel and entry_fuel != fuel_type)


def _filter_specs_by_katashiki(
    specs: list[DromCatalogSpec],
    model_code: str | None,
) -> list[DromCatalogSpec]:
    candidates = normalize_katashiki_candidates(model_code)
    if not candidates:
        return specs
    # Match strictly in priority order (exact -> unprefixed -> body-letter stripped).
    for cand in candidates:
        matched = [s for s in specs if matches_katashiki_token(s.model_code, cand)]
        if matched:
            return matched
    return []


def _filter_specs_by_engine_cc(
    specs: list[DromCatalogSpec],
    engine_cc: int | None,
) -> list[DromCatalogSpec]:
    if engine_cc is None or engine_cc <= 0:
        return specs
    return [
        s
        for s in specs
        if s.engine_cc is not None and abs(s.engine_cc - engine_cc) <= _MAX_ENGINE_CC_DELTA
    ]


def _filter_specs_by_fuel_type(
    specs: list[DromCatalogSpec],
    fuel_type: str | None,
) -> list[DromCatalogSpec]:
    if not fuel_type:
        return specs
    return [s for s in specs if s.fuel_type is None or s.fuel_type == fuel_type]


def _prefer_specs_matching(
    specs: list[DromCatalogSpec],
    predicate: Callable[[DromCatalogSpec], bool],
) -> list[DromCatalogSpec]:
    matched = [s for s in specs if predicate(s)]
    return matched if matched else specs


def _select_best_power_hp(
    specs: list[DromCatalogSpec],
    *,
    model_code: str | None,
    engine_cc: int | None,
    fuel_type: str | None,
    drive_type: str | None,
    year: int | None,
) -> int | None:
    pool = _filter_specs_by_katashiki(list(specs), model_code)
    if not pool:
        return None
    pool = _filter_specs_by_engine_cc(pool, engine_cc)
    if not pool:
        return None
    pool = _filter_specs_by_fuel_type(pool, fuel_type)
    if not pool:
        return None

    if drive_type:
        pool = _prefer_specs_matching(pool, lambda s: s.drive_type == drive_type)
    if year:
        pool = _prefer_specs_matching(
            pool,
            lambda s: (
                (s.year_start is None or s.year_start <= year)
                and (s.year_end is None or s.year_end >= year)
            ),
        )

    # Conservative choice for the 160 hp utilization fee threshold.
    return max(s.power_hp for s in pool)


def _serialize_spec(spec: DromCatalogSpec) -> dict[str, Any]:
    return {
        "model_code": spec.model_code,
        "power_hp": spec.power_hp,
        "engine_cc": spec.engine_cc,
        "fuel_type": spec.fuel_type,
        "drive_type": spec.drive_type,
        "year_start": spec.year_start,
        "year_end": spec.year_end,
    }


def _deserialize_specs(raw_items: Any) -> list[DromCatalogSpec]:
    if not isinstance(raw_items, list):
        return []
    specs: list[DromCatalogSpec] = []
    for item in raw_items:
        if not isinstance(item, dict) or "power_hp" not in item or "model_code" not in item:
            continue
        specs.append(
            DromCatalogSpec(
                model_code=str(item["model_code"]),
                power_hp=int(item["power_hp"]),
                engine_cc=item.get("engine_cc"),
                fuel_type=item.get("fuel_type"),
                drive_type=item.get("drive_type"),
                year_start=item.get("year_start"),
                year_end=item.get("year_end"),
            )
        )
    return specs
