"""Infrastructure adapters for image loading, slicing, caching, and Gemini Vision."""

from ml_service.infrastructure.gemini_schemas import (
    SYSTEM_PROMPT,
    AuctionExtractionSchema,
    DefectExtractionSchema,
    ExtractedRiskFlagsSchema,
    to_raw_extraction_entity,
)
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient
from ml_service.infrastructure.image_cropper import PillowImageCropper
from ml_service.infrastructure.image_loader import AsyncImageLoader
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.infrastructure.result_cache import (
    ResultCache,
    deserialize_parser_result,
    serialize_parser_result,
)

__all__ = [
    "SYSTEM_PROMPT",
    "AsyncGeminiVisionClient",
    "AsyncImageLoader",
    "AuctionExtractionSchema",
    "DefectExtractionSchema",
    "ExtractedRiskFlagsSchema",
    "GeminiKeyPool",
    "PillowImageCropper",
    "ResultCache",
    "deserialize_parser_result",
    "serialize_parser_result",
    "to_raw_extraction_entity",
]
