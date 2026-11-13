"""Application service for parsing single Japanese car auction sheets."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
import time
from typing import Protocol

from app.domains.entities import (
    GatekeeperDecisionEntity,
    LoadedImageEntity,
    ParserResultEntity,
    RawExtractionEntity,
    SlicedSheetEntity,
)
from app.domains.enums import LayoutComplexity
from app.factories.sheet_factory import SheetFactory


StepCallback = Callable[[str, int], Awaitable[None]]


class ImageLoaderProtocol(Protocol):
    async def load_from_bytes(self, data: bytes, filename: str = "upload.png") -> LoadedImageEntity: ...

    async def load_from_url(self, url: str) -> LoadedImageEntity: ...


class CropperProtocol(Protocol):
    async def slice_image_bytes(self, data: bytes, overlap: float = 0.20) -> SlicedSheetEntity: ...


class VisionClientProtocol(Protocol):
    @property
    def flash_model_name(self) -> str: ...

    async def check_sheet(self, full_png: bytes) -> GatekeeperDecisionEntity: ...

    async def extract_sheet(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
    ) -> RawExtractionEntity: ...


class ResultCacheProtocol(Protocol):
    async def get(self, sha256: str, filename: str = "") -> ParserResultEntity | None: ...

    async def set(self, sha256: str, result: ParserResultEntity) -> None: ...


async def _notify_step(on_step: StepCallback | None, step: str, progress_pct: int) -> None:
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
    ) -> None:
        self._image_loader = image_loader
        self._cropper = cropper
        self._vision_client = vision_client
        self._factory = factory
        self._cache = cache

    async def parse_bytes(
        self,
        data: bytes,
        filename: str = "upload.png",
        *,
        force_refresh: bool = False,
        on_step: StepCallback | None = None,
    ) -> ParserResultEntity:
        """Parse an uploaded auction sheet byte payload into a normalized ParserResultEntity."""
        started_at = time.perf_counter()
        await _notify_step(on_step, "loading_image", 15)
        loaded = await self._image_loader.load_from_bytes(data, filename=filename)
        return await self._parse_loaded(
            loaded,
            force_refresh=force_refresh,
            on_step=on_step,
            started_at=started_at,
        )

    async def parse_url(
        self,
        url: str,
        *,
        force_refresh: bool = False,
        on_step: StepCallback | None = None,
    ) -> ParserResultEntity:
        """Download an auction sheet image from URL and parse it."""
        started_at = time.perf_counter()
        await _notify_step(on_step, "downloading_image", 15)
        loaded = await self._image_loader.load_from_url(url)
        return await self._parse_loaded(
            loaded,
            force_refresh=force_refresh,
            on_step=on_step,
            started_at=started_at,
        )

    async def _parse_loaded(
        self,
        loaded: LoadedImageEntity,
        *,
        force_refresh: bool,
        on_step: StepCallback | None,
        started_at: float,
    ) -> ParserResultEntity:
        if not force_refresh:
            cached = await self._cache.get(loaded.sha256, filename=loaded.original_filename)
            if cached is not None:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                await _notify_step(on_step, "completed", 100)
                return replace(
                    cached,
                    meta=replace(cached.meta, cached=True, processing_ms=elapsed_ms),
                )

        await _notify_step(on_step, "slicing_image", 30)
        sliced = await self._cropper.slice_image_bytes(loaded.data)

        await _notify_step(on_step, "checking_sheet", 50)
        decision = await self._vision_client.check_sheet(sliced.full_png)
        if not decision.is_accepted:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            await _notify_step(on_step, "completed", 100)
            return self._factory.build_rejected(
                processing_ms=elapsed_ms,
                sha256=loaded.sha256,
                model_used=self._vision_client.flash_model_name,
            )

        await _notify_step(on_step, "extracting_sheet", 75)
        extracted = await self._vision_client.extract_sheet(sliced, decision.complexity)

        await _notify_step(on_step, "normalizing_result", 90)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        result = self._factory.build_result(
            extracted,
            processing_ms=elapsed_ms,
            mode_used=decision.complexity.value,
            cached=False,
            model_used=extracted.model_used or self._vision_client.flash_model_name,
            sha256=loaded.sha256,
        )

        await self._cache.set(loaded.sha256, result)
        await _notify_step(on_step, "completed", 100)
        return result
