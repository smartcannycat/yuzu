"""Batch pipeline DAG runner and worker startup recovery."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import connection, transaction
from django.utils import timezone

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.core.redis_utils import get_redis_client
from apps.lots.models import Batch, BatchItem
from apps.lots.pipeline.parallel import _run_ocr_stage, _run_parallel_steps, _validate_ready_lot
from apps.lots.pipeline.stages import (
    _advance_step,
    _claim_next_queued_item,
    _complete_item,
    _step_cross_audit,
    _step_customs_calc,
    _step_drom_market,
    _step_farpost_parts,
    _step_gatekeeper,
    _step_scoring,
)

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

logger = logging.getLogger(__name__)


def _process_item(item: BatchItem) -> None:
    if not _step_gatekeeper(item) or not _run_ocr_stage(item):
        return
    _advance_step(item, TaskStep.CROSS_AUDIT)
    if not _run_parallel_steps(
        item,
        [_step_cross_audit, _step_drom_market, _step_farpost_parts],
    ):
        return
    if item.lot is not None:
        item.lot.refresh_from_db()
    if not _step_customs_calc(item) or not _step_scoring(item):
        return
    if not _validate_ready_lot(item):
        return
    _complete_item(item)


def _finalize_batch_locked(batch: Batch) -> None:
    items = list(batch.items.all())
    total = len(items)
    ready = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    if total == 0:
        status = BatchStatus.FAILED
    elif ready == total:
        status = BatchStatus.COMPLETED
    elif failed == total:
        status = BatchStatus.FAILED
    else:
        status = BatchStatus.PARTIAL_FAILED
    batch.status = status
    batch.save(update_fields=["status", "updated_at"])


def run_batch_pipeline(batch_id: uuid.UUID) -> None:
    """Process all queued items in a batch sequentially and finalize batch status."""
    try:
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            if batch.status != BatchStatus.QUEUED:
                return
            batch.status = BatchStatus.PROCESSING
            batch.save(update_fields=["status", "updated_at"])
        while True:
            item = _claim_next_queued_item(batch_id)
            if item is not None:
                _process_item(item)
                Batch.objects.filter(pk=batch_id).update(updated_at=timezone.now())
                continue
            with transaction.atomic():
                batch = Batch.objects.select_for_update().get(id=batch_id)
                if batch.items.filter(status=ItemProcessingStatus.QUEUED).exists():
                    continue
                _finalize_batch_locked(batch)
                break
    except Exception:
        logger.exception("Batch pipeline failed for %s", batch_id)
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            batch.items.filter(
                status__in=(ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING)
            ).update(
                status=ItemProcessingStatus.FAILED,
                current_step=TaskStep.FAILED,
                error_message="Не удалось обработать аукционный лист",
                updated_at=timezone.now(),
            )
            _finalize_batch_locked(batch)
    finally:
        connection.close()


def recover_batches_on_startup(
    *,
    stale_before: datetime | None = None,
    use_startup_lock: bool = True,
) -> int:
    """Requeue interrupted batches when a background worker starts or recovers."""
    if use_startup_lock:
        client = get_redis_client()
        if client is not None:
            try:
                if not client.set("yuzu:recovery:startup_lock", "1", nx=True, ex=60):
                    return 0
            except Exception:
                logger.warning("Could not acquire Redis startup recovery lock", exc_info=True)

    stuck_statuses = [BatchStatus.QUEUED, BatchStatus.PROCESSING]
    batches = Batch.objects.filter(status__in=stuck_statuses)
    if stale_before is not None:
        batches = batches.filter(updated_at__lte=stale_before)

    from apps.lots.tasks import process_batch_task

    requeued = 0
    for batch in batches:
        with transaction.atomic():
            locked = Batch.objects.select_for_update().filter(
                id=batch.id,
                status__in=stuck_statuses,
            )
            if stale_before is not None:
                locked = locked.filter(updated_at__lte=stale_before)
            target = locked.first()
            if target is None:
                continue
            BatchItem.objects.filter(
                batch=target,
                status=ItemProcessingStatus.PROCESSING,
            ).update(
                status=ItemProcessingStatus.QUEUED,
                current_step=TaskStep.GATEKEEPER,
                updated_at=timezone.now(),
            )
            target.status = BatchStatus.QUEUED
            target.save(update_fields=["status", "updated_at"])
        process_batch_task.delay(str(batch.id))
        requeued += 1
    return requeued
