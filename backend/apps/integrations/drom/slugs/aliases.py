"""Drom schema loading, make/model alias tables, and fuzzy matching heuristics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.integrations.drom.directory_parser import _is_seo_label
from apps.integrations.drom.slug_rules import (
    _BRAND_ALIASES,
    _DEFAULT_FRAME_TYPES,
    _MAKE_REGEX_RULES,
    _SUBMODEL_CONFLICT_TOKENS,
    _TRIM_NOISE_WORDS,
    DEFAULT_MODEL_ALIASES,
    _alnum_key,
    _transliterate_cyrillic,
    normalize_slug,
)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "drom_schema.json"


@dataclass(frozen=True, slots=True)
class ResolvedDromSlug:
    make_slug: str
    model_slug: str
    frame_type_id: int | None = None
    is_fallback_guess: bool = False


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
    raw_words = [w for w in re.split(r"[\s/]+", model_key) if w]
    stripped_words = [w for w in raw_words if w not in _TRIM_NOISE_WORDS]

    for word_list in (raw_words, stripped_words):
        for end in range(len(word_list), 0, -1):
            if set(word_list[end:]) & _SUBMODEL_CONFLICT_TOKENS:
                continue
            alias_key = " ".join(word_list[:end])
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


def _resolve_make_aware_alias(make_slug: str, model: str) -> ResolvedDromSlug | None:
    model_key = re.sub(r"\s+", " ", model.strip().lower())
    if not model_key:
        return None
    for pattern, replacement in _MAKE_REGEX_RULES.get(make_slug, ()):
        match = pattern.match(model_key)
        if match:
            slug = pattern.sub(replacement, match.group(0)) if r"\1" in replacement else replacement
            return ResolvedDromSlug(make_slug=make_slug, model_slug=slug)
    return None


def _resolve_make_from_schema(make: str, brands: dict) -> str:
    make_key = re.sub(r"\s+", " ", make.strip().lower())
    if make_key in _BRAND_ALIASES:
        return _BRAND_ALIASES[make_key]
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
    target_alnum = _alnum_key(make)
    if not target_alnum:
        return None
    for name in candidate_names:
        if _alnum_key(name) == target_alnum:
            return slug_map.get(name.strip().lower(), normalize_slug(name))
    variants = [target_alnum]
    if "kh" in target_alnum:
        variants.append(target_alnum.replace("kh", "h"))
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
    best_name = _pick_best_model_name(target_words, clean_candidates, allow_fuzzy=allow_fuzzy)
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
