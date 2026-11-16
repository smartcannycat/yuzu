"""Compatibility matching predicates for Farpost used-parts listings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from apps.integrations.farpost.aliases import (
    _MAKE_ALIASES,
    _MAKE_CONFLICT_PATTERNS,
    _MODEL_ALIASES,
    _SISTER_MAKES,
)

if TYPE_CHECKING:
    from apps.integrations.farpost.parser import PartCriteria

_ACCESSORIES = re.compile(
    r"обшивк|ручк|петл[яи]|молдинг|уплотнител|стеклопод[ъь]емник|замок|"
    r"проводк|накладк|зеркал|заглушк|креплен|комплект|пара\b|"
    r"решетк|усилител|абсорбер|кронштейн|подкрыл|брызговик|"
    r"фара|фонар|повторител|жабо|трапец|ограничител|форточк|"
    r"коврик|полк[аи]|шторк|упор|эмблем|шильдик|омывател|моторчик",
    re.I,
)
_ASSEMBLY_SUFFIX_RE = re.compile(
    r"(?:\bв\s+сборе\b.*|\b(?:с|со|без|под)\s+(?:обшивк|ручк|петл|молдинг|уплотнител|"
    r"стеклопод[ъь]емник|замк|замок|проводк|накладк|зеркал|заглушк|креплен|решетк|"
    r"усилител|абсорбер|кронштейн|подкрыл|брызговик|фара|фонар|повторител|омывател|"
    r"туманк|парктроник|датчик|камер|форточк|ограничител|моторчик|эмблем|шильдик|"
    r"шторк|упор|трапец|стекл)\w*.*)",
    re.I,
)
_NON_WINDSHIELD_GLASS = re.compile(r"^\s*стекл[оа]\b|стекло\s+двер|дверн\w*\s+стекл", re.I)
_NEW_OR_AFTERMARKET = re.compile(
    r"\b(?:нова(?:я|ый|ое|ые)|нов(?:ый|ая|ое)|дубликат\w*|аналог\w*|"
    r"sat|tyg|api|тайван\w*|китай\w*)\b",
    re.I,
)
_DAMAGE = re.compile(r"вмятин|залом|тычк|трещин|под ремонт|поврежден|дефект|разбит", re.I)
_UNAVAILABLE = re.compile(
    r"под заказ|нет в наличии|ожидается|товар находится в другом|доставка из", re.I
)

_LEFT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:л\.?(?![a-zа-я0-9])|лев|слева\b)|[пз][/\\.]л\b|\b(?:lh|fl|rl)\b)",
    re.I,
)
_RIGHT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:прав|пр\.?(?![a-zа-я0-9])|справа\b)|[пз][/\\.]п\b|\b(?:rh|fr|rr)\b)",
    re.I,
)
_FRONT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:перед|пер\.?(?![a-zа-я0-9])|спереди\b)|п[/\\.]л\b|п[/\\.]п\b|\b(?:front|fl|fr)\b)",
    re.I,
)
_REAR_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:зад|сзади\b)|з[/\\.]л\b|з[/\\.]п\b|\b(?:rear|rl|rr)\b)",
    re.I,
)
_FENDER_RE = re.compile(r"\bкрыл(?:о|а|у|е|ья|ьев)\b", re.I)
_LITER_TOKEN_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*л\.?(?![a-zа-я0-9])", re.I)
_TAILGATE_RE = re.compile(
    r"(?:5(?:-?я)?|пят(?:ая|ой))\s*двер|двер\w*\s*(?:5(?:-?я)?|багаж)",
    re.I,
)


def strip_liter_tokens(value: str) -> str:
    """Remove engine displacement tokens (e.g. '1.5 л') so 'л' is not misread as 'левая'."""
    return _LITER_TOKEN_RE.sub(" ", value)


def _compact(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", value.casefold().replace("ё", "е"))


def contains_code(text: str, code: str) -> bool:
    """Return True if chassis body code appears with optional whitespace/suffix."""
    suffix = r"[a-z]?" if re.search(r"\d{2,}$", code) else ""
    pattern = (
        r"(?<![a-z0-9])" + r"\s*".join(map(re.escape, code.lower())) + suffix + r"(?![a-z0-9])"
    )
    return bool(re.search(pattern, text.lower()))


def _has_conflicting_make(text: str, make_key: str) -> bool:
    allowed = _SISTER_MAKES.get(make_key, frozenset({make_key}))
    normalized = text.casefold().replace("ё", "е")
    for other_make, pattern in _MAKE_CONFLICT_PATTERNS.items():
        if other_make in allowed:
            continue
        if pattern.search(normalized):
            return True
    return False


def matches_make_and_model(
    text: str, criteria: PartCriteria, *, has_exact_body_code: bool = False
) -> bool:
    compact_text = _compact(text)
    make_key = _compact(criteria.make)
    model_key = _compact(criteria.model)
    make_variants = _MAKE_ALIASES.get(make_key, (make_key,))
    model_variants = _MODEL_ALIASES.get(model_key, (model_key,))
    make_matched = any(v and v in compact_text for v in make_variants)
    model_matched = any(v and v in compact_text for v in model_variants)
    if make_matched and model_matched:
        return True
    if has_exact_body_code and (make_matched or model_matched):
        return not _has_conflicting_make(text, make_key)
    return False


def matches_part_name(name: str, criteria: PartCriteria) -> bool:
    lowered = name.casefold()
    if criteria.panel_id == "windshield":
        return "стекл" in lowered and ("лобов" in lowered or "ветров" in lowered)
    if criteria.panel_id == "tailgate":
        side_clean = strip_liter_tokens(name)
        has_side_door = bool(_LEFT_RE.search(side_clean) or _RIGHT_RE.search(side_clean))
        return (
            "багажник" in lowered
            or "дверь задка" in lowered
            or bool(_TAILGATE_RE.search(lowered))
            or ("задн" in lowered and "двер" in lowered and not has_side_door)
        )
    if criteria.panel_id in {"front_left_fender", "front_right_fender"}:
        return bool(_FENDER_RE.search(lowered))
    if criteria.part_name == "дверь":
        return "двер" in lowered
    return criteria.part_name.casefold() in lowered


def _matches_position(cleaned_name: str, criteria: PartCriteria) -> bool:
    if not criteria.position or criteria.panel_id == "windshield":
        return True
    pos = criteria.position.casefold()
    if pos.startswith("перед"):
        return bool(_FRONT_RE.search(cleaned_name)) and not _REAR_RE.search(cleaned_name)
    if pos.startswith("зад"):
        return bool(_REAR_RE.search(cleaned_name)) and not _FRONT_RE.search(cleaned_name)
    return pos[:5] in cleaned_name.casefold()


def matches_side_and_position(name: str, criteria: PartCriteria) -> bool:
    cleaned_name = strip_liter_tokens(name)
    if criteria.side:
        want_left = criteria.side.casefold().startswith("лев")
        has_left = bool(_LEFT_RE.search(cleaned_name))
        has_right = bool(_RIGHT_RE.search(cleaned_name))
        if want_left and (not has_left or has_right):
            return False
        if not want_left and (not has_right or has_left):
            return False
    return _matches_position(cleaned_name, criteria)


def matches_paint_code(text: str, paint_code: str) -> bool:
    """Return True when text explicitly confirms the factory paint code."""
    if not paint_code:
        return False
    code_pat = r"[ \t]*".join(map(re.escape, paint_code))
    context_pattern = (
        r"(?:цвет|код\s+краски|окрас|paint|color)"
        r"(?:(?!\b(?:не|другой|пробег|цена)\b)[^.;\n]){0,24}?"
        + r"(?<![a-zа-я0-9])"
        + code_pat
        + r"(?![a-zа-я0-9])"
    )
    if re.search(context_pattern, text, re.I):
        return True
    # Longer alphanumeric factory codes (e.g., NH883P, YR607M) rarely collide with part/body IDs.
    has_mixed_alnum = bool(re.search(r"[a-z]", paint_code, re.I) and re.search(r"\d", paint_code))
    if len(paint_code) >= 4 and has_mixed_alnum:
        return bool(re.search(r"(?<![a-zа-я0-9])" + code_pat + r"(?![a-zа-я0-9])", text, re.I))
    return False


def is_accessory_listing(name: str) -> bool:
    """Reject standalone trim/mounts while keeping complete doors or bumpers sold in assembly."""
    head = _ASSEMBLY_SUFFIX_RE.sub("", name).strip()
    return bool(_ACCESSORIES.search(head))


def is_disqualified_listing(name: str, text: str, criteria: PartCriteria) -> bool:
    """Return True when title/snippet signals damage, backorder, glass mismatch, or trim."""
    clean = re.sub(r"без (?:повреждений|дефектов|вмятин|трещин)", "", text, flags=re.I)
    is_glass_for_non_glass = criteria.panel_id != "windshield" and bool(
        _NON_WINDSHIELD_GLASS.search(name)
    )
    return bool(
        is_accessory_listing(name)
        or is_glass_for_non_glass
        or _DAMAGE.search(clean)
        or _UNAVAILABLE.search(text)
        or _NEW_OR_AFTERMARKET.search(text)
    )
