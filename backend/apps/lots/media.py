"""Lot scan and thumbnail rendering utilities (JPEG/HEIC conversion and starter SVGs)."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

import pillow_heif
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

if TYPE_CHECKING:
    from apps.lots.models import BatchItem, Lot

logger = logging.getLogger(__name__)

_SCAN_MAX_PX = 2400
_THUMB_MAX_PX = 480
_SCAN_JPEG_QUALITY = 88
_THUMB_JPEG_QUALITY = 82

_heif_registered = False


def ensure_heif_registered() -> None:
    """Register the HEIC/HEIF Pillow opener once per process."""
    global _heif_registered
    if not _heif_registered:
        pillow_heif.register_heif_opener()
        _heif_registered = True


def _to_rgb(image: Image.Image) -> Image.Image:
    """Normalize an image (including alpha/palette modes) into RGB on a white canvas."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _encode_jpeg(image: Image.Image, *, max_px: int, quality: int) -> bytes:
    resized = image.copy()
    resized.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    resized.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def render_browser_scan_and_thumbnail(source_bytes: bytes) -> tuple[bytes, bytes]:
    """Decode JPEG/PNG/WEBP/HEIC/HEIF bytes into browser-ready JPEG scan and thumbnail."""
    ensure_heif_registered()
    with Image.open(BytesIO(source_bytes)) as opened:
        transposed = ImageOps.exif_transpose(opened)
        rgb = _to_rgb(transposed)
        scan_bytes = _encode_jpeg(rgb, max_px=_SCAN_MAX_PX, quality=_SCAN_JPEG_QUALITY)
        thumb_bytes = _encode_jpeg(rgb, max_px=_THUMB_MAX_PX, quality=_THUMB_JPEG_QUALITY)
    return scan_bytes, thumb_bytes


def attach_uploaded_sheet_media_from_item(item: BatchItem) -> bool:
    """Generate and persist browser-ready scan and thumbnail from the uploaded batch item."""
    if item.lot is None or not item.original_file:
        return False
    try:
        with item.original_file.open("rb") as file_obj:
            source_bytes = file_obj.read()
        scan_bytes, thumb_bytes = render_browser_scan_and_thumbnail(source_bytes)
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("Could not render scan/thumbnail for item %s: %s", item.pk, exc)
        return False

    lot = item.lot
    lot.sheet_scan.save("sheet.jpg", ContentFile(scan_bytes), save=False)
    lot.sheet_thumbnail.save("thumb.jpg", ContentFile(thumb_bytes), save=False)
    lot.save(update_fields=["sheet_scan", "sheet_thumbnail", "updated_at"])
    return True


def render_starter_sheet_svg(lot: Lot) -> str:
    """Render a compact Japanese auction-sheet SVG preview for starter benchmark lots."""
    house = escape(lot.auction_house or "USS")
    lot_number = escape(lot.lot_number or "—")
    make_model = escape(f"{lot.make or ''} {lot.model or ''}".strip() or "Yuzu Lot")
    trim = escape(lot.trim or "")
    year = escape(str(lot.year) if lot.year else "—")
    frame_id = escape(lot.frame_id or lot.model_code or "—")
    engine_cc = escape(f"{lot.engine_cc} cc" if lot.engine_cc else "—")
    mileage = escape(f"{lot.mileage_km:,} km".replace(",", " ") if lot.mileage_km else "—")
    grade = escape(lot.overall_grade or "—")
    sub_grades = escape(f"{lot.exterior_grade or '-'} / {lot.interior_grade or '-'}")
    color_ru = escape(lot.color_ru or "—")
    defects = list(lot.defects.all()[:4])
    if defects:
        defect_lines = "".join(
            f'<text x="36" y="{336 + idx * 24}" font-size="13" fill="#2c2c2e">'
            f"{escape(d.raw_code)} · {escape(d.panel_ru)}</text>"
            for idx, d in enumerate(defects)
        )
    else:
        defect_lines = (
            '<text x="36" y="336" font-size="13" fill="#636366">'
            "Критических отметок по кузову нет</text>"
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 640 460" width="640" height="460">'
        '<rect width="640" height="460" fill="#faf8f3"/>'
        '<rect x="16" y="16" width="608" height="428" rx="8" '
        'fill="#ffffff" stroke="#1c1c1e" stroke-width="2"/>'
        '<rect x="16" y="16" width="608" height="58" rx="8" fill="#1c1c1e"/>'
        '<text x="32" y="42" font-size="18" font-weight="700" fill="#ffffff">'
        f"{house} · LOT #{lot_number}</text>"
        '<text x="32" y="62" font-size="12" fill="#d1d1d6">'
        "YUZU BENCHMARK AUCTION SHEET</text>"
        '<rect x="528" y="26" width="80" height="38" rx="6" fill="#ff9f0a"/>'
        '<text x="568" y="52" text-anchor="middle" '
        f'font-size="22" font-weight="700" fill="#1c1c1e">{grade}</text>'
        f'<text x="32" y="110" font-size="22" font-weight="700" fill="#1c1c1e">{make_model}</text>'
        f'<text x="32" y="132" font-size="13" fill="#636366">{trim}</text>'
        '<line x1="32" y1="148" x2="608" y2="148" stroke="#e5e5ea" stroke-width="1"/>'
        '<text x="32" y="176" font-size="13" fill="#636366">'
        f'FRAME ID: <tspan font-weight="600" fill="#1c1c1e">{frame_id}</tspan></text>'
        '<text x="340" y="176" font-size="13" fill="#636366">'
        f'ГОД: <tspan font-weight="600" fill="#1c1c1e">{year}</tspan></text>'
        '<text x="32" y="204" font-size="13" fill="#636366">'
        f'ОБЪЁМ: <tspan font-weight="600" fill="#1c1c1e">{engine_cc}</tspan></text>'
        '<text x="340" y="204" font-size="13" fill="#636366">'
        f'ПРОБЕГ: <tspan font-weight="600" fill="#1c1c1e">{mileage}</tspan></text>'
        '<text x="32" y="232" font-size="13" fill="#636366">'
        f'ЦВЕТ: <tspan font-weight="600" fill="#1c1c1e">{color_ru}</tspan></text>'
        '<text x="340" y="232" font-size="13" fill="#636366">'
        f'КУЗОВ/САЛОН: <tspan font-weight="600" fill="#1c1c1e">{sub_grades}</tspan></text>'
        '<rect x="32" y="256" width="576" height="164" rx="6" '
        'fill="#f5f5f7" stroke="#e5e5ea"/>'
        '<text x="36" y="284" font-size="12" font-weight="700" fill="#636366">'
        "ЗАМЕЧАНИЯ ПО КУЗОВУ (ДИАГРАММА)</text>"
        '<line x1="36" y1="296" x2="592" y2="296" stroke="#e5e5ea"/>'
        f"{defect_lines}"
        "</svg>"
    )


def attach_starter_sheet_media(lot: Lot) -> None:
    """Attach generated SVG scan and thumbnail files to a starter benchmark lot."""
    svg_bytes = render_starter_sheet_svg(lot).encode("utf-8")
    lot.sheet_scan.save("sheet.svg", ContentFile(svg_bytes), save=False)
    lot.sheet_thumbnail.save("thumb.svg", ContentFile(svg_bytes), save=False)
    lot.save(update_fields=["sheet_scan", "sheet_thumbnail", "updated_at"])
