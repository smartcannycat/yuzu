"""Candidate model-code normalization, own-lot filtering, and mileage prioritization."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from apps.integrations.shared.katashiki import extract_aleado_body_code

if TYPE_CHECKING:
    from apps.integrations.aleado.parser import AleadoLotRow
    from apps.lots.models import Lot


def clean_model_code(lot: Lot) -> str:
    """Derive the Aleado model type code from the lot's frame/model code."""
    return extract_aleado_body_code(lot.frame_id, lot.model_code)


def _matches_house_token(needle: str, haystack: str) -> bool:
    if not needle or not haystack:
        return False
    if needle == haystack:
        return True
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(needle)}(?![A-Z0-9])", haystack))


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
    return _matches_house_token(branch, house) or _matches_house_token(own_house, house)


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
