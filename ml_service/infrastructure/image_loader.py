import asyncio
import hashlib
import ipaddress
import socket
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
import pillow_heif
from PIL import Image, UnidentifiedImageError

from app.domains.entities import LoadedImageEntity

pillow_heif.register_heif_opener()

_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "HEIF": "image/heic",
    "HEIC": "image/heic",
}

_BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", "0.0.0.0", "metadata.google.internal"})


def _ensure_safe_ip(ip_text: str) -> None:
    ip = ipaddress.ip_address(ip_text)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError(f"Blocked unsafe IP address in URL: {ip_text}")


def validate_url_not_ssrf(url: str) -> None:
    """Validate URL scheme and verify hostname does not target loopback/private/link-local networks."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Invalid image URL: '{url}'. Expected http or https URL.")

    host = parsed.hostname.strip().lower()
    if host in _BLOCKED_HOSTNAMES or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError(f"Blocked unsafe hostname in URL: '{host}'.")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            addr_infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return
        for info in addr_infos:
            _ensure_safe_ip(info[4][0])
    else:
        _ensure_safe_ip(host)


def _detect_and_verify_image_mime(data: bytes) -> str:
    """Verify image integrity via Pillow (+ HEIF opener) and return its canonical MIME type."""
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValueError("Invalid or corrupted image bytes.") from exc

    mime_type = _FORMAT_TO_MIME.get(fmt)
    if mime_type is None:
        raise ValueError(
            f"Unsupported image format '{fmt or 'unknown'}'. Allowed formats: JPEG, PNG, WEBP, HEIC, HEIF."
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
        """Download an image from a safe remote URL (including CDN redirects) and validate it."""
        validate_url_not_ssrf(url)
        parsed = urlparse(url)

        response = await self.http_client.get(url, follow_redirects=True)
        for hop in response.history:
            validate_url_not_ssrf(str(hop.url))
        validate_url_not_ssrf(str(response.url))
        response.raise_for_status()

        final_path = unquote(urlparse(str(response.url)).path) or unquote(parsed.path)
        filename = Path(final_path).name or "remote_sheet"
        return await self.load_from_bytes(response.content, filename)
