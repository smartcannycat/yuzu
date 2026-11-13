import re
from dataclasses import dataclass
from datetime import timedelta

from apps.lots.integrations.drom.cache import read_drom_cache, write_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.schemas import DromFetchError

_MODEL_LIST_URL = (
    "https://www.drom.ru/api/sales/model-list/by-firm-id"
    "?firmId={firm_id}&cityId=23&regionId=0&distance=0&marketId=0"
)
_CATALOG_TTL = timedelta(days=14)

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

_BRAND_ALIASES: dict[str, str] = {
    "toyota": "toyota",
    "тойота": "toyota",
    "honda": "honda",
    "хонда": "honda",
    "nissan": "nissan",
    "ниссан": "nissan",
    "subaru": "subaru",
    "субару": "subaru",
    "mazda": "mazda",
    "мазда": "mazda",
    "suzuki": "suzuki",
    "сузуки": "suzuki",
    "mitsubishi": "mitsubishi",
    "митсубиси": "mitsubishi",
    "daihatsu": "daihatsu",
    "дайхатсу": "daihatsu",
    "lexus": "lexus",
    "лексус": "lexus",
    "isuzu": "isuzu",
    "исузу": "isuzu",
}

_JAPANESE_FIRM_IDS: dict[str, int] = {
    "daihatsu": 1,
    "honda": 2,
    "isuzu": 3,
    "mazda": 4,
    "mitsubishi": 5,
    "nissan": 6,
    "subaru": 7,
    "suzuki": 8,
    "toyota": 9,
    "lexus": 23,
}

