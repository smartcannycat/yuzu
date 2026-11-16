"""Concurrent step execution, OCR orchestration, and lot completeness checks."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection

from apps.core.enums import ItemProcessingStatus, TaskStep
from apps.lots.media import attach_uploaded_sheet_media_from_item
from apps.lots.models import BatchItem
from apps.lots.pipeline.stages import (
    _advance_step,
    _fail_item,
    _missing_summary_fields,
    has_full_detail,
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
    from apps.lots import pipeline as pipeline_pkg

    if not settings.LOT_PARSER_BACKEND:
        _fail_item(item, TaskStep.FAILED, "Сервис распознавания не настроен")
        return False
    try:
        parser = pipeline_pkg.import_string(settings.LOT_PARSER_BACKEND)()
        rejection = parser.gatekeeper(item)
        if rejection:
            _fail_item(item, TaskStep.FAILED, rejection)
            return False
        _advance_step(item, TaskStep.FAST_HEADER_OCR)
        item.preview_title = parser.fast_header(item)
        item.save(update_fields=["preview_title", "updated_at"])
        _advance_step(item, TaskStep.GEMINI_OCR)
        parser.parse(item)
        item.lot.refresh_from_db()
        if not item.lot.make or not item.lot.model:
            _fail_item(item, TaskStep.FAILED, "Распознавание не вернуло марку и модель")
            return False
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
