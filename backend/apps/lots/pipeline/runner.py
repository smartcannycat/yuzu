"""Batch pipeline DAG runner and worker startup recovery."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import connection, transaction
from django.utils import timezone

from apps.core import redis_utils
from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.lots.models import Batch, BatchItem
from apps.lots.pipeline.leases import (
    acquire_batch_lease,
    is_batch_lease_held,
    release_batch_lease,
    renew_batch_lease,
)
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


def _claim_batch_for_processing(batch_id: uuid.UUID) -> bool:
    with transaction.atomic():
        batch = Batch.objects.select_for_update().filter(id=batch_id).first()
        if batch is None or batch.status not in (BatchStatus.QUEUED, BatchStatus.PROCESSING):
            return False
        BatchItem.objects.filter(
            batch=batch,
            status=ItemProcessingStatus.PROCESSING,
        ).update(
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
            updated_at=timezone.now(),
        )
        batch.status = BatchStatus.PROCESSING
        batch.save(update_fields=["status", "updated_at"])
        return True


def _mark_batch_failed_safely(batch_id: uuid.UUID) -> None:
    try:
        with transaction.atomic():
            batch = Batch.objects.select_for_update().filter(id=batch_id).first()
            if batch is None:
                return
            batch.items.filter(
                status__in=(ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING)
            ).update(
                status=ItemProcessingStatus.FAILED,
                current_step=TaskStep.FAILED,
                error_message="Не удалось обработать аукционный лист",
                updated_at=timezone.now(),
            )
            _finalize_batch_locked(batch)
    except Exception:
        logger.exception("Failed to mark batch %s as FAILED after pipeline crash", batch_id)


def run_batch_pipeline(batch_id: uuid.UUID) -> None:
    """Process all queued items in a batch sequentially and finalize batch status."""
    if not acquire_batch_lease(batch_id):
        logger.info("Skipping batch %s: active lease held or Redis lock unavailable", batch_id)
        return
    try:
        if not _claim_batch_for_processing(batch_id):
            return
        while True:
            item = _claim_next_queued_item(batch_id)
            if item is not None:
                _process_item(item)
                Batch.objects.filter(pk=batch_id).update(updated_at=timezone.now())
                renew_batch_lease(batch_id)
                continue
            with transaction.atomic():
                batch = Batch.objects.select_for_update().filter(id=batch_id).first()
                if batch is None:
                    break
                if batch.items.filter(status=ItemProcessingStatus.QUEUED).exists():
                    continue
                _finalize_batch_locked(batch)
                break
    except Exception:
        logger.exception("Batch pipeline failed for %s", batch_id)
        _mark_batch_failed_safely(batch_id)
    finally:
        release_batch_lease(batch_id)
        connection.close()


def _acquire_startup_recovery_lock() -> bool:
    client = redis_utils.get_redis_client()
    if client is None:
        return True
    try:
        return bool(client.set("yuzu:recovery:startup_lock", "1", nx=True, ex=60))
    except Exception:
        logger.warning(
            "Could not acquire Redis startup recovery lock; skipping recovery",
            exc_info=True,
        )
        return False


def recover_batches_on_startup(
    *,
    stale_before: datetime | None = None,
    use_startup_lock: bool = True,
) -> int:
    """Requeue interrupted batches when a background worker starts or recovers."""
    if use_startup_lock and not _acquire_startup_recovery_lock():
        return 0

    stuck_statuses = [BatchStatus.QUEUED, BatchStatus.PROCESSING]
    batches = Batch.objects.filter(status__in=stuck_statuses)
    if stale_before is not None:
        batches = batches.filter(updated_at__lte=stale_before)

    from apps.lots.tasks import process_batch_task

    requeued = 0
    for batch in batches:
        if is_batch_lease_held(batch.id):
            continue
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
