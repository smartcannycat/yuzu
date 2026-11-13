"""Infrastructure adapters for image loading, slicing, caching, and Gemini Vision."""

from app.infrastructure.gemini_schemas import (
    AuctionExtractionSchema,
    DefectExtractionSchema,
    ExtractedRiskFlagsSchema,
    SYSTEM_PROMPT,
    to_raw_extraction_entity,
)
from app.infrastructure.gemini_vision_client import AsyncGeminiVisionClient
from app.infrastructure.image_cropper import PillowImageCropper
from app.infrastructure.image_loader import AsyncImageLoader
from app.infrastructure.key_pool import GeminiKeyPool
from app.infrastructure.result_cache import (
    ResultCache,
    deserialize_parser_result,
    serialize_parser_result,
)

__all__ = [
    "AsyncGeminiVisionClient",
    "AsyncImageLoader",
    "AuctionExtractionSchema",
    "DefectExtractionSchema",
    "ExtractedRiskFlagsSchema",
    "GeminiKeyPool",
    "PillowImageCropper",
    "ResultCache",
    "SYSTEM_PROMPT",
    "deserialize_parser_result",
    "serialize_parser_result",
    "to_raw_extraction_entity",
]
