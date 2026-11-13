import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from app.domains.entities import LoadedImageEntity

_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _detect_and_verify_image_mime(data: bytes) -> str:
    """Verify image integrity via Pillow and return its canonical MIME type."""
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValueError("Invalid or corrupted image bytes.") from exc

    mime_type = _FORMAT_TO_MIME.get(fmt)
    if mime_type is None:
        raise ValueError(
            f"Unsupported image format '{fmt or 'unknown'}'. Allowed formats: JPEG, PNG, WEBP."
        )
    return mime_type


class AsyncImageLoader:
    """Loads, validates, and fingerprints auction sheet images from bytes or URLs."""

    def __init__(self, http_client: httpx.AsyncClient, max_bytes: int = 15 * 1024 * 1024) -> None:
        self.http_client = http_client
        self.max_bytes = max_bytes

    async def load_from_bytes(self, data: bytes, filename: str) -> LoadedImageEntity:
        """Validate raw image bytes, verify format in a worker thread, and compute SHA-256."""
        if not data:
            raise ValueError("Image payload is empty.")
        if len(data) > self.max_bytes:
            raise ValueError(
                f"Image size ({len(data)} bytes) exceeds maximum allowed ({self.max_bytes} bytes)."
            )

        mime_type = await asyncio.to_thread(_detect_and_verify_image_mime, data)
        sha256 = hashlib.sha256(data).hexdigest()
        clean_name = filename.strip() if filename and filename.strip() else "sheet_image"

        return LoadedImageEntity(
            data=data,
            mime_type=mime_type,
            sha256=sha256,
            original_filename=clean_name,
        )

    async def load_from_url(self, url: str) -> LoadedImageEntity:
        """Download an image from a remote URL (including CDN redirects) and validate it."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid image URL: '{url}'. Expected http or https URL.")

        response = await self.http_client.get(url, follow_redirects=True)
        response.raise_for_status()

        final_path = unquote(urlparse(str(response.url)).path) or unquote(parsed.path)
        filename = Path(final_path).name or "remote_sheet"
        return await self.load_from_bytes(response.content, filename)
