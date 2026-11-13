import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.lots.integrations.drom.cache import fetch_with_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.directory_parser import _is_seo_label
from apps.lots.integrations.drom.parser import (
    parse_brand_models_from_html,
    parse_catalog_brands_from_html,
    parse_catalog_models_from_html,
)

_BRAND_PAGE_URL = "https://auto.drom.ru/{make_slug}/"
_CATALOG_BRANDS_URL = "https://www.drom.ru/catalog/"
_CATALOG_MODEL_LIST_URL = "https://www.drom.ru/catalog/{make_slug}/"
_CATALOG_TTL = timedelta(days=14)
_SCHEMA_PATH = Path(__file__).resolve().parent / "data" / "drom_schema.json"


@lru_cache(maxsize=1)
def _load_drom_schema() -> dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        return {}
    try:
        payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


load_drom_schema = _load_drom_schema

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

DEFAULT_MODEL_ALIASES: dict[str, tuple[str, str | None]] = {
    "corolla touring": ("corolla", "универсал"),
    "corolla touring hybrid": ("corolla", "универсал"),
    "corolla sport": ("corolla", "хэтчбек 5 дв."),
    "impreza sport": ("impreza", "хэтчбек 5 дв."),
    "impreza xv": ("xv", None),
    "note aura": ("aura", None),
    "prius a": ("prius_a", None),
    "prius alpha": ("prius_a", None),
    "prius α": ("prius_a", None),
    "every van": ("every", None),
}

_DEFAULT_FRAME_TYPES: dict[str, int] = {
    "универсал": 3,
    "хэтчбек 5 дв.": 5,
}

_TRIM_NOISE_WORDS = frozenset(
    {"hybrid", "hv", "e-power", "epower", "4wd", "2wd", "turbo", "wxb", "w×b"}
)

# Tokens that denote a distinct model/body line on Drom and must not be dropped
# when collapsing a multi-word model name onto a shorter base model.
_SUBMODEL_CONFLICT_TOKENS = frozenset(
    {
        "cross",
        "type",
        "r",
        "alpha",
        "plus",
        "slash",
        "van",
        "wagon",
        "truck",
        "latio",
        "axio",
        "fielder",
        "rumion",
        "spacio",
        "verso",
        "allroad",
        "shuttle",
        "spike",
        "aria",
        "phv",
        "prime",
        "gr",
        "sti",
        "wrx",
    }
)


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
    transliterated = _transliterate_cyrillic(value.strip()).replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", "", transliterated)


def _get_model_aliases(schema: dict[str, Any]) -> dict[str, tuple[str, str | None]]:
    raw = schema.get("model_aliases")
    if not isinstance(raw, dict) or not raw:
        return DEFAULT_MODEL_ALIASES
    aliases = dict(DEFAULT_MODEL_ALIASES)
    for k, v in raw.items():
        if isinstance(v, (list, tuple)) and len(v) >= 1 and v[0]:
            frame = str(v[1]) if len(v) > 1 and v[1] is not None else None
            aliases[str(k).strip().lower()] = (str(v[0]), frame)
    return aliases


def _extract_trivial_models(brand_entry: dict[str, Any]) -> list[str]:
    raw_models = brand_entry.get("models")
    if isinstance(raw_models, str) and raw_models:
        return [m.strip() for m in raw_models.split("|") if m.strip()]
    if isinstance(raw_models, list):
        return [str(m).strip() for m in raw_models if str(m).strip()]
    return []


def _resolve_model_from_schema_dict(
    model: str,
    model_map: object,
    make_slug: str,
    *,
    trivial_models: list[str] | None = None,
) -> ResolvedDromSlug | None:
    merged: dict[str, str] = {}
    for name in trivial_models or []:
        merged[name] = normalize_slug(name)
    if isinstance(model_map, dict):
        for k, v in model_map.items():
            merged[str(k)] = str(v)
    if not merged:
        return None
    matched = _pick_best_model_slug(
        model,
        list(merged.keys()),
        {k.lower(): v for k, v in merged.items()},
        allow_fuzzy=False,
    )
    if not matched:
        return None
    return ResolvedDromSlug(make_slug=make_slug, model_slug=matched, frame_type_id=None)


def _resolve_alias(
    model: str,
    make_slug: str,
    schema: dict[str, Any],
) -> ResolvedDromSlug | None:
    aliases = _get_model_aliases(schema)
    frame_types: dict = (schema.get("filter_schema") or {}).get("frame_types") or {}
    model_key = re.sub(r"\s+", " ", model.strip().lower())
    words = [w for w in re.split(r"[\s/]+", model_key) if w and w not in _TRIM_NOISE_WORDS]
    stripped_key = " ".join(words)

    for alias_key in (model_key, stripped_key):
        if alias_key in aliases:
            slug, frame_label = aliases[alias_key]
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
    return None


