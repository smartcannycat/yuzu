import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from apps.lots.integrations.drom.client import _DEFAULT_HEADERS, _detect_charset
from apps.lots.integrations.drom.html_utils import extract_bulls_list_ssr_payload
from apps.lots.integrations.drom.parser import (
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)

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


def _extract_filter_schema_and_firms(html: str) -> tuple[dict[str, Any], dict[str, int]]:
    payload = extract_bulls_list_ssr_payload(html)
    if payload is None:
        return {"fuel_types": {}, "drive_units": {}, "frame_types": {}}, {}

    view = (payload.get("filter") or {}).get("view") or {}
    firms_data = view.get("firms") or {}
    firm_ids: dict[str, int] = {}
    for bucket in ("top", "regular"):
        for item in firms_data.get(bucket) or []:
            if isinstance(item, dict) and item.get("name") and item.get("id") is not None:
                firm_ids[str(item["name"]).strip().lower()] = int(item["id"])

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

    return (
        {
            "fuel_types": fuel_types,
            "drive_units": drive_units,
            "frame_types": frame_types,
        },
        firm_ids,
    )


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
    firm_id: int | None,
    timeout_sec: float,
) -> tuple[str, dict[str, Any]]:
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

    return make_slug, {
        "name": brand_name,
        "firm_id": firm_id,
        "sales_models": dict(sorted(sales_models.items())),
        "catalog_models": dict(sorted(catalog_models.items())),
    }


def sync_drom_schema(
    output_path: Path = DEFAULT_SCHEMA_PATH,
    *,
    max_workers: int = 10,
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    """Scrape full Drom brand/model directory and filter enum schema into a JSON file."""
    with httpx.Client(
        headers=_DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_sec
    ) as client:
        _, _, all_html = _fetch_text(client, "https://auto.drom.ru/all/")
        filter_schema, firm_ids = _extract_filter_schema_and_firms(all_html)

        _, _, cat_html = _fetch_text(client, "https://www.drom.ru/catalog/")
        brand_names, brand_slug_map = parse_catalog_brands_from_html(cat_html)

    brands_to_scrape: dict[str, tuple[str, int | None]] = {}
    for name in brand_names:
        slug = brand_slug_map.get(name.strip().lower())
        if not slug:
            continue
        firm_id = firm_ids.get(name.strip().lower())
        brands_to_scrape.setdefault(slug, (name.strip(), firm_id))

    brands_result: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_scrape_single_brand, slug, name, firm_id, timeout_sec)
            for slug, (name, firm_id) in sorted(brands_to_scrape.items())
        ]
        for future in as_completed(futures):
            slug, entry = future.result()
            if entry["sales_models"] or entry["catalog_models"]:
                brands_result[slug] = entry

    schema = {
        "filter_schema": filter_schema,
        "brands": dict(sorted(brands_result.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return schema
