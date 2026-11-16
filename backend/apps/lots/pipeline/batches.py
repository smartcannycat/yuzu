"""Uploaded auction-sheet validation, batch queueing, and pipeline scheduling."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Max

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.core.exceptions import (
    BadRequestProblemError,
    ConflictProblemError,
    NotFoundProblemError,
)
from apps.lots.models import Batch, BatchItem, Lot

if TYPE_CHECKING:
    import uuid

    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

_ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)
_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
_MAX_FILE_SIZE = 15 * 1024 * 1024
_MAX_FILES_PER_UPLOAD = 10
_MAX_FILES_PER_BATCH = 20
_POLL_INTERVAL_MS = 1500
_BATCH_TERMINAL_STATUSES = frozenset({BatchStatus.COMPLETED, BatchStatus.FAILED})


def _validate_single_file(upload: UploadedFile) -> None:
    name = upload.name or ""
    ext = Path(name).suffix.lower()
    content_type = (upload.content_type or "").lower()
    allowed = content_type in _ALLOWED_MIME_TYPES if content_type else ext in _ALLOWED_EXTENSIONS
    if not allowed:
        raise BadRequestProblemError(
            f"Файл «{name}» имеет недопустимый формат. Разрешены: JPEG, PNG, WEBP, HEIC, HEIF",
            title="Недопустимый формат файла",
        )
    if upload.size is None or upload.size > _MAX_FILE_SIZE:
        raise BadRequestProblemError(
            f"Файл «{name}» превышает максимальный размер {_MAX_FILE_SIZE // (1024 * 1024)} МБ",
            title="Превышен размер файла",
        )


def _validate_upload_files(files: list[UploadedFile]) -> None:
    if not files:
        raise BadRequestProblemError(
            "Не выбрано ни одного файла",
            title="Файлы не переданы",
        )
    if len(files) > _MAX_FILES_PER_UPLOAD:
        raise BadRequestProblemError(
            f"Можно загрузить не более {_MAX_FILES_PER_UPLOAD} файлов за один раз",
            title="Превышен лимит файлов",
        )
    for upload in files:
        _validate_single_file(upload)


def _next_file_index(batch: Batch) -> int:
    max_index = batch.items.aggregate(max=Max("file_index"))["max"]
    return (max_index if max_index is not None else -1) + 1


def _create_batch_items(
    batch: Batch,
    user: User,
    files: list[UploadedFile],
    *,
    start_index: int = 0,
) -> None:
    for offset, upload in enumerate(files):
        upload.seek(0)
        lot = Lot.objects.create(user=user)
        item = BatchItem.objects.create(
            batch=batch,
            lot=lot,
            file_index=start_index + offset,
            original_filename=upload.name,
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        item.original_file.save(upload.name, upload, save=True)


def _schedule_batch_pipeline(batch_id: uuid.UUID) -> None:
    from apps.lots.tasks import process_batch_task

    transaction.on_commit(lambda: process_batch_task.delay(str(batch_id)))


@transaction.atomic
def enqueue_batch(user: User, files: list[UploadedFile]) -> Batch:
    """Validate uploaded sheets, persist a new queued batch, and schedule processing."""
    from apps.lots import pipeline as pipeline_pkg

    _validate_upload_files(files)
    batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
    _create_batch_items(batch, user, files, start_index=0)
    pipeline_pkg._schedule_batch_pipeline(batch.id)
    return batch


@transaction.atomic
def append_items_to_batch(
    user: User,
    batch_id: uuid.UUID,
    files: list[UploadedFile],
) -> Batch:
    """Append additional auction sheets to an active or partial-failed batch."""
    from apps.lots import pipeline as pipeline_pkg

    _validate_upload_files(files)
    try:
        batch = Batch.objects.select_for_update().get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError("Пачка не найдена", title="Пачка не найдена") from exc
    if batch.status in _BATCH_TERMINAL_STATUSES:
        raise ConflictProblemError(
            "Пачка уже завершена. Откройте новую пачку через POST /api/v1/lots/batches",
            title="Пачка завершена",
        )
    if batch.items.count() + len(files) > _MAX_FILES_PER_BATCH:
        raise BadRequestProblemError(
            f"В одной пачке может быть не более {_MAX_FILES_PER_BATCH} файлов",
            title="Превышен лимит файлов в пачке",
        )
    _create_batch_items(batch, user, files, start_index=_next_file_index(batch))
    if batch.status == BatchStatus.PARTIAL_FAILED:
        batch.status = BatchStatus.QUEUED
        batch.save(update_fields=["status", "updated_at"])
        pipeline_pkg._schedule_batch_pipeline(batch.id)
    return batch


def load_user_batch(user: User, batch_id: uuid.UUID) -> Batch:
    """Fetch a user's batch or raise RFC 9457 NotFoundProblemError."""
    try:
        return Batch.objects.get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError("Пачка не найдена", title="Пачка не найдена") from exc
