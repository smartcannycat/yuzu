"""Authenticated lot media streaming endpoint query helper."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from django.http import FileResponse

from apps.core.exceptions import NotFoundProblemError
from apps.lots.models import Lot

if TYPE_CHECKING:
    import uuid

    from apps.users.models import User

_EXT_CONTENT_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def _guess_image_content_type(filename: str) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    ext = suffix.lstrip(".") or "bin"
    mapped = _EXT_CONTENT_TYPES.get(suffix)
    if mapped is not None:
        return mapped, ext
    guessed, _encoding = mimetypes.guess_type(filename)
    if guessed and guessed.startswith("image/"):
        return guessed, ext
    return "application/octet-stream", ext


def get_lot_media_response(
    user: User,
    lot_id: uuid.UUID,
    kind: Literal["scan", "thumbnail"],
) -> FileResponse:
    """Stream an owned, completed lot's scan or thumbnail with strict security headers."""
    field_name = "sheet_scan" if kind == "scan" else "sheet_thumbnail"
    lot = (
        Lot.objects.filter(
            id=lot_id,
            user=user,
            completed_at__isnull=False,
            deleted_at__isnull=True,
        )
        .only("id", field_name)
        .first()
    )
    if lot is None:
        raise NotFoundProblemError("Лот не найден", title="Лот не найден")

    field_file = getattr(lot, field_name, None)
    if not field_file or not getattr(field_file, "name", ""):
        raise NotFoundProblemError(
            "Изображение аукционного листа не найдено",
            title="Медиафайл не найден",
        )

    try:
        file_handle = field_file.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise NotFoundProblemError(
            "Изображение аукционного листа не найдено",
            title="Медиафайл не найден",
        ) from exc

    content_type, ext = _guess_image_content_type(field_file.name)
    response = FileResponse(file_handle, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response["Content-Disposition"] = f'inline; filename="lot-{kind}.{ext}"'
    return response
