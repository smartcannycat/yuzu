"""Catalog specification filters, trim selection, and cache serialization helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from apps.integrations.drom.katashiki import (
    matches_katashiki_token,
    normalize_katashiki_candidates,
)
from apps.integrations.drom.schemas import DromCatalogSpec

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_ENGINE_CC_DELTA = 250

_SPECIAL_PERF_TRIM_MARKERS: tuple[str, ...] = (
    "touring",
    "turbo",
    "modulo",
    "type r",
    "sti",
    "nismo",
)

_IGNORED_TRIM_TOKENS = frozenset(
    {"honda", "sensing", "hybrid", "4wd", "2wd", "just", "selection", "flex"}
)


def _filter_specs_by_katashiki(
    specs: list[DromCatalogSpec],
    model_code: str | None,
) -> list[DromCatalogSpec]:
    candidates = normalize_katashiki_candidates(model_code)
    if not candidates:
        return specs
    for cand in candidates:
        matched = [s for s in specs if matches_katashiki_token(s.model_code, cand)]
        if matched:
            return matched
    if len(candidates) >= 3:
        matched = [
            s
            for s in specs
            if matches_katashiki_token(s.model_code, candidates[-1], allow_body_suffix=True)
        ]
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
    *,
    has_katashiki_match: bool = False,
) -> list[DromCatalogSpec]:
    if not fuel_type:
        return specs
    exact = [s for s in specs if s.fuel_type is None or s.fuel_type == fuel_type]
    if exact:
        return exact
    if has_katashiki_match and fuel_type == "gasoline":
        return [s for s in specs if s.fuel_type == "hybrid"]
    return []


def _prefer_specs_matching(
    specs: list[DromCatalogSpec],
    predicate: Callable[[DromCatalogSpec], bool],
) -> list[DromCatalogSpec]:
    matched = [s for s in specs if predicate(s)]
    return matched if matched else specs


def _prefer_specs_by_trim(
    specs: list[DromCatalogSpec],
    model: str | None,
    trim: str | None = None,
) -> list[DromCatalogSpec]:
    if (not model and not trim) or len({s.power_hp for s in specs}) <= 1:
        return specs
    model_lower = (model or "").lower()
    trim_lower = (trim or "").lower()
    combined_lower = f"{model_lower} {trim_lower}".strip()

    model_tokens = [
        t
        for t in re.split(r"[\s_\-/]+", model_lower)
        if len(t) >= 2 and t not in _IGNORED_TRIM_TOKENS
    ][1:]
    trim_tokens = [
        t
        for t in re.split(r"[\s_\-/]+", trim_lower)
        if len(t) >= 2 and t not in _IGNORED_TRIM_TOKENS
    ]
    for token in [*model_tokens, *trim_tokens]:
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
        matched = [s for s in specs if s.trim_text and re.search(pattern, s.trim_text)]
        if matched:
            specs = matched
    if not any(marker in combined_lower for marker in _SPECIAL_PERF_TRIM_MARKERS):
        standard = [
            s
            for s in specs
            if not s.trim_text
            or not any(marker in s.trim_text for marker in _SPECIAL_PERF_TRIM_MARKERS)
        ]
        if standard:
            specs = standard
    return specs


def select_best_power_hp(
    specs: list[DromCatalogSpec],
    *,
    model: str | None = None,
    trim: str | None = None,
    model_code: str | None,
    engine_cc: int | None,
    fuel_type: str | None,
    drive_type: str | None,
    year: int | None,
) -> int | None:
    """Filter parsed catalog specs to the closest vehicle match and return max HP."""
    pool = _filter_specs_by_katashiki(list(specs), model_code)
    if not pool:
        return None
    pool = _filter_specs_by_engine_cc(pool, engine_cc)
    if not pool:
        return None
    has_code = bool(normalize_katashiki_candidates(model_code))
    pool = _filter_specs_by_fuel_type(pool, fuel_type, has_katashiki_match=has_code)
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
    pool = _prefer_specs_by_trim(pool, model, trim)
    return max(s.power_hp for s in pool)


def serialize_spec(spec: DromCatalogSpec) -> dict[str, Any]:
    return {
        "model_code": spec.model_code,
        "power_hp": spec.power_hp,
        "engine_cc": spec.engine_cc,
        "fuel_type": spec.fuel_type,
        "drive_type": spec.drive_type,
        "year_start": spec.year_start,
        "year_end": spec.year_end,
        "trim_text": spec.trim_text,
    }


def deserialize_specs(raw_items: Any) -> list[DromCatalogSpec]:
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
                trim_text=item.get("trim_text"),
            )
        )
    return specs
