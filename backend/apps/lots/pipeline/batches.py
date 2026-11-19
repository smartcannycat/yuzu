"""Uploaded auction-sheet validation, batch queueing, and pipeline scheduling."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Max
from PIL import Image, UnidentifiedImageError

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.core.exceptions import (
    BadRequestProblemError,
    ConflictProblemError,
    NotFoundProblemError,
)
from apps.lots.media import (
    MAX_IMAGE_PIXELS,
    ensure_heif_registered,
    ensure_safe_image_dimensions,
)
from apps.lots.models import Batch, BatchItem, Lot

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

logger = logging.getLogger(__name__)

_ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)
_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
_ALLOWED_PIL_FORMATS = ("JPEG", "PNG", "WEBP", "HEIF")
_MAX_FILE_SIZE = 15 * 1024 * 1024
_MAX_FILES_PER_UPLOAD = 10
_MAX_FILES_PER_BATCH = 20
_POLL_INTERVAL_MS = 1500
_BATCH_TERMINAL_STATUSES = frozenset({BatchStatus.COMPLETED, BatchStatus.FAILED})

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _sanitize_original_filename(raw_name: str | None) -> str:
    cleaned = (raw_name or "").replace("\\", "/").strip()
    leaf = Path(cleaned).name.strip()
    if not leaf or leaf in {".", ".."}:
        return "sheet"
    return leaf[:255]


def _verify_uploaded_image(upload: UploadedFile, safe_name: str) -> None:
    ensure_heif_registered()
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        upload.seek(0)
        with Image.open(upload, formats=_ALLOWED_PIL_FORMATS) as img:
            if img.format not in _ALLOWED_PIL_FORMATS:
                raise UnidentifiedImageError("Unsupported image format")
            ensure_safe_image_dimensions(img)
            img.verify()
    except Image.DecompressionBombError as exc:
        raise BadRequestProblemError(
            f"Изображение «{safe_name}» превышает допустимое разрешение",
            title="Слишком большое изображение",
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise BadRequestProblemError(
            f"Файл «{safe_name}» поврежден или не является корректным изображением",
            title="Некорректный файл изображения",
        ) from exc
    finally:
        upload.seek(0)


def _validate_single_file(upload: UploadedFile) -> tuple[UploadedFile, str, str]:
    safe_name = _sanitize_original_filename(upload.name)
    raw_leaf = Path((upload.name or "sheet").replace("\\", "/").strip()).name.strip()
    ext = Path(raw_leaf).suffix.lower()
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()

    ext_allowed = ext in _ALLOWED_EXTENSIONS
    mime_allowed = content_type in _ALLOWED_MIME_TYPES if content_type else True
    if not (ext_allowed and mime_allowed):
        raise BadRequestProblemError(
            f"Файл «{safe_name}» имеет недопустимый формат. Разрешены: JPEG, PNG, WEBP, HEIC, HEIF",
            title="Недопустимый формат файла",
        )
    if upload.size is None or upload.size <= 0:
        raise BadRequestProblemError(
            f"Файл «{safe_name}» пуст или имеет некорректный размер",
            title="Некорректный размер файла",
        )
    if upload.size > _MAX_FILE_SIZE:
        raise BadRequestProblemError(
            f"Файл «{safe_name}» превышает максимальный размер "
            f"{_MAX_FILE_SIZE // (1024 * 1024)} МБ",
            title="Превышен размер файла",
        )
    _verify_uploaded_image(upload, safe_name)
    return upload, safe_name, ext


def _validate_upload_files(
    files: list[UploadedFile],
) -> list[tuple[UploadedFile, str, str]]:
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
    return [_validate_single_file(upload) for upload in files]


def _next_file_index(batch: Batch) -> int:
    max_index = batch.items.aggregate(max=Max("file_index"))["max"]
    return (max_index if max_index is not None else -1) + 1


def _cleanup_saved_files(saved_files: list[tuple[Any, str]]) -> None:
    for storage, name in saved_files:
        try:
            if name and storage.exists(name):
                storage.delete(name)
        except OSError:
            logger.warning("Failed to remove rolled-back batch upload %s", name, exc_info=True)


def _create_batch_items(
    batch: Batch,
    user: User,
    validated_files: list[tuple[UploadedFile, str, str]],
    *,
    start_index: int = 0,
    saved_files: list[tuple[Any, str]] | None = None,
) -> None:
    tracked_files = saved_files if saved_files is not None else []
    for offset, (upload, safe_name, ext) in enumerate(validated_files):
        upload.seek(0)
        lot = Lot.objects.create(user=user)
        item = BatchItem.objects.create(
            batch=batch,
            lot=lot,
            file_index=start_index + offset,
            original_filename=safe_name,
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        storage_name = f"{uuid.uuid4().hex}{ext}"
        item.original_file.save(storage_name, upload, save=False)
        tracked_files.append((item.original_file.storage, item.original_file.name))
        item.save(update_fields=["original_file", "updated_at"])


def _schedule_batch_pipeline(batch_id: uuid.UUID) -> None:
    from apps.lots.tasks import process_batch_task

    transaction.on_commit(lambda: process_batch_task.delay(str(batch_id)))


@transaction.atomic
def enqueue_batch(user: User, files: list[UploadedFile]) -> Batch:
    """Validate uploaded sheets, persist a new queued batch, and schedule processing."""
    from apps.lots import pipeline as pipeline_pkg

    validated_files = _validate_upload_files(files)
    saved_files: list[tuple[Any, str]] = []
    try:
        batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
        _create_batch_items(
            batch,
            user,
            validated_files,
            start_index=0,
            saved_files=saved_files,
        )
        pipeline_pkg._schedule_batch_pipeline(batch.id)
    except BaseException:
        _cleanup_saved_files(saved_files)
        raise
    return batch


@transaction.atomic
def append_items_to_batch(
    user: User,
    batch_id: uuid.UUID,
    files: list[UploadedFile],
) -> Batch:
    """Append additional auction sheets to an active or partial-failed batch."""
    from apps.lots import pipeline as pipeline_pkg

    validated_files = _validate_upload_files(files)
    try:
        batch = Batch.objects.select_for_update().get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError("Пачка не найдена", title="Пачка не найдена") from exc
    if batch.status in _BATCH_TERMINAL_STATUSES:
        raise ConflictProblemError(
            "Пачка уже завершена. Откройте новую пачку через POST /api/v1/lots/batches",
            title="Пачка завершена",
        )
    if batch.items.count() + len(validated_files) > _MAX_FILES_PER_BATCH:
        raise BadRequestProblemError(
            f"В одной пачке может быть не более {_MAX_FILES_PER_BATCH} файлов",
            title="Превышен лимит файлов в пачке",
        )
    saved_files: list[tuple[Any, str]] = []
    try:
        _create_batch_items(
            batch,
            user,
            validated_files,
            start_index=_next_file_index(batch),
            saved_files=saved_files,
        )
        if batch.status == BatchStatus.PARTIAL_FAILED:
            batch.status = BatchStatus.QUEUED
            batch.save(update_fields=["status", "updated_at"])
            pipeline_pkg._schedule_batch_pipeline(batch.id)
    except BaseException:
        _cleanup_saved_files(saved_files)
        raise
    return batch


def load_user_batch(user: User, batch_id: uuid.UUID) -> Batch:
    """Fetch a user's batch or raise RFC 9457 NotFoundProblemError."""
    try:
        return Batch.objects.get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError("Пачка не найдена", title="Пачка не найдена") from exc
