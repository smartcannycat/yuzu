"""Candidate model-code normalization, own-lot filtering, and mileage prioritization."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.integrations.aleado.parser import AleadoLotRow
    from apps.lots.models import Lot

_BODY_CODE_RE = re.compile(r"[A-Z]{1,5}\d{1,4}[A-Z]{0,2}")


def clean_model_code(lot: Lot) -> str:
    """Derive the Aleado model type code from the lot's frame/model code.

    Strips emission prefixes ("6BA-GB5" -> "GB5", "DAA-RU3" -> "RU3") and
    trailing spec suffixes ("3BA-NRE210W-AWXNB" -> "NRE210W").
    A Frame ID ("GB5-1025108") contributes the part before the dash.
    """
    for value in (lot.frame_id, lot.model_code):
        code = (value or "").upper().strip()
        if not code:
            continue
        parts = [part for part in code.split("-") if part]
        if len(parts) == 2 and parts[-1].isdigit() and _BODY_CODE_RE.fullmatch(parts[0]):
            return parts[0]
        if len(parts) >= 2:
            for part in parts[1:]:
                if _BODY_CODE_RE.fullmatch(part):
                    return part
        if _BODY_CODE_RE.fullmatch(parts[0]):
            return parts[0]
    return ""


def _candidate_is_own_lot(row: AleadoLotRow, lot: Lot) -> bool:
    """Identify whether a catalog candidate is the audited lot itself."""
    own_lot_number = (lot.lot_number or "").strip()
    if not own_lot_number or not row.lot_number:
        return False
    if row.lot_number.strip() != own_lot_number:
        return False
    own_house = (lot.auction_house or "").upper().strip()
    branch = (lot.auction_branch or "").upper().strip()
    house = row.auction_house.upper().strip()
    return (bool(branch) and branch in house) or (
        bool(own_house) and (house.startswith(own_house) or own_house in house)
    )


def _normalize_frame_id(value: str | None) -> str:
    """Normalize a frame id for comparison: uppercase, no internal spaces."""
    return re.sub(r"\s+", "", (value or "").strip().upper())


def select_and_sort_candidates(
    rows: list[AleadoLotRow],
    lot: Lot,
    model_code: str,
) -> tuple[list[AleadoLotRow], bool]:
    """Filter candidates matching ``model_code``, strip own lot, and order closest mileage first."""
    candidates: list[AleadoLotRow] = []
    includes_own = False
    for row in rows:
        if row.model_type and row.model_type.upper() != model_code:
            continue
        if _candidate_is_own_lot(row, lot):
            includes_own = True
            continue
        candidates.append(row)

    candidates.sort(
        key=lambda r: (
            r.mileage_km is None,
            abs(r.mileage_km - lot.mileage_km)
            if r.mileage_km is not None and lot.mileage_km is not None
            else 0,
        )
    )
    return candidates, includes_own
