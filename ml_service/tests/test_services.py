"""Unit tests for SheetParserService and BatchParserService."""

import asyncio
from pathlib import Path

import httpx
import pytest

from ml_service.api.mappers import to_batch_progress_response
from ml_service.domains.entities import FastHeaderPreviewEntity, GatekeeperDecisionEntity
from ml_service.domains.enums import (
    BatchItemState,
    BatchStatus,
    LayoutComplexity,
    ParseStatus,
    TaskStep,
)
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.image_cropper import PillowImageCropper
from ml_service.infrastructure.image_loader import AsyncImageLoader
from ml_service.infrastructure.result_cache import ResultCache
from ml_service.services.batch_parser_service import (
    BatchCapacityError,
    BatchConflictError,
    BatchParserService,
)
from ml_service.services.sheet_parser_service import SheetParserService
from tests.conftest import make_image_bytes, make_raw_extraction


class _FakeVisionClient:
    def __init__(self, *, accepted: bool = True, fail_extract: bool = False) -> None:
        self.accepted = accepted
        self.fail_extract = fail_extract
        self.check_calls = 0
        self.fast_header_calls = 0
        self.extract_calls = 0

    @property
    def flash_model_name(self) -> str:
        return "gemini-3.6-flash"

    async def check_sheet(self, _full_png: bytes) -> GatekeeperDecisionEntity:
        self.check_calls += 1
        return GatekeeperDecisionEntity(
            is_auction_sheet=self.accepted,
            is_readable=self.accepted,
            complexity=LayoutComplexity.CLEAN_DIGITAL,
            model_used="gemini-decision-1",
            duration_ms=10,
        )

    async def extract_fast_header(self, _sliced) -> FastHeaderPreviewEntity | None:
        self.fast_header_calls += 1
        return FastHeaderPreviewEntity(
            make="Toyota", model="Corolla Touring", lot_number="3142", duration_ms=15
        )

    async def extract_sheet(self, _sliced, _complexity: LayoutComplexity):
        await asyncio.sleep(0)
        self.extract_calls += 1
        if self.fail_extract:
            raise RuntimeError("Gemini extraction failed")
        return make_raw_extraction()


def _build_parser_service(
    tmp_path: Path,
    *,
    vision: _FakeVisionClient | None = None,
    transport: httpx.MockTransport | None = None,
) -> tuple[SheetParserService, _FakeVisionClient, AsyncImageLoader]:
    http_client = httpx.AsyncClient(transport=transport)
    loader = AsyncImageLoader(
        http_client=http_client,
        max_bytes=5 * 1024 * 1024,
        dns_resolver=lambda _host: ["93.184.216.34"],
    )
    cropper = PillowImageCropper(min_px=400, max_px=600, image_format="JPEG")
    v = vision or _FakeVisionClient()
    service = SheetParserService(
        image_loader=loader,
        cropper=cropper,
        vision_client=v,
        factory=SheetFactory(),
        cache=ResultCache(cache_dir=tmp_path / "cache"),
    )
    return service, v, loader


@pytest.mark.asyncio
async def test_sheet_parser_service_cache_hit_force_refresh_and_rejection(
    tmp_path: Path, sample_png_bytes: bytes
) -> None:
    service, vision, loader = _build_parser_service(tmp_path)
    steps: list[tuple[TaskStep, int]] = []
    previews: list[str] = []

    async def on_step(step: TaskStep, pct: int) -> None:
        steps.append((step, pct))

    async def on_preview(title: str) -> None:
        previews.append(title)

    first = await service.parse_bytes(
        sample_png_bytes, filename="corolla.png", on_step=on_step, on_preview=on_preview
    )
    assert first.status == ParseStatus.OK
    assert first.meta.cached is False
    assert vision.extract_calls == 1
    assert previews == ["Toyota Corolla Touring #3142"]
    assert steps[-1] == (TaskStep.COMPLETED, 100)

    # Cache hit skips vision calls
    second = await service.parse_bytes(sample_png_bytes, filename="corolla.png")
    assert second.meta.cached is True
    assert vision.extract_calls == 1

    # force_refresh bypasses cache
    third = await service.parse_bytes(sample_png_bytes, filename="corolla.png", force_refresh=True)
    assert third.meta.cached is False
    assert vision.extract_calls == 2
    await loader.http_client.aclose()

    # Gatekeeper rejection returns REJECTED_NOT_SHEET without calling extract_sheet
    reject_service, reject_vision, reject_loader = _build_parser_service(
        tmp_path / "rej", vision=_FakeVisionClient(accepted=False)
    )
    rejected = await reject_service.parse_bytes(sample_png_bytes, filename="cat.png")
    assert rejected.status == ParseStatus.REJECTED_NOT_SHEET
    assert reject_vision.extract_calls == 0
    await reject_loader.http_client.aclose()


