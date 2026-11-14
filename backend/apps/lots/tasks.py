"""Celery background tasks for batch pipeline processing, recovery, and media purge."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.utils import timezone

from celery import shared_task

logger = logging.getLogger(__name__)

_STUCK_BATCH_AGE_MINUTES = 15


@shared_task(name="apps.lots.tasks.process_batch_task", ignore_result=True)
def process_batch_task(batch_id: str) -> None:
    """Execute the full batch processing pipeline inside the Celery worker."""
    from apps.lots.pipeline import run_batch_pipeline

    run_batch_pipeline(uuid.UUID(batch_id))


@shared_task(name="apps.lots.tasks.recover_stuck_batches_task", ignore_result=True)
def recover_stuck_batches_task() -> int:
    """Requeue batches stuck in QUEUED or PROCESSING beyond the staleness threshold."""
    from apps.lots.pipeline import recover_batches_on_startup

    stale_before = timezone.now() - timedelta(minutes=_STUCK_BATCH_AGE_MINUTES)
    return recover_batches_on_startup(stale_before=stale_before, use_startup_lock=False)


@shared_task(name="apps.lots.tasks.purge_stale_media_task", ignore_result=True)
def purge_stale_media_task() -> dict[str, int]:
    """Periodically remove expired media files for deleted lots and finished uploads."""
    from apps.lots.media_purge import purge_stale_media

    result = purge_stale_media()
    logger.info("Purged stale media: %s", result)
    return result
