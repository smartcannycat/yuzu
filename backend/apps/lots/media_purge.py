"""Media retention and cleanup helpers for soft-deleted lots and processed uploads."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.core.enums import BatchStatus, ItemProcessingStatus
from apps.lots.models import BatchItem, Lot

logger = logging.getLogger(__name__)

_TERMINAL_BATCH_STATUSES = (
    BatchStatus.COMPLETED,
    BatchStatus.FAILED,
    BatchStatus.PARTIAL_FAILED,
)


def _delete_field_file(instance: object, field_name: str) -> bool:
    field_file = getattr(instance, field_name, None)
    if not field_file or not getattr(field_file, "name", ""):
        return False
    try:
        field_file.delete(save=False)
    except OSError as exc:
        logger.warning("Failed to delete media file %s: %s", field_file.name, exc)
        return False
    setattr(instance, field_name, "")
    return True


def purge_stale_media(
    *,
    deleted_after_days: int | None = None,
    originals_after_hours: int | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete media files for aged soft-deleted lots and completed batch uploads."""
    moment = now or timezone.now()
    del_days = (
        getattr(settings, "MEDIA_PURGE_DELETED_AFTER_DAYS", 7)
        if deleted_after_days is None
        else deleted_after_days
    )
    orig_hours = (
        getattr(settings, "MEDIA_PURGE_BATCH_ORIGINALS_AFTER_HOURS", 24)
        if originals_after_hours is None
        else originals_after_hours
    )

    deleted_lots_files = 0
    batch_originals_files = 0

    deleted_cutoff = moment - timedelta(days=del_days)
    deleted_lots = (
        Lot.objects.filter(deleted_at__isnull=False, deleted_at__lte=deleted_cutoff)
        .select_related("batch_item")
        .iterator(chunk_size=100)
    )
    for lot in deleted_lots:
        changed_fields: list[str] = []
        if _delete_field_file(lot, "sheet_scan"):
            deleted_lots_files += 1
            changed_fields.append("sheet_scan")
        if _delete_field_file(lot, "sheet_thumbnail"):
            deleted_lots_files += 1
            changed_fields.append("sheet_thumbnail")
        if changed_fields:
            lot.save(update_fields=[*changed_fields, "updated_at"])
        item = getattr(lot, "batch_item", None)
        if item is not None and _delete_field_file(item, "original_file"):
            batch_originals_files += 1
            item.save(update_fields=["original_file", "updated_at"])

    originals_cutoff = moment - timedelta(hours=orig_hours)
    terminal_items = (
        BatchItem.objects.filter(
            batch__status__in=_TERMINAL_BATCH_STATUSES,
            batch__updated_at__lte=originals_cutoff,
            status__in=(ItemProcessingStatus.READY, ItemProcessingStatus.FAILED),
        )
        .exclude(original_file="")
        .iterator(chunk_size=100)
    )
    for item in terminal_items:
        if _delete_field_file(item, "original_file"):
            batch_originals_files += 1
            item.save(update_fields=["original_file", "updated_at"])

    return {
        "deleted_lots_files": deleted_lots_files,
        "batch_originals_files": batch_originals_files,
    }
