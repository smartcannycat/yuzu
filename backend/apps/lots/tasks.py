"""Celery background tasks for batch pipeline processing, recovery, and media purge."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from celery import shared_task

logger = logging.getLogger(__name__)

_STUCK_BATCH_AGE_MINUTES = 15


def _close_idle_db_connection() -> None:
    if not connection.in_atomic_block:
        connection.close()


@shared_task(name="apps.lots.tasks.process_batch_task", ignore_result=True)
def process_batch_task(batch_id: str) -> None:
    """Execute the full batch processing pipeline inside the Celery worker."""
    from apps.lots.pipeline import run_batch_pipeline

    run_batch_pipeline(uuid.UUID(batch_id))


@shared_task(name="apps.lots.tasks.recover_stuck_batches_task", ignore_result=True)
def recover_stuck_batches_task() -> int:
    """Requeue batches stuck in QUEUED or PROCESSING beyond the staleness threshold."""
    from apps.lots.pipeline import recover_batches_on_startup

    try:
        stale_before = timezone.now() - timedelta(minutes=_STUCK_BATCH_AGE_MINUTES)
        return recover_batches_on_startup(stale_before=stale_before, use_startup_lock=False)
    finally:
        _close_idle_db_connection()


@shared_task(name="apps.lots.tasks.purge_stale_media_task", ignore_result=True)
def purge_stale_media_task() -> dict[str, int]:
    """Periodically remove expired media files for deleted lots and finished uploads."""
    from apps.lots.media_purge import purge_stale_media

    try:
        result = purge_stale_media()
        logger.info("Purged stale media: %s", result)
        return result
    finally:
        _close_idle_db_connection()


@shared_task(name="apps.lots.tasks.archive_expired_lots_task", ignore_result=True)
def archive_expired_lots_task() -> int:
    """Periodically archive active completed lots whose expiration deadline has passed."""
    from apps.lots.lifecycle import archive_expired_lots

    try:
        archived = archive_expired_lots()
        if archived:
            logger.info("Archived %s expired lots", archived)
        return archived
    finally:
        _close_idle_db_connection()
