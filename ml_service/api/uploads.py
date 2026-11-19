"""Shared multipart upload validation, bounded reading, and batch spill staging helpers."""

from fastapi import HTTPException, UploadFile, status

from ml_service.services.batch_parser_service import BatchParserService, StagedBatchItem

_UPLOAD_CHUNK_SIZE = 1024 * 1024

ALLOWED_SHEET_UPLOAD_MIMES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "application/octet-stream",
        "",
    }
)
ALLOWED_CHASSIS_UPLOAD_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})


def validate_upload_content_type(
    upload: UploadFile,
    *,
    allowed_mimes: frozenset[str] = ALLOWED_SHEET_UPLOAD_MIMES,
    allowed_description: str = "image/jpeg, image/png, image/webp, image/heic, image/heif",
) -> None:
    """Reject uploads whose declared MIME type is outside the allowed set."""
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported Content-Type '{mime}' for '{upload.filename or 'upload'}'. "
                f"Allowed MIME types: {allowed_description}."
            ),
        )


async def read_upload_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file in bounded chunks so oversized payloads fail before buffering."""
    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image size ({declared_size} bytes) exceeds maximum allowed ({max_bytes} bytes)."
            ),
        )

    chunks = bytearray()
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        if len(chunks) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image size exceeds maximum allowed ({max_bytes} bytes).",
            )
        chunks.extend(chunk)
    return bytes(chunks)


def declared_sizes_sum(files: list[UploadFile], max_image_bytes: int) -> int:
    """Validate declared upload sizes and sum known byte sizes before reading payloads."""
    total = 0
    for upload in files:
        declared = getattr(upload, "size", None)
        if declared is not None:
            if declared > max_image_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Image size ({declared} bytes) exceeds maximum allowed "
                        f"({max_image_bytes} bytes)."
                    ),
                )
            total += declared
    return total


async def stage_batch_uploads(
    files: list[UploadFile],
    *,
    max_image_bytes: int,
    batch_service: BatchParserService,
) -> tuple[list[StagedBatchItem] | list[tuple[bytes, str]], list[StagedBatchItem]]:
    """Read and spill uploads one-by-one so multi-file batches never buffer together in RAM."""
    if not hasattr(batch_service, "stage_upload"):
        raw_items = [
            (
                await read_upload_bounded(upload, max_image_bytes),
                upload.filename or f"sheet_{index}.png",
            )
            for index, upload in enumerate(files)
        ]
        return raw_items, []

    staged_items: list[StagedBatchItem] = []
    pending_bytes = 0
    try:
        for index, upload in enumerate(files):
            payload = await read_upload_bounded(upload, max_image_bytes)
            filename = upload.filename or f"sheet_{index}.png"
            staged = await batch_service.stage_upload(
                payload, filename, pending_bytes=pending_bytes
            )
            staged_items.append(staged)
            pending_bytes += staged.size
    except BaseException:
        await batch_service.discard_staged(staged_items)
        raise
    return staged_items, staged_items