# Maps JDM model names (normalized spaces) to (drom_model_slug, optional Drom frameType ID).
# Frame type 3 = Wagon, 5 = 5-door Hatchback.
_MODEL_ALIASES: dict[str, tuple[str, int | None]] = {
    "corolla touring": ("corolla", 3),
    "corolla touring hybrid": ("corolla", 3),
    "corolla sport": ("corolla", 5),
    "corolla axio": ("corolla_axio", None),
    "corolla fielder": ("corolla_fielder", None),
    "vezel hybrid": ("vezel", None),
    "note e-power": ("note", None),
    "note e power": ("note", None),
    "note aura": ("aura", None),
    "fit hybrid": ("fit", None),
    "fit shuttle": ("fit_shuttle", None),
    "prius alpha": ("prius_alpha", None),
    "prius a": ("prius_alpha", None),
    "land cruiser prado": ("land_cruiser_prado", None),
    "land cruiser": ("land_cruiser", None),
    "x trail": ("x-trail", None),
    "x-trail": ("x-trail", None),
    "cx 5": ("cx-5", None),
    "cx-5": ("cx-5", None),
    "cx 3": ("cx-3", None),
    "cx-3": ("cx-3", None),
    "cx 30": ("cx-30", None),
    "cx-30": ("cx-30", None),
    "cx 8": ("cx-8", None),
    "cx-8": ("cx-8", None),
    "zr v": ("zr-v", None),
    "zr-v": ("zr-v", None),
    "c hr": ("c-hr", None),
    "c-hr": ("c-hr", None),
    "impreza xv": ("xv", None),
    "impreza sport": ("impreza", 5),
    "levorg layback": ("levorg", None),
    "stepwgn": ("stepwgn", None),
    "step wgn": ("stepwgn", None),
    "step wagon": ("stepwgn", None),
    "delica d5": ("delica_d_5", None),
    "delica d 5": ("delica_d_5", None),
    "delica d:5": ("delica_d_5", None),
    "crown athlete": ("crown", None),
    "crown royal": ("crown", None),
    "yaris cross": ("yaris_cross", None),
    "corolla cross": ("corolla_cross", None),
    "rav 4": ("rav4", None),
    "rav4": ("rav4", None),
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


def _model_name_to_slug(name: str) -> str:
    return normalize_slug(name)


class DromSlugResolver:
    """Three-level Drom brand/model slug resolver backed by ExternalCache."""

    def __init__(self, client: DromHttpClient) -> None:
        self._client = client

    def resolve(self, make: str, model: str) -> ResolvedDromSlug:
        """Resolve brand and model using alias table first, then normalized slug."""
        make_norm = make.strip().lower()
        make_slug = _BRAND_ALIASES.get(make_norm, normalize_slug(make_norm))

        model_key = re.sub(r"\s+", " ", model.strip().lower())
        if model_key in _MODEL_ALIASES:
            slug, frame_type = _MODEL_ALIASES[model_key]
            return ResolvedDromSlug(
                make_slug=make_slug,
                model_slug=slug,
                frame_type_id=frame_type,
            )

        words = [w for w in re.split(r"[\s/]+", model_key) if w and w not in _TRIM_NOISE_WORDS]
        stripped_key = " ".join(words)
        if stripped_key in _MODEL_ALIASES:
            slug, frame_type = _MODEL_ALIASES[stripped_key]
            return ResolvedDromSlug(
                make_slug=make_slug,
                model_slug=slug,
                frame_type_id=frame_type,
            )

        return ResolvedDromSlug(
            make_slug=make_slug,
            model_slug=normalize_slug(stripped_key or model_key),
            frame_type_id=None,
        )

    def resolve_via_api(self, make: str, model: str) -> ResolvedDromSlug | None:
        """Fallback lookup via Drom's model-list API when a direct slug returns 404."""
        make_norm = make.strip().lower()
        make_slug = _BRAND_ALIASES.get(make_norm, normalize_slug(make_norm))
        firm_id = _JAPANESE_FIRM_IDS.get(make_slug)
        if firm_id is None:
            return None

        models = self._get_firm_models(firm_id, make_slug)
        if not models:
            return None

        target_words = [
            word
            for word in re.split(r"[\s_\-/]+", model.strip().lower())
            if word and word not in _TRIM_NOISE_WORDS
        ]
        if not target_words:
            return None

        best_name = _pick_best_model_name(target_words, models)
        if best_name is None:
            return None

        return ResolvedDromSlug(
            make_slug=make_slug,
            model_slug=_model_name_to_slug(best_name),
            frame_type_id=None,
        )

    def _get_firm_models(self, firm_id: int, make_slug: str) -> list[str]:
        cache_key = f"drom:models:{make_slug}:{firm_id}"
        cached_payload = read_drom_cache(cache_key, allow_stale=False)
        if cached_payload is not None and isinstance(cached_payload.get("models"), list):
            return [str(n) for n in cached_payload["models"]]

        url = _MODEL_LIST_URL.format(firm_id=firm_id)
        try:
            payload = self._client.get_json(url)
        except DromFetchError:
            stale_payload = read_drom_cache(cache_key, allow_stale=True)
            if stale_payload is not None and isinstance(stale_payload.get("models"), list):
                return [str(n) for n in stale_payload["models"]]
            return []

        data = payload.get("data") or {}
        raw_items = (data.get("top") or []) + (data.get("regular") or [])
        names = [
            str(item["name"]) for item in raw_items if isinstance(item, dict) and "name" in item
        ]
        if names:
            write_drom_cache(cache_key, {"models": names}, ttl=_CATALOG_TTL)
        return names


def _pick_best_model_name(target_words: list[str], candidate_names: list[str]) -> str | None:
    target_joined = " ".join(target_words)
    for name in candidate_names:
        if name.strip().lower() == target_joined:
            return name

    # Match progressively shorter prefix (e.g. ["corolla", "touring"] -> "Corolla")
    for end in range(len(target_words), 0, -1):
        prefix = " ".join(target_words[:end])
        for name in candidate_names:
            if name.strip().lower() == prefix:
                return name

    # Token overlap fallback, preferring highest overlap and fewer extra words.
    target_set = set(target_words)
    best_key: tuple[int, int] = (0, 0)
    best_match: str | None = None
    for name in candidate_names:
        cand_tokens = set(re.split(r"[\s_\-/]+", name.strip().lower()))
        overlap = len(target_set & cand_tokens)
        score = (overlap, -len(cand_tokens))
        if overlap > 0 and score > best_key:
            best_key = score
            best_match = name
    return best_match
