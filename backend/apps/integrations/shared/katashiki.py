"""Shared Japanese katashiki / chassis body-code parsing and matching helpers."""

from __future__ import annotations

import re

BODY_CODE_RE = re.compile(r"[A-Z]{1,5}\d{1,4}[A-Z]{0,2}")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


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


def matches_katashiki_token(
    text: str,
    candidate: str,
    *,
    allow_body_suffix: bool = False,
) -> bool:
    """Return True if candidate appears as an alphanumeric token in text."""
    suffix = "[A-Z]?" if allow_body_suffix and candidate[-1:].isdigit() else ""
    pattern = rf"(?<![A-Z0-9]){re.escape(candidate)}{suffix}(?![A-Z0-9])"
    return bool(re.search(pattern, text.upper()))


def extract_aleado_body_code(*values: str | None) -> str:
    """Derive the Aleado model type code from frame_id / model_code values."""
    for value in values:
        code = (value or "").upper().strip()
        if not code:
            continue
        parts = [part for part in code.split("-") if part]
        if len(parts) == 2 and parts[-1].isdigit() and BODY_CODE_RE.fullmatch(parts[0]):
            return parts[0]
        if len(parts) >= 2:
            for part in parts[1:]:
                if BODY_CODE_RE.fullmatch(part):
                    return part
        if BODY_CODE_RE.fullmatch(parts[0]):
            return parts[0]
    return ""


def extract_farpost_body_code(
    *,
    frame_id: str | None = None,
    chassis_number: str | None = None,
    model_code: str | None = None,
) -> str:
    """Prefer the raw chassis series (GB5, NRE210) for Farpost parts queries."""
    candidates: list[str] = []
    for value in (frame_id, chassis_number):
        upper = (value or "").upper().strip()
        if not upper:
            continue
        if "-" not in upper and VIN_RE.fullmatch(upper):
            # 17-char VINs do not start with a searchable Farpost chassis series.
            continue
        candidates.append(upper.split("-", 1)[0])
    if model_code:
        upper = model_code.upper().strip()
        if "-" in upper:
            candidates.append(upper.split("-", 1)[1])
        candidates.append(upper)
    for candidate in candidates:
        match = BODY_CODE_RE.search(candidate)
        if match:
            return match[0]
    return ""
