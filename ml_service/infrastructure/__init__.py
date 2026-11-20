"""Infrastructure adapters for image loading, slicing, caching, and Gemini Vision."""

from ml_service.infrastructure.gemini_runner import GeminiRunner
from ml_service.infrastructure.gemini_schemas import (
    EXTRACTION_CACHE_VERSION,
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
    build_sheet_cache_key,
    deserialize_parser_result,
    serialize_parser_result,
)

__all__ = [
    "EXTRACTION_CACHE_VERSION",
    "SYSTEM_PROMPT",
    "AsyncGeminiVisionClient",
    "AsyncImageLoader",
    "AuctionExtractionSchema",
    "DefectExtractionSchema",
    "ExtractedRiskFlagsSchema",
    "GeminiKeyPool",
    "GeminiRunner",
    "PillowImageCropper",
    "ResultCache",
    "build_sheet_cache_key",
    "deserialize_parser_result",
    "serialize_parser_result",
    "to_raw_extraction_entity",
]
