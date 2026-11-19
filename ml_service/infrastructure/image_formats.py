"""Shared image MIME mappings, dimension limits, HEIF registration, and magic-byte detection."""

import pillow_heif
from PIL import Image

MAX_IMAGE_PIXELS = 50_000_000
MAX_IMAGE_DIMENSION = 12_000
CHASSIS_MAX_IMAGE_PIXELS = 25_000_000
CHASSIS_MAX_IMAGE_DIMENSION = 8_000

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

_heif_registered = False


def ensure_heif_registered() -> None:
    """Register pillow-heif opener once across the process."""
    global _heif_registered
    if not _heif_registered:
        pillow_heif.register_heif_opener()
        _heif_registered = True


def validate_image_dimensions(
    img: Image.Image,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
    max_dimension: int = MAX_IMAGE_DIMENSION,
) -> None:
    """Validate image width, height, and total pixel count immediately after opening."""
    width, height = img.size
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions.")
    if width > max_dimension or height > max_dimension:
        raise ValueError(
            f"Image dimensions ({width}x{height}) exceed maximum side length ({max_dimension}px)."
        )
    if width * height > max_pixels:
        raise ValueError(
            f"Image pixel count ({width * height}) exceeds maximum allowed ({max_pixels})."
        )


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
    if (
        len(data) >= 12
        and data[4:8] == b"ftyp"
        and data[8:12] in {b"heic", b"heix", b"hevc", b"mif1"}
    ):
        return "image/heic"
    return "image/png"
