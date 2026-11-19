"""Batch pipeline DAG runner and worker startup recovery."""

from __future__ import annotations

import logging
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TYPE_CHECKING

from django.conf import settings
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
    _fail_item,
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


def _close_idle_db_connection() -> None:
    if not connection.in_atomic_block:
        connection.close()


def _process_item(item: BatchItem) -> None:
    if not _step_gatekeeper(item) or not _run_ocr_stage(item):
        return
    _advance_step(item, TaskStep.CROSS_AUDIT)
    _close_idle_db_connection()
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


def _run_item_in_worker(item: BatchItem) -> None:
    try:
        _process_item(item)
    except Exception:
        logger.exception("Pipeline item %s crashed unexpectedly", item.pk)
        try:
            already_failed = BatchItem.objects.filter(
                pk=item.pk,
                status=ItemProcessingStatus.FAILED,
            ).exists()
            if not already_failed:
                _fail_item(item, TaskStep.FAILED, "Не удалось обработать аукционный лист")
        except Exception:
            logger.exception("Failed to mark crashed item %s as FAILED", item.pk)
    finally:
        _close_idle_db_connection()


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


def _submit_available_items(
    batch_id: uuid.UUID,
    pool: ThreadPoolExecutor,
    active: set[Future[None]],
    max_workers: int,
) -> None:
    while len(active) < max_workers:
        item = _claim_next_queued_item(batch_id)
        if item is None:
            break
        active.add(pool.submit(_run_item_in_worker, item))


def _finalize_if_drained(batch_id: uuid.UUID) -> bool:
    with transaction.atomic():
        batch = Batch.objects.select_for_update().filter(id=batch_id).first()
        if batch is None:
            return True
        if batch.items.filter(status=ItemProcessingStatus.QUEUED).exists():
            return False
        _finalize_batch_locked(batch)
        return True


def _drain_batch_items(batch_id: uuid.UUID, max_workers: int) -> None:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        active: set[Future[None]] = set()
        while True:
            _submit_available_items(batch_id, pool, active, max_workers)
            if not active:
                if _finalize_if_drained(batch_id):
                    break
                continue
            _close_idle_db_connection()
            done, active = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                future.result()
            Batch.objects.filter(pk=batch_id).update(updated_at=timezone.now())
            renew_batch_lease(batch_id)


def run_batch_pipeline(batch_id: uuid.UUID) -> None:
    """Process all queued items in a batch concurrently and finalize batch status."""
    if not acquire_batch_lease(batch_id):
        logger.info("Skipping batch %s: active lease held or Redis lock unavailable", batch_id)
        return
    max_workers = max(1, int(getattr(settings, "PIPELINE_BATCH_ITEM_CONCURRENCY", 4)))
    try:
        if not _claim_batch_for_processing(batch_id):
            return
        _drain_batch_items(batch_id, max_workers)
    except Exception:
        logger.exception("Batch pipeline failed for %s", batch_id)
        _mark_batch_failed_safely(batch_id)
    finally:
        release_batch_lease(batch_id)
        _close_idle_db_connection()


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
