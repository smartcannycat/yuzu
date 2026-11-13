import asyncio
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from ml_service.domains.entities import SlicedSheetEntity
from ml_service.infrastructure.image_formats import CROP_FORMAT_TO_MIME, ensure_heif_registered

ensure_heif_registered()


def trim_uniform_margins(
    img: Image.Image, bg_threshold: int = 245, pad_ratio: float = 0.02
) -> Image.Image:
    """Softly trim bright uniform scan margins while keeping a safety padding."""
    gray = img.convert("L")
    mask = gray.point(lambda p: 255 if p < bg_threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img

    w, h = img.size
    pad_x, pad_y = int(w * pad_ratio), int(h * pad_ratio)
    left = max(0, bbox[0] - pad_x)
    top = max(0, bbox[1] - pad_y)
    right = min(w, bbox[2] + pad_x)
    bottom = min(h, bbox[3] + pad_y)

    if (right - left) < w * 0.96 or (bottom - top) < h * 0.96:
        return img.crop((left, top, right, bottom))
    return img


def normalize_size(img: Image.Image, min_px: int = 1200, max_px: int = 1800) -> Image.Image:
    """Upscale small crops to min_px and downscale oversized images to max_px."""
    w, h = img.size
    longest = max(w, h)
    if longest == 0:
        return img
    if longest < min_px or longest > max_px:
        target = min_px if longest < min_px else max_px
        scale = target / longest
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        return img.resize(new_size, Image.Resampling.LANCZOS)
    return img


def _encode_rgb_image(img: Image.Image, image_format: str = "PNG", quality: int = 88) -> bytes:
    """Encode an RGB Pillow image into PNG, JPEG, or WEBP bytes in memory."""
    buf = BytesIO()
    if image_format == "PNG":
        img.save(buf, format="PNG", compress_level=1)
    elif image_format == "JPEG":
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    elif image_format == "WEBP":
        img.save(buf, format="WEBP", quality=quality, method=4)
    else:
        raise ValueError(f"Unsupported crop image format: {image_format}")
    return buf.getvalue()


def _encode_rgb_png(img: Image.Image) -> bytes:
    """Encode an RGB Pillow image into lossless PNG bytes in memory with fast compression."""
    return _encode_rgb_image(img, image_format="PNG")


class PillowImageCropper:
    """Preprocesses auction sheet images into normalized full image and 4 overlapping crops."""

    def __init__(
        self,
        min_px: int = 1200,
        max_px: int = 1800,
        image_format: str = "PNG",
        quality: int = 88,
    ) -> None:
        normalized_fmt = image_format.strip().upper()
        if normalized_fmt == "JPG":
            normalized_fmt = "JPEG"
        if normalized_fmt not in CROP_FORMAT_TO_MIME:
            raise ValueError(f"Unsupported crop image format: {image_format}")
        self.min_px = min_px
        self.max_px = max_px
        self.image_format = normalized_fmt
        self.quality = quality
        self.mime_type = CROP_FORMAT_TO_MIME[normalized_fmt]

    async def slice_image_bytes(self, data: bytes, overlap: float = 0.20) -> SlicedSheetEntity:
        """Prepare normalized full sheet and 4 overlapping 60%x60% quadrants."""
        if not data:
            raise ValueError("Cannot slice empty image bytes.")
        return await asyncio.to_thread(self._slice_sync, data, overlap)

    def _slice_sync(self, data: bytes, overlap: float) -> SlicedSheetEntity:
        try:
            with Image.open(BytesIO(data)) as raw_img:
                img = ImageOps.exif_transpose(raw_img).convert("RGB")
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ValueError("Unable to decode image for slicing.") from exc

        img = trim_uniform_margins(img)
        w, h = img.size

        ratio = min(0.75, max(0.50, 0.5 + overlap / 2))
        cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))

        boxes = {
            "top_left": (0, 0, cw, ch),
            "top_right": (w - cw, 0, w, ch),
            "bottom_left": (0, h - ch, cw, h),
            "bottom_right": (w - cw, h - ch, w, h),
        }

        full_normalized = normalize_size(img, min_px=self.min_px, max_px=self.max_px)
        full_encoded = _encode_rgb_image(
            full_normalized, image_format=self.image_format, quality=self.quality
        )

        crops_encoded: dict[str, bytes] = {}
        for name, box in boxes.items():
            crop_normalized = normalize_size(img.crop(box), min_px=self.min_px, max_px=self.max_px)
            crops_encoded[name] = _encode_rgb_image(
                crop_normalized, image_format=self.image_format, quality=self.quality
            )

        return SlicedSheetEntity(
            full_png=full_encoded,
            crops_png=crops_encoded,
            width=full_normalized.width,
            height=full_normalized.height,
            mime_type=self.mime_type,
        )