@pytest.mark.asyncio
async def test_sheet_parser_service_parse_url(tmp_path: Path, sample_jpeg_bytes: bytes) -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, content=sample_jpeg_bytes))
    service, _vision, loader = _build_parser_service(tmp_path, transport=transport)
    result = await service.parse_url("https://cdn.example.com/sheet.jpg")
    assert result.status == ParseStatus.OK
    assert result.sheet is not None
    assert result.sheet.lot_number == "3142"
    assert _vision.fast_header_calls == 0
    await loader.http_client.aclose()


@pytest.mark.asyncio
async def test_sheet_parser_skips_fast_header_when_disabled(
    tmp_path: Path, sample_png_bytes: bytes
) -> None:
    vision = _FakeVisionClient()
    http_client = httpx.AsyncClient()
    loader = AsyncImageLoader(
        http_client=http_client,
        max_bytes=5 * 1024 * 1024,
        dns_resolver=lambda _host: ["93.184.216.34"],
    )
    service = SheetParserService(
        image_loader=loader,
        cropper=PillowImageCropper(min_px=400, max_px=600, image_format="JPEG"),
        vision_client=vision,
        factory=SheetFactory(),
        cache=ResultCache(cache_dir=tmp_path / "cache"),
        enable_fast_header=False,
    )
    previews: list[str] = []

    async def on_preview(title: str) -> None:
        previews.append(title)

    res = await service.parse_bytes(
        sample_png_bytes, filename="no_header.png", on_preview=on_preview
    )
    assert res.status == ParseStatus.OK
    assert vision.fast_header_calls == 0
    assert previews == []
    await loader.http_client.aclose()


@pytest.mark.asyncio
async def test_batch_parser_service_lifecycle_add_items_and_limits(tmp_path: Path) -> None:
    service, _vision, loader = _build_parser_service(tmp_path)
    batch_service = BatchParserService(
        parser_service=service,
        max_items_per_batch=3,
        max_concurrency=2,
        image_loader=loader,
        ttl_seconds=60.0,
        max_batches=2,
    )

    img1 = make_image_bytes(fmt="PNG", size=(150, 100))
    img2 = make_image_bytes(fmt="JPEG", size=(160, 100))
    img3 = make_image_bytes(fmt="PNG", size=(170, 100))

    with pytest.raises(ValueError, match="between 1 and 3"):
        await batch_service.create_batch([])

    job = await batch_service.create_batch([(img1, "a.png")])
    extended = await batch_service.add_items(job.batch_id, [(img2, "b.jpg")])
    assert extended.total_items == 2

    with pytest.raises(ValueError, match="cannot exceed 3"):
        await batch_service.add_items(job.batch_id, [(img3, "c.png"), (img1, "d.png")])

    # Wait for background tasks to finish
    for _ in range(50):
        current = await batch_service.get_batch(job.batch_id)
        if current and current.is_terminal:
            break
        await asyncio.sleep(0.02)

    done_job = await batch_service.get_batch(job.batch_id)
    assert done_job is not None
    assert done_job.status == BatchStatus.COMPLETED
    assert done_job.ready_count == 2
    assert all(item.status == BatchItemState.READY for item in done_job.items)

    with pytest.raises(BatchConflictError):
        await batch_service.add_items(job.batch_id, [(img3, "c.png")])

    await batch_service.shutdown()
    await loader.http_client.aclose()


