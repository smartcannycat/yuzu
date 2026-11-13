import json
import re
from dataclasses import dataclass
from datetime import timedelta
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

from apps.lots.integrations.drom.cache import read_drom_cache, write_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.parser import (
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)
from apps.lots.integrations.drom.schemas import DromBlockedError, DromFetchError

_BRAND_PAGE_URL = "https://auto.drom.ru/{make_slug}/"
_CATALOG_BRANDS_URL = "https://www.drom.ru/catalog/"
_CATALOG_MODEL_LIST_URL = "https://www.drom.ru/catalog/{make_slug}/"
_CATALOG_TTL = timedelta(days=14)
_SCHEMA_PATH = Path(__file__).resolve().parent / "data" / "drom_schema.json"


@lru_cache(maxsize=1)
def _load_drom_schema() -> dict:
    if not _SCHEMA_PATH.exists():
        return {}
    try:
        payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


_CYRILLIC_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

# Only true structural mismatches where Drom shares one model slug across multiple
# auction model names (requires frametype[]) or renames a separate catalog entry.
_MODEL_ALIASES: dict[str, tuple[str, str | None]] = {
    "corolla touring": ("corolla", "универсал"),
    "corolla touring hybrid": ("corolla", "универсал"),
    "corolla sport": ("corolla", "хэтчбек 5 дв."),
    "impreza sport": ("impreza", "хэтчбек 5 дв."),
    "impreza xv": ("xv", None),
    "note aura": ("aura", None),
    "prius a": ("prius_alpha", None),
}

_DEFAULT_FRAME_TYPES: dict[str, int] = {
    "универсал": 3,
    "хэтчбек 5 дв.": 5,
}

_TRIM_NOISE_WORDS = frozenset({"hybrid", "e-power", "epower", "4wd", "2wd", "turbo", "wxb", "w×b"})


@dataclass(frozen=True, slots=True)
class ResolvedDromSlug:
    make_slug: str
    model_slug: str
    frame_type_id: int | None = None


def _transliterate_cyrillic(value: str) -> str:
    return "".join(_CYRILLIC_TRANSLIT.get(ch, ch) for ch in value.lower())


def normalize_slug(value: str) -> str:
    """Normalize a brand or model string into a non-empty URL-safe Drom slug."""
    transliterated = _transliterate_cyrillic(value.strip())
    cleaned = re.sub(r"[^a-z0-9\-\s_]+", " ", transliterated)
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_-")
    return cleaned or "auto"


def _alnum_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _transliterate_cyrillic(value.strip()))


