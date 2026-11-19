"""Safe image loading, Pillow MIME/dimension verification, and SSRF-hardened URL fetching."""

import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from urllib.parse import ParseResult, unquote, urljoin, urlparse, urlunparse

import httpx
from PIL import Image, UnidentifiedImageError

from ml_service.domains.entities import LoadedImageEntity
from ml_service.infrastructure.image_formats import (
    IMAGE_FORMAT_TO_MIME,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    ensure_heif_registered,
    validate_image_dimensions,
)

ensure_heif_registered()
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

_BLOCKED_HOSTNAMES = frozenset(
    {"localhost", "localhost.localdomain", "0.0.0.0", "metadata.google.internal"}
)
_MAX_URL_REDIRECTS = 5


def _ensure_safe_ip(ip_text: str) -> None:
    clean_ip = ip_text.split("%", 1)[0]
    ip = ipaddress.ip_address(clean_ip)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        _ensure_safe_ip(str(mapped))
    if (
        not ip.is_global
        or (isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local)
        or ip.is_private
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


def _parse_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    candidate = host.rstrip(".").strip("[]")
    if not candidate:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(candidate))
    except OSError:
        return None


def _validate_parsed_url(url: str) -> tuple[ParseResult, str, int | None]:
    if not url or any(ch in url for ch in ("\t", "\r", "\n")):
        raise ValueError("Invalid image URL: control characters are disallowed.")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError(f"Invalid image URL: '{url}'.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Invalid image URL: '{url}'. Expected http or https URL.")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise ValueError("Credentials in image URL are disallowed.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Malformed port in image URL: '{url}'.") from exc
    if port is not None and not (1 <= port <= 65535):
        raise ValueError(f"Invalid port in image URL: {port}.")
    host = parsed.hostname.strip().lower().rstrip(".")
    if (
        not host
        or host in _BLOCKED_HOSTNAMES
        or host.endswith((".local", ".localhost", ".internal"))
    ):
        raise ValueError(f"Blocked unsafe hostname in URL: '{host}'.")
    return parsed, host, port


async def validate_url_not_ssrf(
    url: str,
    *,
    dns_resolver: Callable[[str], list[str]] | None = None,
) -> list[str]:
    """Validate URL scheme/credentials and asynchronously verify resolved IPs are public."""
    _, host, _ = _validate_parsed_url(url)
    ip_literal = _parse_ip_literal(host)
    if ip_literal is not None:
        _ensure_safe_ip(str(ip_literal))
        return [str(ip_literal)]

    resolver = dns_resolver or _resolve_host_ips
    try:
        resolved_ips = await asyncio.to_thread(resolver, host)
    except OSError as exc:
        raise ValueError(f"Failed to resolve remote host '{host}': {exc}") from exc
    if not resolved_ips:
        raise ValueError(f"No IP addresses resolved for remote host '{host}'.")
    for ip_text in resolved_ips:
        _ensure_safe_ip(ip_text)
    return list(resolved_ips)


def _build_pinned_request_target(
    url: str, pinned_ip: str
) -> tuple[str, dict[str, str], dict[str, object]]:
    parsed, orig_host, port = _validate_parsed_url(url)
    clean_ip = pinned_ip.split("%", 1)[0]
    pinned_netloc_host = f"[{clean_ip}]" if ":" in clean_ip else clean_ip
    new_netloc = f"{pinned_netloc_host}:{port}" if port is not None else pinned_netloc_host
    pinned_url = urlunparse(parsed._replace(netloc=new_netloc))

    host_only = f"[{orig_host}]" if ":" in orig_host else orig_host
    host_header = f"{host_only}:{port}" if port is not None else host_only
    headers = {"Host": host_header}
    extensions: dict[str, object] = {}
    if parsed.scheme == "https" and _parse_ip_literal(orig_host) is None:
        extensions["sni_hostname"] = orig_host
    return pinned_url, headers, extensions


def verify_image_mime(
    data: bytes,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
    max_dimension: int = MAX_IMAGE_DIMENSION,
) -> str:
    """Verify image integrity and dimensions via Pillow (+ HEIF) and return its MIME type."""
    try:
        with Image.open(BytesIO(data)) as img:
            validate_image_dimensions(img, max_pixels=max_pixels, max_dimension=max_dimension)
            fmt = (img.format or "").upper()
            img.verify()
    except Image.DecompressionBombError as exc:
        raise ValueError("Image exceeds maximum allowed pixel count.") from exc
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("Invalid or corrupted image bytes.") from exc

    mime_type = IMAGE_FORMAT_TO_MIME.get(fmt)
    if mime_type is None:
        raise ValueError(
            f"Unsupported image format '{fmt or 'unknown'}'. "
            "Allowed formats: JPEG, PNG, WEBP, HEIC, HEIF."
        )
    return mime_type


_detect_and_verify_image_mime = verify_image_mime


class AsyncImageLoader:
    """Loads, validates, and fingerprints auction sheet images from bytes or URLs."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        max_bytes: int = 15 * 1024 * 1024,
        dns_resolver: Callable[[str], list[str]] | None = None,
        total_timeout_seconds: float = 20.0,
    ) -> None:
        self.http_client = http_client or httpx.AsyncClient(
            timeout=total_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        self.max_bytes = max_bytes
        self._dns_resolver = dns_resolver
        self._total_timeout_seconds = total_timeout_seconds

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

    async def _read_response_bytes(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if (
            content_length is not None
            and content_length.strip().isdigit()
            and int(content_length.strip()) > self.max_bytes
        ):
            raise ValueError(
                f"Remote image size ({content_length.strip()} bytes) "
                f"exceeds maximum allowed ({self.max_bytes} bytes)."
            )

        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > self.max_bytes:
                raise ValueError(
                    f"Remote image stream exceeded maximum allowed size ({self.max_bytes} bytes)."
                )
            chunks.extend(chunk)
        return bytes(chunks)

    async def load_from_url(self, url: str) -> LoadedImageEntity:
        """Stream an image from a verified remote URL with IP pinning, SSRF, and timeout checks."""
        async with asyncio.timeout(self._total_timeout_seconds):
            current_url = url
            for _ in range(_MAX_URL_REDIRECTS + 1):
                resolved_ips = await validate_url_not_ssrf(
                    current_url, dns_resolver=self._dns_resolver
                )
                pinned_url, headers, extensions = _build_pinned_request_target(
                    current_url, resolved_ips[0]
                )

                async with self.http_client.stream(
                    "GET",
                    pinned_url,
                    headers=headers,
                    extensions=extensions,
                    follow_redirects=False,
                ) as response:
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
                    payload = await self._read_response_bytes(response)
                    final_path = unquote(urlparse(str(response.url)).path) or unquote(
                        urlparse(current_url).path
                    )
                    filename = Path(final_path).name or "remote_sheet"
                    return await self.load_from_bytes(payload, filename)

            raise ValueError(f"Too many redirects (>{_MAX_URL_REDIRECTS}) while downloading image.")