@pytest.mark.asyncio
async def test_batch_parser_service_capacity_and_failures(tmp_path: Path) -> None:
    service, _vision, loader = _build_parser_service(
        tmp_path, vision=_FakeVisionClient(fail_extract=True)
    )
    batch_service = BatchParserService(
        parser_service=service,
        max_items_per_batch=5,
        max_concurrency=1,
        image_loader=loader,
        ttl_seconds=0.0,
        max_batches=1,
    )

    img = make_image_bytes(fmt="PNG", size=(120, 90))
    job = await batch_service.create_batch([(img, "fail.png")])
    for _ in range(50):
        if job.is_terminal:
            break
        await asyncio.sleep(0.02)
    assert job.status == BatchStatus.FAILED
    assert job.failed_count == 1

    # ttl_seconds=0.0 allows immediate eviction of terminal batch on next create
    job2 = await batch_service.create_batch([(img, "fail2.png")])
    assert job2.batch_id != job.batch_id

    # Force non-terminal active batch to test BatchCapacityError
    job2.items[0].status = BatchItemState.PROCESSING
    with pytest.raises(BatchCapacityError):
        await batch_service.create_batch([(img, "blocked.png")])

    await batch_service.shutdown()
    await loader.http_client.aclose()


@pytest.mark.asyncio
async def test_batch_parser_service_rejected_partial_failed_and_expired_add_items(
    tmp_path: Path,
) -> None:
    img = make_image_bytes(fmt="PNG", size=(120, 90))

    # 1) Rejected item -> REJECTED_NOT_SHEET + warning mascot
    rej_service, _v1, rej_loader = _build_parser_service(
        tmp_path / "rej", vision=_FakeVisionClient(accepted=False)
    )
    rej_batch_svc = BatchParserService(parser_service=rej_service, max_items_per_batch=5)
    rej_job = await rej_batch_svc.create_batch([(img, "not_sheet.png")])
    for _ in range(50):
        if rej_job.is_terminal:
            break
        await asyncio.sleep(0.02)
    assert rej_job.status == BatchStatus.FAILED
    assert rej_job.rejected_count == 1
    assert to_batch_progress_response(rej_job).mascot.mood == "warning"
    await rej_batch_svc.shutdown()
    await rej_loader.http_client.aclose()

    # 2) Partial failure (one succeeds, one raises) -> PARTIAL_FAILED + confused mascot
    class _AlternatingVision(_FakeVisionClient):
        async def extract_sheet(self, _sliced, _complexity: LayoutComplexity):
            self.extract_calls += 1
            if self.extract_calls == 2:
                raise RuntimeError("boom on second image")
            return make_raw_extraction()

    part_service, _v2, part_loader = _build_parser_service(
        tmp_path / "part", vision=_AlternatingVision()
    )
    part_batch_svc = BatchParserService(
        parser_service=part_service,
        max_items_per_batch=5,
        max_concurrency=1,
        ttl_seconds=0.0,
    )
    img2 = make_image_bytes(fmt="JPEG", size=(140, 100))
    part_job = await part_batch_svc.create_batch([(img, "ok.png"), (img2, "fail.jpg")])
    for _ in range(50):
        if part_job.is_terminal:
            break
        await asyncio.sleep(0.02)
    assert part_job.status == BatchStatus.PARTIAL_FAILED
    assert part_job.ready_count == 1
    assert part_job.failed_count == 1
    assert to_batch_progress_response(part_job).mascot.mood == "confused"

    # Expired batch (ttl_seconds=0.0) raises KeyError on add_items
    with pytest.raises(KeyError):
        await part_batch_svc.add_items(part_job.batch_id, [(img, "late.png")])

    await part_batch_svc.shutdown()
    await part_loader.http_client.aclose()
