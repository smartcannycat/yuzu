"""Application service for parsing single Japanese car auction sheets."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Protocol

import httpx

from ml_service.domains.entities import (
    FastHeaderPreviewEntity,
    GatekeeperDecisionEntity,
    LoadedImageEntity,
    ParserResultEntity,
    RawExtractionEntity,
    SlicedSheetEntity,
)
from ml_service.domains.enums import LayoutComplexity, TaskStep
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.gemini_schemas import EXTRACTION_CACHE_VERSION
from ml_service.infrastructure.result_cache import build_sheet_cache_key

StepCallback = Callable[[TaskStep, int], Awaitable[None]]
PreviewCallback = Callable[[str], Awaitable[None]]


class VisionUpstreamError(RuntimeError):
    """Raised when the upstream Gemini Vision API fails over HTTP transport."""


class ImageLoaderProtocol(Protocol):
    async def load_from_bytes(
        self, data: bytes, filename: str = "upload.png"
    ) -> LoadedImageEntity: ...

    async def load_from_url(self, url: str) -> LoadedImageEntity: ...


class CropperProtocol(Protocol):
    async def slice_image_bytes(self, data: bytes, overlap: float = 0.20) -> SlicedSheetEntity: ...


class VisionClientProtocol(Protocol):
    @property
    def flash_model_name(self) -> str: ...

    async def check_sheet(self, full_png: bytes) -> GatekeeperDecisionEntity: ...

    async def extract_fast_header(
        self, sliced: SlicedSheetEntity
    ) -> FastHeaderPreviewEntity | None: ...

    async def extract_sheet(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
    ) -> RawExtractionEntity: ...


class ResultCacheProtocol(Protocol):
    async def get(self, cache_key: str, filename: str = "") -> ParserResultEntity | None: ...

    async def set(self, cache_key: str, result: ParserResultEntity) -> None: ...


async def _notify_step(on_step: StepCallback | None, step: TaskStep, progress_pct: int) -> None:
    if on_step is not None:
        await on_step(step, progress_pct)


class SheetParserService:
    """Orchestrates image loading, caching, slicing, Vision extraction, and domain normalization."""

    def __init__(
        self,
        image_loader: ImageLoaderProtocol,
        cropper: CropperProtocol,
        vision_client: VisionClientProtocol,
        factory: SheetFactory,
        cache: ResultCacheProtocol,
        *,
        schema_version: str = EXTRACTION_CACHE_VERSION,
        enable_fast_header: bool = True,
    ) -> None:
        self._image_loader = image_loader
        self._cropper = cropper
        self._vision_client = vision_client
        self._factory = factory
        self._cache = cache
        self._schema_version = schema_version
        self._enable_fast_header = enable_fast_header

    async def parse_bytes(
        self,
        data: bytes,
        filename: str = "upload.png",
        *,
        force_refresh: bool = False,
        on_step: StepCallback | None = None,
        on_preview: PreviewCallback | None = None,
    ) -> ParserResultEntity:
        """Parse an uploaded auction sheet byte payload into a normalized ParserResultEntity."""
        started_at = time.perf_counter()
        await _notify_step(on_step, TaskStep.GATEKEEPER, 15)
        loaded = await self._image_loader.load_from_bytes(data, filename=filename)
        return await self._parse_loaded(
            loaded,
            force_refresh=force_refresh,
            on_step=on_step,
            on_preview=on_preview,
            started_at=started_at,
        )

    async def parse_url(
        self,
        url: str,
        *,
        force_refresh: bool = False,
        on_step: StepCallback | None = None,
        on_preview: PreviewCallback | None = None,
    ) -> ParserResultEntity:
        """Download an auction sheet image from URL and parse it."""
        started_at = time.perf_counter()
        await _notify_step(on_step, TaskStep.GATEKEEPER, 15)
        try:
            loaded = await self._image_loader.load_from_url(url)
        except TimeoutError as exc:
            raise httpx.ReadTimeout("Remote image download timed out.") from exc
        return await self._parse_loaded(
            loaded,
            force_refresh=force_refresh,
            on_step=on_step,
            on_preview=on_preview,
            started_at=started_at,
        )

    async def _run_extraction(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
        *,
        on_step: StepCallback | None,
        on_preview: PreviewCallback | None,
    ) -> tuple[RawExtractionEntity, FastHeaderPreviewEntity | None]:
        header_preview: FastHeaderPreviewEntity | None = None
        run_preview = self._enable_fast_header and on_preview is not None
        header_task: asyncio.Task[FastHeaderPreviewEntity | None] | None = None

        if run_preview:
            assert on_preview is not None

            async def _run_fast_header() -> FastHeaderPreviewEntity | None:
                preview = await self._vision_client.extract_fast_header(sliced)
                if preview is not None and preview.preview_title:
                    await on_preview(preview.preview_title)
                return preview

            await _notify_step(on_step, TaskStep.FAST_HEADER_OCR, 45)
            header_task = asyncio.create_task(_run_fast_header())

        await _notify_step(on_step, TaskStep.GEMINI_OCR, 65)
        try:
            extracted = await self._vision_client.extract_sheet(sliced, complexity)
        except httpx.HTTPError as exc:
            raise VisionUpstreamError(f"Vision extraction HTTP error: {exc}") from exc
        finally:
            if header_task is not None:
                if not header_task.done():
                    header_task.cancel()
                results = await asyncio.gather(header_task, return_exceptions=True)
                if results and isinstance(results[0], FastHeaderPreviewEntity):
                    header_preview = results[0]
        return extracted, header_preview

    async def _parse_loaded(
        self,
        loaded: LoadedImageEntity,
        *,
        force_refresh: bool,
        on_step: StepCallback | None,
        on_preview: PreviewCallback | None,
        started_at: float,
    ) -> ParserResultEntity:
        ref_year, ref_month = self._factory.resolve_reference_date()
        cache_key = build_sheet_cache_key(
            loaded.sha256,
            reference_year=ref_year,
            reference_month=ref_month,
            default_auction_strictness=self._factory.default_auction_strictness,
            schema_version=self._schema_version,
        )
        if not force_refresh:
            cached = await self._cache.get(cache_key, filename=loaded.original_filename)
            if cached is not None:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                await _notify_step(on_step, TaskStep.COMPLETED, 100)
                return replace(
                    cached,
                    meta=replace(cached.meta, cached=True, processing_ms=elapsed_ms),
                )

        sliced = await self._cropper.slice_image_bytes(loaded.data)
        await _notify_step(on_step, TaskStep.GATEKEEPER, 30)
        try:
            decision = await self._vision_client.check_sheet(sliced.full_png)
        except httpx.HTTPError as exc:
            raise VisionUpstreamError(f"Vision gatekeeper HTTP error: {exc}") from exc

        if not decision.is_accepted:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            await _notify_step(on_step, TaskStep.FAILED, 100)
            return self._factory.build_rejected(
                processing_ms=elapsed_ms,
                sha256=loaded.sha256,
                model_used=decision.model_used or self._vision_client.flash_model_name,
                gatekeeper=decision,
            )

        extracted, header_preview = await self._run_extraction(
            sliced,
            decision.complexity,
            on_step=on_step,
            on_preview=on_preview,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        result = self._factory.build_result(
            extracted,
            processing_ms=elapsed_ms,
            mode_used=decision.complexity.value,
            cached=False,
            model_used=extracted.model_used or self._vision_client.flash_model_name,
            sha256=loaded.sha256,
            gatekeeper=decision,
            header_preview=header_preview,
            reference_date=(ref_year, ref_month),
        )

        await self._cache.set(cache_key, result)
        await _notify_step(on_step, TaskStep.COMPLETED, 100)
        return result
