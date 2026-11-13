import json
import re
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.core.enums import PowerHpSource
from apps.lots.integrations.drom.cache import read_drom_cache, write_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
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


def normalize_katashiki_candidates(model_code: str | None) -> list[str]:
    """Generate ordered candidate chassis codes (exact, unprefixed, base)."""
    if not model_code:
        return []
    raw = model_code.strip().upper()
    if not raw:
        return []

    candidates: list[str] = [raw]
    parts = [p for p in raw.split("-") if p]
    # Handle both "3BA-NRE210W" (parts[1]) and "3BA-NRE210W-AWXNB" (parts[1]).
    base = (parts[1] if len(parts[0]) <= 3 else parts[0]) if len(parts) >= 2 else raw

    if base not in candidates:
        candidates.append(base)

    # Strip trailing single body letter (e.g. NRE210W -> NRE210, NZE161G -> NZE161).
    stripped = re.sub(r"[A-Z]$", "", base)
    if stripped and len(stripped) >= 3 and stripped not in candidates:
        candidates.append(stripped)

    return candidates


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
            entry_cc = entry.get("engine_cc")
            if (
                engine_cc is not None
                and engine_cc > 0
                and entry_cc is not None
                and abs(int(entry_cc) - engine_cc) > _MAX_ENGINE_CC_DELTA
            ):
                continue
            entry_fuel = entry.get("fuel_type")
            if fuel_type and entry_fuel and entry_fuel != fuel_type:
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

        cached_payload = read_drom_cache(cache_key, allow_stale=False)
        if cached_payload is not None:
            return _deserialize_specs(cached_payload.get("specs", []))

        model_url = _CATALOG_MODEL_URL.format(make_slug=make_slug, model_slug=model_slug)
        try:
            try:
                model_html = self._client.get_html(model_url)
            except DromNotFoundError:
                api_slug = self._slug_resolver.resolve_via_api(make, model)
                if api_slug is None or api_slug.model_slug == model_slug:
                    return []
                model_url = _CATALOG_MODEL_URL.format(
                    make_slug=api_slug.make_slug, model_slug=api_slug.model_slug
                )
                model_html = self._client.get_html(model_url)
        except DromBlockedError:
            stale_payload = read_drom_cache(cache_key, allow_stale=True)
            if stale_payload is not None:
                return _deserialize_specs(stale_payload.get("specs", []))
            return []
        except DromFetchError:
            stale_payload = read_drom_cache(cache_key, allow_stale=True)
            if stale_payload is not None:
                return _deserialize_specs(stale_payload.get("specs", []))
            return []

        gen_urls = parse_catalog_generations(model_html, model_code=model_code)
        specs: list[DromCatalogSpec] = []
        for gen_url in gen_urls[:_MAX_GENERATIONS_TO_FETCH]:
            try:
                gen_html = self._client.get_html(gen_url)
            except DromBlockedError:
                break
            except DromFetchError:
                continue
            specs.extend(parse_catalog_power_specs(gen_html))

        if specs:
            write_drom_cache(
                cache_key,
                {"specs": [_serialize_spec(s) for s in specs]},
                ttl=_CATALOG_TTL,
            )
            return specs

        stale_payload = read_drom_cache(cache_key, allow_stale=True)
        if stale_payload is not None:
            return _deserialize_specs(stale_payload.get("specs", []))
        return []


def _matches_code_token(spec_code: str, candidate: str) -> bool:
    pattern = rf"(?<![A-Z0-9]){re.escape(candidate)}(?![A-Z0-9])"
    return bool(re.search(pattern, spec_code.upper()))


def _select_best_power_hp(
    specs: list[DromCatalogSpec],
    *,
    model_code: str | None,
    engine_cc: int | None,
    fuel_type: str | None,
    drive_type: str | None,
    year: int | None,
) -> int | None:
    pool = list(specs)
    candidates = normalize_katashiki_candidates(model_code)
    if candidates:
        # Match strictly in priority order (exact -> unprefixed -> body-letter stripped).
        tier_matched: list[DromCatalogSpec] = []
        for cand in candidates:
            matched = [s for s in pool if _matches_code_token(s.model_code, cand)]
            if matched:
                tier_matched = matched
                break
        if not tier_matched:
            return None
        pool = tier_matched

    if engine_cc is not None and engine_cc > 0:
        pool = [
            s
            for s in pool
            if s.engine_cc is not None and abs(s.engine_cc - engine_cc) <= _MAX_ENGINE_CC_DELTA
        ]
        if not pool:
            return None

    if fuel_type:
        pool = [s for s in pool if s.fuel_type is None or s.fuel_type == fuel_type]
        if not pool:
            return None

    if drive_type:
        drive_matched = [s for s in pool if s.drive_type == drive_type]
        if drive_matched:
            pool = drive_matched

    if year:
        year_matched = [
            s
            for s in pool
            if (s.year_start is None or s.year_start <= year)
            and (s.year_end is None or s.year_end >= year)
        ]
        if year_matched:
            pool = year_matched

    if not pool:
        return None
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
