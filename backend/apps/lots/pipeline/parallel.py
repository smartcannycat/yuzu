"""Concurrent step execution, OCR orchestration, and lot completeness checks."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection
from django.utils.module_loading import import_string

from apps.core.enums import ItemProcessingStatus, TaskStep
from apps.lots.media import attach_uploaded_sheet_media_from_item
from apps.lots.models import BatchItem, has_full_detail
from apps.lots.pipeline.leases import managed_closing
from apps.lots.pipeline.stages import (
    _advance_step,
    _fail_item,
    _missing_summary_fields,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def _run_step_in_worker(step_fn: Callable[[BatchItem], bool], item: BatchItem) -> bool:
    try:
        return bool(step_fn(item))
    except Exception:
        logger.exception("Parallel pipeline step %s crashed for item %s", step_fn.__name__, item.pk)
        try:
            already_failed = BatchItem.objects.filter(
                pk=item.pk,
                status=ItemProcessingStatus.FAILED,
            ).exists()
            if not already_failed:
                _fail_item(item, TaskStep.FAILED, "Внутренняя ошибка при обработке лота")
        except Exception:
            logger.exception("Failed to mark item %s as FAILED after step crash", item.pk)
        return False
    finally:
        connection.close()


def _run_parallel_steps(item: BatchItem, step_fns: list[Callable[[BatchItem], bool]]) -> bool:
    pool = ThreadPoolExecutor(max_workers=len(step_fns))
    all_ok = True
    try:
        futures = {pool.submit(_run_step_in_worker, fn, item): fn for fn in step_fns}
        for future in as_completed(futures):
            if not future.result():
                all_ok = False
                break
        return all_ok
    finally:
        # Cancel unstarted futures while waiting for already-started threads.
        pool.shutdown(wait=True, cancel_futures=not all_ok)


def _run_ocr_stage(item: BatchItem) -> bool:
    if not settings.LOT_PARSER_BACKEND:
        _fail_item(item, TaskStep.FAILED, "Сервис распознавания не настроен")
        return False
    try:
        if not connection.in_atomic_block:
            connection.close()
        with managed_closing(import_string(settings.LOT_PARSER_BACKEND)()) as parser:
            rejection = parser.gatekeeper(item)
            if rejection:
                _fail_item(item, TaskStep.FAILED, rejection)
                return False
            _advance_step(item, TaskStep.GEMINI_OCR)
            parser.parse(item)
        item.lot.refresh_from_db()
        if not item.lot.make or not item.lot.model:
            _fail_item(item, TaskStep.FAILED, "Распознавание не вернуло марку и модель")
            return False
        preview_base = " ".join(
            part.strip() for part in (item.lot.make, item.lot.model) if part and part.strip()
        )
        lot_no = (item.lot.lot_number or "").strip()
        preview_title = (
            f"{preview_base} #{lot_no}" if preview_base and lot_no else preview_base or None
        )
        if preview_title:
            item.preview_title = preview_title[:200]
            item.save(update_fields=["preview_title", "updated_at"])
        attach_uploaded_sheet_media_from_item(item)
        return True
    except Exception:
        logger.exception("Parser failed for batch item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось распознать аукционный лист")
        return False


def _validate_ready_lot(item: BatchItem) -> bool:
    if item.lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    missing = _missing_summary_fields(item.lot)
    if missing:
        _fail_item(
            item,
            TaskStep.FAILED,
            f"Недостаточно данных для карточки лота: {', '.join(missing)}",
        )
        return False
    item.lot.refresh_from_db()
    if not has_full_detail(item.lot):
        _fail_item(
            item,
            TaskStep.FAILED,
            "Недостаточно данных для детальной карточки лота",
        )
        return False
    return True