class DromSlugResolver:
    """Dynamic Drom brand and model slug resolver backed by Drom HTML catalogs and ExternalCache."""

    def __init__(self, client: DromHttpClient) -> None:
        self._client = client

    def resolve(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve sales brand and model from compact Drom schema and structural aliases."""
        schema = _load_drom_schema()
        brands: dict = schema.get("brands") or {}
        make_slug = _resolve_make_from_schema(make, brands)

        aliased = _resolve_alias(model, make_slug, schema)
        if aliased is not None:
            return aliased

        brand_entry = brands.get(make_slug)
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

        return self._fallback_normalized_slug(make_slug, model)

    def resolve_via_api(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Resolve exact Drom brand and model URL slugs dynamically from Drom's live sales pages."""
        return self._resolve_via_directory(make, model, self._get_sales_models)

    def resolve_catalog_slug(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve canonical Drom catalog slug from compact schema."""
        schema = _load_drom_schema()
        brands: dict = schema.get("brands") or {}
        make_slug = _resolve_make_from_schema(make, brands)
        brand_entry = brands.get(make_slug)
        trivial = _extract_trivial_models(brand_entry) if isinstance(brand_entry, dict) else []

        if isinstance(brand_entry, dict):
            from_cat = _resolve_model_from_schema_dict(
                model,
                brand_entry.get("catalog_models"),
                make_slug,
            )
            if from_cat is not None:
                return from_cat

        aliased = _resolve_alias(model, make_slug, schema)
        if aliased is not None:
            return ResolvedDromSlug(
                make_slug=aliased.make_slug,
                model_slug=aliased.model_slug,
                frame_type_id=None,
            )

        if isinstance(brand_entry, dict):
            from_sales = _resolve_model_from_schema_dict(
                model,
                brand_entry.get("sales_models"),
                make_slug,
                trivial_models=trivial,
            )
            if from_sales is not None:
                return from_sales

        return self._fallback_normalized_slug(make_slug, model)

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
        )
        return result if result is not None else ([], {})


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


def _fuzzy_match_alnum(
    target_keys: list[str],
    candidate_names: list[str],
    *,
    cutoff: float = 0.72,
) -> str | None:
    alnum_to_name = {
        _alnum_key(n): n for n in candidate_names if _alnum_key(n) and not _is_seo_label(n)
    }
    if not alnum_to_name:
        return None
    for key in target_keys:
        if key in alnum_to_name:
            return alnum_to_name[key]
        close = get_close_matches(key, list(alnum_to_name.keys()), n=1, cutoff=cutoff)
        if close:
            return alnum_to_name[close[0]]
    return None


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

    variants = [target_alnum]
    if "kh" in target_alnum:
        variants.append(target_alnum.replace("kh", "h"))
    if target_norm.startswith("bmv"):
        variants.append("bmw")

    matched_name = _fuzzy_match_alnum(variants, candidate_names)
    if matched_name is None:
        return None
    return slug_map.get(matched_name.strip().lower(), normalize_slug(matched_name))


def _pick_best_model_slug(
    model: str,
    candidate_names: list[str],
    slug_map: dict[str, str],
    *,
    allow_fuzzy: bool = True,
) -> str | None:
    target_words = [
        _transliterate_cyrillic(word)
        for word in re.split(r"[\s_\-/]+", model.strip().lower())
        if word and word not in _TRIM_NOISE_WORDS
    ]
    if not target_words:
        return None

    clean_candidates = [n for n in candidate_names if not _is_seo_label(n)]
    best_name = _pick_best_model_name(
        target_words,
        clean_candidates,
        allow_fuzzy=allow_fuzzy,
    )
    if best_name is None:
        return None
    return slug_map.get(best_name.strip().lower(), normalize_slug(best_name))


def _match_exact_or_alnum(target_words: list[str], candidate_names: list[str]) -> str | None:
    target_joined = " ".join(target_words)
    target_alnum = _alnum_key(target_joined)
    for name in candidate_names:
        if name.strip().lower() == target_joined:
            return name
    for name in candidate_names:
        if _alnum_key(name) == target_alnum:
            return name
    return None


def _match_prefix_words(target_words: list[str], candidate_names: list[str]) -> str | None:
    for end in range(len(target_words), 0, -1):
        dropped = set(target_words[end:])
        if dropped & _SUBMODEL_CONFLICT_TOKENS:
            continue
        prefix = " ".join(target_words[:end])
        prefix_alnum = _alnum_key(prefix)
        for name in candidate_names:
            if name.strip().lower() == prefix or _alnum_key(name) == prefix_alnum:
                return name
    return None


def _match_token_overlap(target_words: list[str], candidate_names: list[str]) -> str | None:
    target_set = set(target_words)
    best_key: tuple[int, int] = (0, 0)
    best_match: str | None = None
    for name in candidate_names:
        cand_tokens = {
            t for t in re.split(r"[\s_\-/]+", _transliterate_cyrillic(name.strip().lower())) if t
        }
        if not cand_tokens or not cand_tokens.issubset(target_set):
            continue
        extra_target_tokens = target_set - cand_tokens
        if extra_target_tokens & _SUBMODEL_CONFLICT_TOKENS:
            continue
        overlap = len(cand_tokens)
        score = (overlap, -len(cand_tokens))
        if score > best_key:
            best_key = score
            best_match = name
    return best_match


def _pick_best_model_name(
    target_words: list[str],
    candidate_names: list[str],
    *,
    allow_fuzzy: bool = True,
) -> str | None:
    if any(w in _SUBMODEL_CONFLICT_TOKENS for w in target_words[1:]):
        return _match_exact_or_alnum(target_words, candidate_names) or _match_prefix_words(
            target_words, candidate_names
        )
    matched = (
        _match_exact_or_alnum(target_words, candidate_names)
        or _match_prefix_words(target_words, candidate_names)
        or _match_token_overlap(target_words, candidate_names)
    )
    if matched or not allow_fuzzy:
        return matched
    return _fuzzy_match_alnum([_alnum_key(" ".join(target_words))], candidate_names)
