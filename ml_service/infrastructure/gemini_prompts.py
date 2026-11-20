"""Prompt assembly and Gemini ThinkingLevel/media-part builders."""

import base64

from google.genai import types

from ml_service.domains.entities import SlicedSheetEntity
from ml_service.domains.enums import LayoutComplexity
from ml_service.infrastructure.image_formats import detect_mime_from_magic_bytes

_THINKING_LEVELS: dict[str, types.ThinkingLevel] = {
    "MINIMAL": types.ThinkingLevel.MINIMAL,
    "LOW": types.ThinkingLevel.LOW,
    "MEDIUM": types.ThinkingLevel.MEDIUM,
    "HIGH": types.ThinkingLevel.HIGH,
}


def resolve_thinking_level(level_name: str) -> types.ThinkingLevel:
    """Resolve configured thinking level name to SDK ThinkingLevel enum."""
    return _THINKING_LEVELS.get(level_name.strip().upper(), types.ThinkingLevel.LOW)


def image_part(
    image_bytes: bytes,
    level: types.PartMediaResolutionLevel,
    mime_type: str = "image/png",
) -> types.Part:
    """Build an image Part with per-part Gemini 3 media resolution."""
    return types.Part(
        inline_data=types.Blob(data=image_bytes, mime_type=mime_type),
        media_resolution=types.PartMediaResolution(level=level),
    )


def build_gatekeeper_payload(
    decision_model: str, full_png: bytes, mime_type: str
) -> dict[str, object]:
    """Assemble Decisions API payload for gatekeeper classification."""
    b64_img = base64.b64encode(full_png).decode("ascii")
    return {
        "model": decision_model,
        "input": [
            {
                "type": "image",
                "data": b64_img,
                "mime_type": mime_type,
                "resolution": "low",
            }
        ],
        "questions": {
            "is_auction_sheet": {
                "type": "noul",
                "instructions": (
                    "Is this image a filled-in Japanese car auction inspection sheet "
                    "for a specific vehicle (with actual vehicle data filled in, NOT "
                    "a blank empty template, guide, or car photo)?"
                ),
            },
            "is_readable": {
                "type": "noul",
                "instructions": (
                    "Are the filled-in vehicle details (model, mileage, grade) "
                    "and body diagram present and clearly readable for extraction?"
                ),
            },
            "layout_complexity": {
                "type": "choice",
                "instructions": "Classify the sheet readability and layout complexity:",
                "criteria": {
                    "clean_digital": (
                        "Crisp digital printed sheet with no handwritten notes "
                        "or tiny circled ovals."
                    ),
                    "complex_or_handwritten": (
                        "Scan/fax, handwritten inspector/seller notes, "
                        "circled ovals, or dense diagram."
                    ),
                },
            },
        },
    }


def build_extraction_contents(
    sliced: SlicedSheetEntity,
    complexity: LayoutComplexity,
) -> list[str | types.Part]:
    """Assemble prompt text and per-part image payloads based on sheet complexity."""
    mime_type = sliced.mime_type or detect_mime_from_magic_bytes(sliced.full_png)
    if complexity == LayoutComplexity.CLEAN_DIGITAL:
        return [
            "Лист аукциона:",
            image_part(
                sliced.full_png, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type
            ),
            "Извлеки данные строго по JSON-схеме.",
        ]

    return [
        "Общий лист (для ориентации сторон и общей структуры):",
        image_part(sliced.full_png, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW, mime_type),
        "Фрагмент 1 (верх-лево):",
        image_part(
            sliced.crops_png["top_left"],
            types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
            mime_type,
        ),
        "Фрагмент 2 (верх-право — оценки, чек-лист опций, продавец):",
        image_part(
            sliced.crops_png["top_right"],
            types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
            mime_type,
        ),
        "Фрагмент 3 (низ-лево — заметки инспектора, шасси):",
        image_part(
            sliced.crops_png["bottom_left"],
            types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
            mime_type,
        ),
        "Фрагмент 4 (низ-право — схема дефектов, вертикальный текст):",
        image_part(
            sliced.crops_png["bottom_right"],
            types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
            mime_type,
        ),
        "Извлеки данные строго по JSON-схеме. Не дублируй метки с пересечений фрагментов.",
    ]
