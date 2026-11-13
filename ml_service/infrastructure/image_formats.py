"""Shared image format MIME mappings, HEIF registration, and magic-byte detection."""

import pillow_heif

_heif_registered = False


def ensure_heif_registered() -> None:
    """Register pillow-heif opener once across the process."""
    global _heif_registered
    if not _heif_registered:
        pillow_heif.register_heif_opener()
        _heif_registered = True


IMAGE_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "HEIF": "image/heic",
    "HEIC": "image/heic",
}

CROP_FORMAT_TO_MIME: dict[str, str] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


def detect_mime_from_magic_bytes(data: bytes) -> str:
    """Detect common raster image MIME type from magic bytes with PNG fallback."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"hevc", b"mif1"}:
        return "image/heic"
    return "image/png"
