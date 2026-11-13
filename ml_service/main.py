"""FastAPI application factory, DI wiring, CORS configuration, and lifespan hooks."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml_service.api.router import register_exception_handlers, router
from ml_service.config import Settings, get_settings
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient
from ml_service.infrastructure.image_cropper import PillowImageCropper
from ml_service.infrastructure.image_loader import AsyncImageLoader
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.infrastructure.result_cache import ResultCache
from ml_service.services.batch_parser_service import BatchParserService
from ml_service.services.sheet_parser_service import SheetParserService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI sheet-parser microservice."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        http_client = httpx.AsyncClient(
            timeout=resolved_settings.http_timeout_seconds,
            follow_redirects=False,
        )
        key_pool = GeminiKeyPool(
            api_keys=resolved_settings.gemini_api_keys,
            rpm_limit=resolved_settings.gemini_rpm_limit,
        )
        image_loader = AsyncImageLoader(
            http_client=http_client,
            max_bytes=resolved_settings.max_image_bytes,
        )
        cropper = PillowImageCropper(
            min_px=resolved_settings.crop_min_px,
            max_px=resolved_settings.crop_max_px,
            image_format=resolved_settings.crop_format,
            quality=resolved_settings.crop_quality,
        )
        vision_client = AsyncGeminiVisionClient(
            key_pool=key_pool,
            decision_model=resolved_settings.gemini_decision_model,
            flash_model=resolved_settings.gemini_flash_model,
            fallback_models=resolved_settings.gemini_fallback_models,
            enable_gatekeeper=resolved_settings.enable_gatekeeper,
            gatekeeper_fail_open=resolved_settings.gemini_gatekeeper_fail_open,
            request_timeout_ms=resolved_settings.gemini_request_timeout_ms,
            sdk_max_attempts=resolved_settings.gemini_sdk_max_attempts,
            model_cooldown_seconds=resolved_settings.gemini_model_cooldown_seconds,
            key_cooldown_seconds=resolved_settings.gemini_key_cooldown_seconds,
            thinking_level=resolved_settings.gemini_thinking_level,
            request_deadline_seconds=resolved_settings.gemini_request_deadline_seconds,
            hedge_delay_seconds=resolved_settings.gemini_hedge_delay_seconds,
            fast_header_timeout_seconds=resolved_settings.gemini_fast_header_timeout_seconds,
            gatekeeper_sheet_threshold=resolved_settings.gemini_gatekeeper_sheet_threshold,
            gatekeeper_readable_threshold=resolved_settings.gemini_gatekeeper_readable_threshold,
            client_error_cooldown_seconds=resolved_settings.gemini_client_error_cooldown_seconds,
            max_key_tries=resolved_settings.gemini_max_key_tries,
        )
        factory = SheetFactory(
            reference_year=resolved_settings.reference_year,
            reference_month=resolved_settings.reference_month,
            default_auction_strictness=resolved_settings.default_auction_strictness,
        )
        cache = ResultCache(cache_dir=resolved_settings.cache_dir)

        parser_service = SheetParserService(
            image_loader=image_loader,
            cropper=cropper,
            vision_client=vision_client,
            factory=factory,
            cache=cache,
        )
        batch_service = BatchParserService(
            parser_service=parser_service,
            max_items_per_batch=resolved_settings.batch_max_items,
            max_concurrency=resolved_settings.batch_max_concurrency,
            image_loader=image_loader,
            ttl_seconds=resolved_settings.batch_ttl_seconds,
            max_batches=resolved_settings.batch_max_stored_batches,
        )

        app_instance.state.settings = resolved_settings
        app_instance.state.key_pool = key_pool
        app_instance.state.parser_service = parser_service
        app_instance.state.batch_service = batch_service
        try:
            yield
        finally:
            await batch_service.shutdown()
            await http_client.aclose()

    app_instance = FastAPI(
        title="Auction Sheet Parser Microservice",
        version="0.1.0",
        description="Domain-driven FastAPI microservice for Japanese car auction sheet parsing.",
        lifespan=lifespan,
    )
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app_instance)
    app_instance.include_router(router)
    return app_instance


app = create_app()
