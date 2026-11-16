import re


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
