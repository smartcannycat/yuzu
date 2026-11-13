import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from ml_service.domains.entities import LoadedImageEntity
from ml_service.infrastructure.image_formats import IMAGE_FORMAT_TO_MIME, ensure_heif_registered

ensure_heif_registered()

_BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", "0.0.0.0", "metadata.google.internal"})
_MAX_URL_REDIRECTS = 5


def _ensure_safe_ip(ip_text: str) -> None:
    clean_ip = ip_text.split("%", 1)[0]
    ip = ipaddress.ip_address(clean_ip)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError(f"Blocked unsafe IP address in URL: {ip_text}")


def _resolve_host_ips(host: str) -> list[str]:
    """Resolve hostname to IP strings, failing closed on DNS errors."""
    try:
        addr_infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Failed to resolve remote host '{host}': {exc}") from exc
    ips = [str(info[4][0]) for info in addr_infos if info[4]]
    if not ips:
        raise ValueError(f"No IP addresses resolved for remote host '{host}'.")
    return ips


async def validate_url_not_ssrf(
    url: str,
    *,
    dns_resolver: Callable[[str], list[str]] | None = None,
) -> None:
    """Validate URL scheme and asynchronously verify host IPs do not target internal networks."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Invalid image URL: '{url}'. Expected http or https URL.")

    host = parsed.hostname.strip().lower()
    if host in _BLOCKED_HOSTNAMES or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError(f"Blocked unsafe hostname in URL: '{host}'.")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        resolver = dns_resolver or _resolve_host_ips
        try:
            resolved_ips = await asyncio.to_thread(resolver, host)
        except OSError as exc:
            raise ValueError(f"Failed to resolve remote host '{host}': {exc}") from exc
        if not resolved_ips:
            raise ValueError(f"No IP addresses resolved for remote host '{host}'.")
        for ip_text in resolved_ips:
            _ensure_safe_ip(ip_text)
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

    mime_type = IMAGE_FORMAT_TO_MIME.get(fmt)
    if mime_type is None:
        raise ValueError(
            f"Unsupported image format '{fmt or 'unknown'}'. Allowed formats: JPEG, PNG, WEBP, HEIC, HEIF."
        )
    return mime_type


class AsyncImageLoader:
    """Loads, validates, and fingerprints auction sheet images from bytes or URLs."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        max_bytes: int = 15 * 1024 * 1024,
        dns_resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.http_client = http_client
        self.max_bytes = max_bytes
        self._dns_resolver = dns_resolver

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
        """Stream an image from a verified remote URL with per-hop SSRF and byte-cap checks."""
        current_url = url
        for _ in range(_MAX_URL_REDIRECTS + 1):
            await validate_url_not_ssrf(current_url, dns_resolver=self._dns_resolver)

            async with self.http_client.stream("GET", current_url, follow_redirects=False) as response:
                network_stream = response.extensions.get("network_stream")
                if network_stream is not None:
                    server_addr = network_stream.get_extra_info("server_addr")
                    if isinstance(server_addr, tuple) and server_addr:
                        _ensure_safe_ip(str(server_addr[0]))

                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect response is missing Location header.")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if (
                    content_length is not None
                    and content_length.strip().isdigit()
                    and int(content_length.strip()) > self.max_bytes
                ):
                    raise ValueError(
                        f"Remote image size ({content_length.strip()} bytes) exceeds maximum allowed ({self.max_bytes} bytes)."
                    )

                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(chunks) + len(chunk) > self.max_bytes:
                        raise ValueError(
                            f"Remote image stream exceeded maximum allowed size ({self.max_bytes} bytes)."
                        )
                    chunks.extend(chunk)

                final_path = unquote(urlparse(str(response.url)).path) or unquote(urlparse(current_url).path)
                filename = Path(final_path).name or "remote_sheet"
                return await self.load_from_bytes(bytes(chunks), filename)

        raise ValueError(f"Too many redirects (>{_MAX_URL_REDIRECTS}) while downloading image.")
