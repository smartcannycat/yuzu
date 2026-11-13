import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from apps.lots.integrations.drom.client import _DEFAULT_HEADERS, _detect_charset
from apps.lots.integrations.drom.directory_parser import _is_seo_label
from apps.lots.integrations.drom.html_utils import extract_bulls_list_ssr_payload
from apps.lots.integrations.drom.parser import (
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)
from apps.lots.integrations.drom.slugs import DEFAULT_MODEL_ALIASES, normalize_slug

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "data" / "drom_schema.json"

_FUEL_LABEL_TO_KEY: dict[str, str] = {
    "бензин": "gasoline",
    "дизель": "diesel",
    "электро": "ev",
    "гибрид": "hybrid",
    "гбо": "lpg",
}


def _parse_drive_unit_key(label: str) -> str | None:
    lower = label.strip().lower()
    if "4wd" in lower:
        return "4WD"
    if "перед" in lower:
        return "FWD"
    if "зад" in lower:
        return "RWD"
    return None


def _extract_filter_schema(html: str) -> dict[str, Any]:
    payload = extract_bulls_list_ssr_payload(html)
    if payload is None:
        return {"fuel_types": {}, "drive_units": {}, "frame_types": {}}

    view = (payload.get("filter") or {}).get("view") or {}

    fuel_types: dict[str, str] = {}
    for item in view.get("fuelTypes") or []:
        if isinstance(item, dict) and item.get("label") and item.get("value"):
            key = _FUEL_LABEL_TO_KEY.get(str(item["label"]).strip().lower())
            if key:
                fuel_types[key] = str(item["value"])

    drive_units: dict[str, str] = {}
    for item in view.get("driveUnits") or []:
        if isinstance(item, dict) and item.get("label") and item.get("value"):
            key = _parse_drive_unit_key(str(item["label"]))
            if key:
                drive_units[key] = str(item["value"])

    frame_types: dict[str, int] = {}
    for item in view.get("frameTypes") or []:
        if isinstance(item, dict) and item.get("title") and item.get("id") is not None:
            frame_types[str(item["title"]).strip().lower()] = int(item["id"])

    return {
        "fuel_types": fuel_types,
        "drive_units": drive_units,
        "frame_types": frame_types,
    }


def _strip_brand_prefix(label: str, brand_name: str) -> str:
    cleaned = label.strip()
    prefix = f"{brand_name.strip()} "
    if brand_name and cleaned.lower().startswith(prefix.lower()):
        stripped = cleaned[len(prefix) :].strip()
        if stripped:
            return stripped
    return cleaned


def compact_brand_models(
    brand_name: str,
    raw_sales: dict[str, str],
    raw_catalog: dict[str, str],
) -> dict[str, Any]:
    """Filter out SEO noise and compact trivial `slug == normalize_slug(name)` entries."""
    clean_sales: dict[str, str] = {}
    trivial_names: set[str] = set()
    for raw_name, slug in sorted(raw_sales.items()):
        name = _strip_brand_prefix(raw_name, brand_name)
        if not name or _is_seo_label(raw_name) or _is_seo_label(name):
            continue
        if normalize_slug(name) != slug:
            clean_sales[name] = slug
        else:
            trivial_names.add(name)

    clean_catalog: dict[str, str] = {}
    for raw_name, slug in sorted(raw_catalog.items()):
        name = _strip_brand_prefix(raw_name, brand_name)
        if not name or _is_seo_label(raw_name) or _is_seo_label(name):
            continue
        sales_slug = clean_sales.get(name, normalize_slug(name))
        if slug != sales_slug:
            clean_catalog[name] = slug
        elif normalize_slug(name) == slug:
            trivial_names.add(name)

    entry: dict[str, Any] = {"name": brand_name}
    if trivial_names:
        entry["models"] = "|".join(sorted(trivial_names))
    if clean_sales:
        entry["sales_models"] = clean_sales
    if clean_catalog:
        entry["catalog_models"] = clean_catalog
    return entry


def _fetch_text(client: httpx.Client, url: str) -> tuple[int, str, str]:
    resp = client.get(url)
    enc = _detect_charset(resp)
    return resp.status_code, str(resp.url), resp.content.decode(enc, errors="replace")


def _scrape_model_map(
    client: httpx.Client,
    *,
    url: str,
    expected_path_part: str,
    extractor: Callable[[str], tuple[list[str], dict[str, str]]],
) -> dict[str, str]:
    models: dict[str, str] = {}
    try:
        status, final_url, html = _fetch_text(client, url)
    except httpx.HTTPError:
        return models
    if status != 200 or expected_path_part not in final_url.lower():
        return models
    names, slug_map = extractor(html)
    for name in names:
        key = name.strip()
        slug = slug_map.get(key.lower())
        if key and slug:
            models[key] = slug
    return models


def _scrape_single_brand(
    make_slug: str,
    brand_name: str,
    timeout_sec: float,
) -> tuple[str, dict[str, Any], bool]:
    with httpx.Client(
        headers=_DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_sec
    ) as client:
        sales_models = _scrape_model_map(
            client,
            url=f"https://auto.drom.ru/{make_slug}/",
            expected_path_part=f"/{make_slug}/",
            extractor=lambda html: parse_brand_models_from_html(html, make_slug),
        )
        catalog_models = _scrape_model_map(
            client,
            url=f"https://www.drom.ru/catalog/{make_slug}/",
            expected_path_part=f"/catalog/{make_slug}/",
            extractor=lambda html: parse_catalog_models_from_html(html, make_slug),
        )

    has_any = bool(sales_models or catalog_models)
    return make_slug, compact_brand_models(brand_name, sales_models, catalog_models), has_any


def sync_drom_schema(
    output_path: Path = DEFAULT_SCHEMA_PATH,
    *,
    max_workers: int = 10,
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    """Scrape full Drom brand/model directory and filter enum schema into a compact JSON file."""
    with httpx.Client(
        headers=_DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_sec
    ) as client:
        _, _, all_html = _fetch_text(client, "https://auto.drom.ru/all/")
        filter_schema = _extract_filter_schema(all_html)

        _, _, cat_html = _fetch_text(client, "https://www.drom.ru/catalog/")
        brand_names, brand_slug_map = parse_catalog_brands_from_html(cat_html)

    brands_to_scrape: dict[str, str] = {}
    for name in brand_names:
        slug = brand_slug_map.get(name.strip().lower())
        if slug:
            brands_to_scrape.setdefault(slug, name.strip())

    brands_result: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_scrape_single_brand, slug, name, timeout_sec)
            for slug, name in sorted(brands_to_scrape.items())
        ]
        for future in as_completed(futures):
            slug, entry, has_any = future.result()
            if has_any and (
                "sales_models" in entry
                or "catalog_models" in entry
                or normalize_slug(entry["name"]) != slug
                or "h" in slug
            ):
                brands_result[slug] = entry

    schema = {
        "filter_schema": filter_schema,
        "model_aliases": {k: [v[0], v[1]] for k, v in DEFAULT_MODEL_ALIASES.items()},
        "brands": dict(sorted(brands_result.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return schema