class DromSlugResolver:
    """Dynamic Drom brand and model slug resolver backed by Drom HTML catalogs and ExternalCache."""

    def __init__(self, client: DromHttpClient) -> None:
        self._client = client

    def resolve(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve brand and model from scraped Drom schema first, then structural splits."""
        schema = _load_drom_schema()
        brands: dict = schema.get("brands") or {}
        frame_types: dict = (schema.get("filter_schema") or {}).get("frame_types") or {}

        make_slug = _resolve_make_from_schema(make, brands)

        model_key = re.sub(r"\s+", " ", model.strip().lower())
        words = [w for w in re.split(r"[\s/]+", model_key) if w and w not in _TRIM_NOISE_WORDS]
        stripped_key = " ".join(words)

        for alias_key in (model_key, stripped_key):
            if alias_key in _MODEL_ALIASES:
                slug, frame_label = _MODEL_ALIASES[alias_key]
                frame_id = (
                    frame_types.get(frame_label, _DEFAULT_FRAME_TYPES.get(frame_label))
                    if frame_label
                    else None
                )
                return ResolvedDromSlug(
                    make_slug=make_slug,
                    model_slug=slug,
                    frame_type_id=frame_id,
                )

        brand_entry = brands.get(make_slug)
        if isinstance(brand_entry, dict):
            sales_models = brand_entry.get("sales_models") or {}
            if isinstance(sales_models, dict) and sales_models:
                matched = _pick_best_model_slug(
                    model,
                    list(sales_models.keys()),
                    {str(k).lower(): str(v) for k, v in sales_models.items()},
                )
                if matched:
                    return ResolvedDromSlug(
                        make_slug=make_slug,
                        model_slug=matched,
                        frame_type_id=None,
                    )

        return ResolvedDromSlug(
            make_slug=make_slug,
            model_slug=normalize_slug(stripped_key or model_key),
            frame_type_id=None,
        )

    def resolve_via_api(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Resolve exact Drom brand and model URL slugs dynamically from Drom's live pages."""
        make_slug = _resolve_make_from_schema(make, _load_drom_schema().get("brands") or {})
        names, slug_map = self._get_sales_models(make_slug)

        # If the initial brand slug redirected/404'd (e.g. Cyrillic transliteration mismatch),
        # look up the canonical brand slug from Drom's full brand directory.
        if not names:
            resolved_make = self._resolve_brand_slug(make)
            if resolved_make and resolved_make != make_slug:
                make_slug = resolved_make
                names, slug_map = self._get_sales_models(make_slug)

        if not names:
            return None

        best_slug = _pick_best_model_slug(model, names, slug_map)
        if best_slug is None:
            return None

        return ResolvedDromSlug(
            make_slug=make_slug,
            model_slug=best_slug,
            frame_type_id=None,
        )

    def resolve_catalog_slug(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Resolve canonical Drom catalog slug from scraped schema or live catalog page."""
        brands = _load_drom_schema().get("brands") or {}
        make_slug = _resolve_make_from_schema(make, brands)
        brand_entry = brands.get(make_slug)
        if isinstance(brand_entry, dict):
            catalog_models = brand_entry.get("catalog_models") or {}
            if isinstance(catalog_models, dict) and catalog_models:
                matched = _pick_best_model_slug(
                    model,
                    list(catalog_models.keys()),
                    {str(k).lower(): str(v) for k, v in catalog_models.items()},
                )
                if matched:
                    return ResolvedDromSlug(
                        make_slug=make_slug,
                        model_slug=matched,
                        frame_type_id=None,
                    )

        names, slug_map = self._get_catalog_models(make_slug)
        if not names:
            resolved_make = self._resolve_brand_slug(make)
            if resolved_make and resolved_make != make_slug:
                make_slug = resolved_make
                names, slug_map = self._get_catalog_models(make_slug)

        if not names:
            return None

        best_slug = _pick_best_model_slug(model, names, slug_map)
        if best_slug is None:
            return None
        return ResolvedDromSlug(make_slug=make_slug, model_slug=best_slug, frame_type_id=None)

    def _resolve_brand_slug(self, make: str) -> str | None:
        cache_key = "drom:catalog:brands"
        names, slug_map = self._load_or_fetch_directory(
            cache_key=cache_key,
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
        extractor,
    ) -> tuple[list[str], dict[str, str]]:
        cached = read_drom_cache(cache_key, allow_stale=False)
        parsed_cached = _unpack_directory_cache(cached)
        if parsed_cached is not None:
            return parsed_cached

        try:
            html = self._client.get_html(url, expected_path_parts=expected_path_parts)
        except DromBlockedError:
            stale = read_drom_cache(cache_key, allow_stale=True)
            return _unpack_directory_cache(stale) or ([], {})
        except DromFetchError:
            stale = read_drom_cache(cache_key, allow_stale=True)
            return _unpack_directory_cache(stale) or ([], {})

        names, slug_map = extractor(html)
        if names:
            write_drom_cache(cache_key, {"models": names, "slug_map": slug_map}, ttl=_CATALOG_TTL)
        return names, slug_map


def _resolve_make_from_schema(make: str, brands: dict) -> str:
    make_slug = normalize_slug(make)
    if not brands or make_slug in brands:
        return make_slug
    names: list[str] = []
    slug_map: dict[str, str] = {}
    for slug, entry in brands.items():
        if isinstance(entry, dict) and entry.get("name"):
            name = str(entry["name"]).strip()
            names.append(name)
            slug_map[name.lower()] = str(slug)
    if names:
        matched = _pick_best_brand_slug(make, names, slug_map)
        if matched:
            return matched
    return make_slug


def _unpack_directory_cache(payload: dict | None) -> tuple[list[str], dict[str, str]] | None:
    if payload is None or not isinstance(payload.get("models"), list):
        return None
    raw_slug_map = payload.get("slug_map")
    slug_map = (
        {str(k): str(v) for k, v in raw_slug_map.items()} if isinstance(raw_slug_map, dict) else {}
    )
    return [str(n) for n in payload["models"]], slug_map


def _pick_best_brand_slug(
    make: str,
    candidate_names: list[str],
    slug_map: dict[str, str],
) -> str | None:
    target_norm = _transliterate_cyrillic(make.strip())
    target_alnum = _alnum_key(make)
    if not target_alnum:
        return None

    for name in candidate_names:
        if _alnum_key(name) == target_alnum:
            return slug_map.get(name.strip().lower(), normalize_slug(name))

    alnum_to_name = {_alnum_key(n): n for n in candidate_names if _alnum_key(n)}
    # Check both raw transliteration (khonda) and h/kh-normalized form (honda).
    variants = [target_alnum]
    if "kh" in target_alnum:
        variants.append(target_alnum.replace("kh", "h"))
    if target_norm.startswith("bmv"):
        variants.append("bmw")
    for variant in variants:
        if variant in alnum_to_name:
            matched_name = alnum_to_name[variant]
            return slug_map.get(matched_name.strip().lower(), normalize_slug(matched_name))
        close = get_close_matches(variant, list(alnum_to_name.keys()), n=1, cutoff=0.72)
        if close:
            matched_name = alnum_to_name[close[0]]
            return slug_map.get(matched_name.strip().lower(), normalize_slug(matched_name))
    return None


def _pick_best_model_slug(
    model: str,
    candidate_names: list[str],
    slug_map: dict[str, str],
) -> str | None:
    target_words = [
        _transliterate_cyrillic(word)
        for word in re.split(r"[\s_\-/]+", model.strip().lower())
        if word and word not in _TRIM_NOISE_WORDS
    ]
    if not target_words:
        return None

    best_name = _pick_best_model_name(target_words, candidate_names)
    if best_name is None:
        return None
    return slug_map.get(best_name.strip().lower(), normalize_slug(best_name))


def _pick_best_model_name(target_words: list[str], candidate_names: list[str]) -> str | None:
    target_joined = " ".join(target_words)
    target_alnum = _alnum_key(target_joined)

    for name in candidate_names:
        if name.strip().lower() == target_joined:
            return name

    # Match alphanumeric forms ignoring hyphens/spaces/colons (e.g. "cx 5" -> "CX-5", "delica d:5").
    for name in candidate_names:
        if _alnum_key(name) == target_alnum:
            return name

    # Match progressively shorter prefix (e.g. ["corolla", "rumion", "x"] -> "Corolla Rumion",
    # ["every", "van"] -> "Every").
    for end in range(len(target_words), 0, -1):
        prefix = " ".join(target_words[:end])
        prefix_alnum = _alnum_key(prefix)
        for name in candidate_names:
            if name.strip().lower() == prefix or _alnum_key(name) == prefix_alnum:
                return name

    # Token overlap fallback, preferring highest overlap and fewer extra words.
    target_set = set(target_words)
    best_key: tuple[int, int] = (0, 0)
    best_match: str | None = None
    for name in candidate_names:
        cand_tokens = set(re.split(r"[\s_\-/]+", _transliterate_cyrillic(name.strip().lower())))
        overlap = len(target_set & cand_tokens)
        score = (overlap, -len(cand_tokens))
        if overlap > 0 and score > best_key:
            best_key = score
            best_match = name
    if best_match is not None:
        return best_match

    # Fuzzy match for minor spelling/transliteration differences (e.g. Cyrillic "Королла").
    alnum_to_name = {_alnum_key(n): n for n in candidate_names if _alnum_key(n)}
    close = get_close_matches(target_alnum, list(alnum_to_name.keys()), n=1, cutoff=0.72)
    return alnum_to_name[close[0]] if close else None
