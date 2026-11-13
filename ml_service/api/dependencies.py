"""FastAPI dependency providers reading service instances from app.state."""

from fastapi import Request

from app.config import Settings
from app.infrastructure.key_pool import GeminiKeyPool
from app.services.batch_parser_service import BatchParserService
from app.services.sheet_parser_service import SheetParserService


def get_settings_dep(request: Request) -> Settings:
    """Return active application settings stored during app startup."""
    return request.app.state.settings


def get_key_pool_dep(request: Request) -> GeminiKeyPool:
    """Return initialized Gemini API key pool stored during app startup."""
    return request.app.state.key_pool


def get_parser_service_dep(request: Request) -> SheetParserService:
    """Return initialized single-sheet parser service stored during app startup."""
    return request.app.state.parser_service


def get_batch_service_dep(request: Request) -> BatchParserService:
    """Return initialized batch parser service stored during app startup."""
    return request.app.state.batch_service
