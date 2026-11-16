"""API serializers and entrypoints for batch upload and polling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.core.enums import BatchStatus, ItemProcessingStatus, MascotMood
from apps.lots.api.queries import _build_lot_summary
from apps.lots.api.schemas import (
    BatchCreateResponse,
    BatchItemStatus,
    BatchProgressResponse,
    LotSummary,
    MascotState,
)
from apps.lots.pipeline.batches import (
    _POLL_INTERVAL_MS,
    append_items_to_batch,
    enqueue_batch,
    load_user_batch,
)

if TYPE_CHECKING:
    import uuid

    from django.core.files.uploadedfile import UploadedFile

    from apps.lots.models import Batch, BatchItem
    from apps.users.models import User


def _build_mascot(status: str, ready_count: int, total_count: int) -> MascotState:
    if status == BatchStatus.COMPLETED:
        return MascotState(
            mood=MascotMood.HAPPY,
            phrase_ru=f"Все лоты готовы! {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.PARTIAL_FAILED:
        return MascotState(
            mood=MascotMood.CONFUSED,
            phrase_ru=f"Часть листов не распознана. Готово {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.FAILED:
        return MascotState(
            mood=MascotMood.WARNING,
            phrase_ru="Не удалось обработать листы",
            badge_text=f"0 из {total_count} готово",
        )
    return MascotState(
        mood=MascotMood.THINKING,
        phrase_ru=f"Распознаем лоты... {ready_count}/{total_count}",
        badge_text=f"{ready_count} из {total_count} готово",
    )


def _build_item_status(item: BatchItem) -> BatchItemStatus:
    is_deleted = item.lot is not None and item.lot.deleted_at is not None
    summary: LotSummary | None = None
    if (
        not is_deleted
        and item.status == ItemProcessingStatus.READY
        and item.lot is not None
        and item.lot.make
    ):
        summary = _build_lot_summary(item.lot)
    return BatchItemStatus(
        lot_id=None if is_deleted else item.lot_id,
        file_index=item.file_index,
        original_filename=item.original_filename,
        preview_title=item.preview_title,
        status=item.status,
        current_step=item.current_step,
        error_message=item.error_message,
        summary=summary,
    )


def _build_batch_progress(batch: Batch) -> BatchProgressResponse:
    items = list(batch.items.order_by("file_index").select_related("lot"))
    ready_count = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed_count = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    return BatchProgressResponse(
        batch_id=batch.id,
        status=batch.status,
        mascot=_build_mascot(batch.status, ready_count, len(items)),
        total_count=len(items),
        processed_count=ready_count + failed_count,
        ready_count=ready_count,
        failed_count=failed_count,
        items=[_build_item_status(item) for item in items],
    )


def create_batch(user: User, files: list[UploadedFile]) -> BatchCreateResponse:
    """Validate uploaded sheets, create a batch, and schedule background processing."""
    batch = enqueue_batch(user, files)
    return BatchCreateResponse(
        batch_id=batch.id,
        total_items=len(files),
        status=batch.status,
        created_at=batch.created_at,
        poll_interval_ms=_POLL_INTERVAL_MS,
    )


def append_batch_items(
    user: User,
    batch_id: uuid.UUID,
    files: list[UploadedFile],
) -> BatchProgressResponse:
    """Append additional auction sheets to an active or partial-failed batch."""
    batch = append_items_to_batch(user, batch_id, files)
    return _build_batch_progress(batch)


def get_batch_progress(user: User, batch_id: uuid.UUID) -> BatchProgressResponse:
    """Return current processing progress and item statuses for a user's batch."""
    return _build_batch_progress(load_user_batch(user, batch_id))
