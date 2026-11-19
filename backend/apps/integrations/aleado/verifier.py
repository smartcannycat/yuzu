"""Aleado candidate verification with Redis shortcuts, OCR overlap, and soft budget."""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import httpx

from apps.integrations.aleado.client import AleadoUnavailableError
from apps.integrations.aleado.comparator import _VerifiedRow
from apps.integrations.aleado.matcher import _normalize_frame_id
from apps.integrations.aleado.parser import AleadoParseError
from apps.integrations.ml.client import MlServiceError, MlServiceUnavailableError

if TYPE_CHECKING:
    from apps.integrations.aleado.cache import AleadoCache
    from apps.integrations.aleado.client import AleadoClient
    from apps.integrations.aleado.parser import AleadoLotDetail, AleadoLotRow
    from apps.integrations.ml.client import MlServiceClient

logger = logging.getLogger(__name__)

_ALEADO_FETCH_ERRORS = (AleadoParseError, AleadoUnavailableError, ValueError, httpx.HTTPError)
_ML_OCR_ERRORS = (MlServiceError, MlServiceUnavailableError, ValueError, httpx.HTTPError)


def _budget_expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _resolve_detail(
    internal_id: str,
    *,
    client: AleadoClient,
    cache: AleadoCache | None,
    deadline: float | None,
) -> tuple[AleadoLotDetail | None, bool]:
    if cache is not None:
        cached = cache.get_detail(internal_id)
        if cached is not None:
            return cached, False
    if _budget_expired(deadline):
        return None, True
    detail = client.get_lot_detail(internal_id)
    if cache is not None:
        cache.set_detail(internal_id, detail)
    return detail, False


def _handle_cached_chassis(
    *,
    idx: int,
    candidate: AleadoLotRow,
    cached_chassis: str,
    expected_frame_id: str,
    client: AleadoClient,
    cache: AleadoCache | None,
    deadline: float | None,
    lot_pk: Any,
    results_by_index: dict[int, _VerifiedRow],
) -> bool:
    """Resolve a cached chassis hit without OCR; returns True if the budget expired."""
    if _normalize_frame_id(cached_chassis) != expected_frame_id:
        return False
    assert candidate.internal_id is not None
    try:
        detail, timed_out = _resolve_detail(
            candidate.internal_id,
            client=client,
            cache=cache,
            deadline=deadline,
        )
    except _ALEADO_FETCH_ERRORS as exc:
        logger.warning(
            "Aleado detail lookup failed for cached candidate %s (lot %s): %s",
            candidate.internal_id,
            lot_pk,
            exc,
        )
        return False
    if timed_out or detail is None:
        return True
    results_by_index[idx] = _VerifiedRow(candidate, detail)
    return False


def _fetch_candidate_image(
    *,
    candidate: AleadoLotRow,
    client: AleadoClient,
    cache: AleadoCache | None,
    deadline: float | None,
    lot_pk: Any,
) -> tuple[AleadoLotDetail | None, bytes | None, bool]:
    """Fetch candidate detail and chassis image within budget."""
    assert candidate.internal_id is not None
    if _budget_expired(deadline):
        return None, None, True
    try:
        detail, timed_out = _resolve_detail(
            candidate.internal_id,
            client=client,
            cache=cache,
            deadline=deadline,
        )
        if timed_out or detail is None:
            return None, None, True
        if not detail.chassis_image_url:
            return None, None, False
        if _budget_expired(deadline):
            return None, None, True
        return detail, client.fetch_chassis_image(detail), False
    except _ALEADO_FETCH_ERRORS as exc:
        logger.warning(
            "Aleado chassis fetch failed for candidate %s (lot %s): %s",
            candidate.internal_id,
            lot_pk,
            exc,
        )
        return None, None, False


def _collect_ocr_results(
    lot_pk: Any,
    expected_frame_id: str,
    pending_ocr: list[tuple[int, AleadoLotRow, AleadoLotDetail, Future[Any]]],
    cache: AleadoCache | None,
    results_by_index: dict[int, _VerifiedRow],
) -> None:
    for idx, candidate, detail, future in pending_ocr:
        try:
            chassis_read = future.result()
        except _ML_OCR_ERRORS as exc:
            logger.warning(
                "Aleado chassis OCR failed for candidate %s (lot %s): %s",
                candidate.internal_id,
                lot_pk,
                exc,
            )
            continue
        if chassis_read is None or not chassis_read.frame_id:
            continue
        normalized = _normalize_frame_id(chassis_read.frame_id)
        if not normalized:
            continue
        if cache is not None and candidate.internal_id:
            cache.set_chassis(candidate.internal_id, normalized)
        if normalized == expected_frame_id:
            results_by_index[idx] = _VerifiedRow(candidate, detail)


def verify_candidates(
    *,
    lot_pk: Any,
    candidates: list[AleadoLotRow],
    expected_frame_id: str,
    client: AleadoClient,
    ml_client: MlServiceClient,
    cache: AleadoCache | None = None,
    budget_sec: float | None = None,
    ocr_max_workers: int = 3,
) -> list[_VerifiedRow]:
    """Verify candidate Aleado rows against ``expected_frame_id`` deterministically."""
    if not candidates or not expected_frame_id:
        return []

    deadline = time.monotonic() + budget_sec if budget_sec and budget_sec > 0 else None
    results_by_index: dict[int, _VerifiedRow] = {}
    pending_ocr: list[tuple[int, AleadoLotRow, AleadoLotDetail, Future[Any]]] = []

    with ThreadPoolExecutor(max_workers=max(1, ocr_max_workers)) as ocr_pool:
        for idx, candidate in enumerate(candidates):
            if not candidate.internal_id:
                continue
            cached_chassis = cache.get_chassis(candidate.internal_id) if cache is not None else None
            if cached_chassis is not None:
                timed_out = _handle_cached_chassis(
                    idx=idx,
                    candidate=candidate,
                    cached_chassis=cached_chassis,
                    expected_frame_id=expected_frame_id,
                    client=client,
                    cache=cache,
                    deadline=deadline,
                    lot_pk=lot_pk,
                    results_by_index=results_by_index,
                )
                if timed_out:
                    logger.info("Aleado candidate verification budget reached for lot %s", lot_pk)
                    break
                continue

            detail, image_bytes, timed_out = _fetch_candidate_image(
                candidate=candidate,
                client=client,
                cache=cache,
                deadline=deadline,
                lot_pk=lot_pk,
            )
            if timed_out:
                logger.info("Aleado candidate verification budget reached for lot %s", lot_pk)
                break
            if detail is not None and image_bytes is not None:
                pending_ocr.append(
                    (idx, candidate, detail, ocr_pool.submit(ml_client.read_chassis, image_bytes))
                )

        _collect_ocr_results(lot_pk, expected_frame_id, pending_ocr, cache, results_by_index)

    return [results_by_index[i] for i in sorted(results_by_index)]
