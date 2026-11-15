"""Shared fixtures and deterministic builders for offline ml_service tests."""

from io import BytesIO
from pathlib import Path

import pillow_heif
import pytest
from PIL import Image, ImageDraw

from ml_service.config import Settings
from ml_service.domains.entities import (
    RawDefectEntity,
    RawExtractionEntity,
    RawRiskFlagsEntity,
    SlicedSheetEntity,
)
from ml_service.domains.enums import BodyPanel, DriveType, FuelType, OdometerStatus

pillow_heif.register_heif_opener()


def make_image_bytes(
    *,
    fmt: str = "PNG",
    size: tuple[int, int] = (200, 140),
    color: tuple[int, int, int] = (255, 255, 255),
    draw_box: bool = True,
) -> bytes:
    """Create valid in-memory image bytes in PNG, JPEG, WEBP, or HEIF format."""
    img = Image.new("RGB", size, color=color)
    if draw_box:
        draw = ImageDraw.Draw(img)
        w, h = size
        draw.rectangle(
            (int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.85)),
            outline=(20, 20, 20),
            width=3,
        )
    buf = BytesIO()
    save_fmt = "HEIF" if fmt.upper() in {"HEIC", "HEIF"} else fmt.upper()
    img.save(buf, format=save_fmt)
    return buf.getvalue()


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    """Create isolated Settings ignoring local .env files."""
    defaults: dict[str, object] = {
        "ml_service_api_key_single": "test-service-key",
        "gemini_api_keys_raw": "gemini-key-1,gemini-key-2",
        "cache_dir": tmp_path / "cache",
        "rate_limit_requests_per_minute": 120,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def make_raw_extraction(**overrides: object) -> RawExtractionEntity:
    """Create a realistic RawExtractionEntity for factory/service tests."""
    defaults: dict[str, object] = {
        "auction_house_raw": "TAA",
        "lot_number_raw": "3142",
        "make_raw": "トヨタ",
        "model_raw": "カローラツーリング",
        "trim_raw": "W×B",
        "model_code_raw": "6AA-ZWE211W",
        "chassis_number_raw": "6012345",
        "first_reg_raw": "R4.05",
        "mileage_raw": "45,000 km",
        "engine_cc_raw": "1800",
        "transmission_raw": "CVT",
        "drive_type_raw": "2WD",
        "color_raw": "パール (070)",
        "paint_code_raw": "070",
        "shaken_raw": "R8.05",
        "recycling_fee_raw": "11,200",
        "overall_grade": "4.5",
        "exterior_grade": "B",
        "interior_grade": "B",
        "inspector_notes_raw": ["純正ナビ", "小キズ"],
        "seller_comments_raw": ["ワンオーナー"],
        "auction_house": "TAA",
        "make_en": "Toyota",
        "model_en": "Corolla Touring",
        "trim_en": "W×B",
        "mileage_km": 45000,
        "odometer_status": OdometerStatus.CONFIRMED,
        "engine_cc": 1800,
        "transmission_ru": "вариатор",
        "drive_type": DriveType.TWO_WD,
        "fuel_type": FuelType.HYBRID,
        "color_ru": "Белый перламутр (070)",
        "shaken_ru": "05.2026",
        "recycling_fee_yen": 11200,
        "recycling_fee_paid": True,
        "equipment_ru": ["AAC", "PS", "PW"],
        "defects": [
            RawDefectEntity(
                visual_location="передний бампер слева",
                panel_id=BodyPanel.FRONT_BUMPER,
                panel_ru="Передний бампер",
                raw_code="A1",
            )
        ],
        "risk_flags": RawRiskFlagsEntity(),
        "inspector_notes_ru": ["Штатная навигация", "Мелкие царапины"],
        "seller_comments_ru": ["Один владелец"],
        "extra_ru": [],
        "unreadable_fields": [],
        "auction_branch": "Yokohama",
        "right_hand_drive": True,
        "name_change_deadline": None,
        "ocr_warnings": [],
        "model_used": "gemini-3.6-flash",
        "extract_ms": 120,
    }
    defaults.update(overrides)
    return RawExtractionEntity(**defaults)


def make_sliced_sheet() -> SlicedSheetEntity:
    """Create minimal SlicedSheetEntity with valid JPEG bytes."""
    img_bytes = make_image_bytes(fmt="JPEG", size=(100, 80))
    return SlicedSheetEntity(
        full_png=img_bytes,
        crops_png={
            "top_left": img_bytes,
            "top_right": img_bytes,
            "bottom_left": img_bytes,
            "bottom_right": img_bytes,
        },
        width=100,
        height=80,
        mime_type="image/jpeg",
    )


@pytest.fixture
def sample_png_bytes() -> bytes:
    return make_image_bytes(fmt="PNG")


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    return make_image_bytes(fmt="JPEG")
