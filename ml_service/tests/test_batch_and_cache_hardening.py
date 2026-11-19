"""Batch disk-spill, TTL, queued-bytes cap, and ResultCache tests (ML-SEC-02,05; ML-MAJ-01,05)."""

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx
import pytest

from ml_service.domains.enums import BatchItemState, TaskStep
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.image_cropper import PillowImageCropper
from ml_service.infrastructure.image_loader import AsyncImageLoader
from ml_service.infrastructure.result_cache import ResultCache
from ml_service.main import create_app
from ml_service.services.batch_parser_service import BatchCapacityError, BatchParserService
from ml_service.services.sheet_parser_service import SheetParserService
from tests.conftest import make_image_bytes, make_raw_extraction, make_settings
from tests.test_services import _FakeVisionClient


@pytest.mark.asyncio
async def test_batch_ttl_from_completed_monotonic_disk_spill_and_sanitized_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    gate = asyncio.Event()

    class _SlowSecretFailParser:
        async def parse_bytes(
            self,
            data: bytes,
            filename: str = "upload.png",
            *,
            force_refresh: bool = False,
            on_step=None,
            on_preview=None,
        ):
            await gate.wait()
            if "secret" in filename:
                raise RuntimeError("INTERNAL_DB_DSN=postgres://secret:pw@host/db")
            if on_step is not None:
                await on_step(TaskStep.COMPLETED, 100)
            return SheetFactory(reference_year=2026, reference_month=11).build_result(
                make_raw_extraction(),
                processing_ms=10,
                mode_used="clean_digital",
                cached=False,
                model_used="gemini-3.6-flash",
                sha256="abc123",
            )

    cache_dir = tmp_path / "cache"
    batch_service = BatchParserService(
        parser_service=_SlowSecretFailParser(),  # type: ignore[arg-type]
        max_items_per_batch=5,
        max_concurrency=1,
        ttl_seconds=0.05,
        max_batches=5,
        cache_dir=cache_dir,
        max_queued_bytes=1024 * 1024,
    )
    img = make_image_bytes(fmt="PNG", size=(100, 80))
    job = await batch_service.create_batch([(img, "ok.png"), (img, "secret.png")])

    # Spill files exist on disk while tasks are blocked; wait past ttl_seconds (0.05s)
    await asyncio.sleep(0.1)
    spill_files = list((cache_dir / "batch_spill").glob("item_*.bin"))
    assert len(spill_files) >= 1
    assert await batch_service.get_batch(job.batch_id) is not None

    with caplog.at_level(logging.ERROR):
        gate.set()
        for _ in range(50):
            if job.is_terminal:
                break
            await asyncio.sleep(0.01)

    assert job.is_terminal
    assert job.completed_monotonic is not None
    assert job.items[0].status == BatchItemState.READY
    assert job.items[0].current_step == TaskStep.COMPLETED
    assert job.items[0].progress_pct == 100
    assert job.items[1].status == BatchItemState.FAILED
    assert job.items[1].error_message is not None
    assert "INTERNAL_DB_DSN" not in job.items[1].error_message
    assert "postgres://secret" not in job.items[1].error_message
    assert any("Traceback" in r.exc_text or r.exc_info for r in caplog.records if r.exc_info)

    # All spill files cleaned up after completion/error
    assert list((cache_dir / "batch_spill").glob("item_*.bin")) == []
    assert batch_service.queued_bytes == 0

    # Expires only after ttl_seconds elapses from completed_monotonic
    await asyncio.sleep(0.07)
    assert await batch_service.get_batch(job.batch_id) is None
    await batch_service.shutdown()


@pytest.mark.asyncio
async def test_batch_on_step_completed_only_after_ready_and_result_persisted(
    tmp_path: Path,
) -> None:
    observed_states: list[tuple[BatchItemState, bool]] = []

    class _SpyBatchParser(BatchParserService):
        pass

    class _EarlyCompletedParser:
        async def parse_bytes(self, data: bytes, filename: str = "a.png", **kwargs):
            on_step = kwargs.get("on_step")
            if on_step is not None:
                await on_step(TaskStep.COMPLETED, 100)
                # Early COMPLETED callback must not flip state before result is persisted
                observed_states.append((job.items[0].status, job.items[0].result is not None))
                assert job.items[0].current_step != TaskStep.COMPLETED
            return SheetFactory(reference_year=2026, reference_month=11).build_result(
                make_raw_extraction(),
                processing_ms=5,
                mode_used="clean_digital",
                cached=False,
                model_used="gemini-3.6-flash",
                sha256="sha",
            )

    svc = _SpyBatchParser(parser_service=_EarlyCompletedParser(), cache_dir=tmp_path)  # type: ignore[arg-type]
    img = make_image_bytes(fmt="PNG", size=(80, 60))
    job = await svc.create_batch([(img, "a.png")])
    for _ in range(50):
        if job.is_terminal:
            break
        await asyncio.sleep(0.01)

    assert observed_states == [(BatchItemState.PROCESSING, False)]
    assert job.items[0].status == BatchItemState.READY
    assert job.items[0].result is not None
    assert job.items[0].current_step == TaskStep.COMPLETED
    assert job.items[0].progress_pct == 100
    await svc.shutdown()


@pytest.mark.asyncio
async def test_batch_preflight_capacity_and_queued_bytes_cap_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    img = make_image_bytes(fmt="PNG", size=(120, 90))
    app = create_app(
        make_settings(
            tmp_path,
            batch_max_stored_batches=1,
            batch_max_queued_bytes=2048,
        )
    )
    headers = {"X-API-Key": "test-service-key"}
    gate = asyncio.Event()

    class _HeldParser:
        async def parse_bytes(self, *_a, **_kw):
            await gate.wait()
            return SheetFactory(reference_year=2026, reference_month=11).build_result(
                make_raw_extraction(),
                processing_ms=5,
                mode_used="clean_digital",
                cached=False,
                model_used="gemini-3.6-flash",
                sha256="x",
            )

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        app.state.batch_service = BatchParserService(
            parser_service=_HeldParser(),  # type: ignore[arg-type]
            max_items_per_batch=5,
            max_concurrency=1,
            max_batches=1,
            cache_dir=tmp_path / "cache",
            max_queued_bytes=len(img) + 10,
        )
        created = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[("files", ("s1.png", img, "image/png"))],
        )
        assert created.status_code == 202

        # Spy on read_upload_bounded to prove over-capacity request rejects BEFORE reading upload
        import importlib

        api_uploads_mod = importlib.import_module("ml_service.api.uploads")
        read_calls = 0
        orig_read = api_uploads_mod.read_upload_bounded

        async def _spy_read(upload, max_bytes):
            nonlocal read_calls
            read_calls += 1
            return await orig_read(upload, max_bytes)

        monkeypatch.setattr(api_uploads_mod, "read_upload_bounded", _spy_read)
        rejected = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[("files", ("s2.png", img, "image/png"))],
        )
        assert rejected.status_code == 429
        assert read_calls == 0
        gate.set()

    # Global queued-bytes cap across active batches
    svc = BatchParserService(
        parser_service=_HeldParser(),  # type: ignore[arg-type]
        max_batches=10,
        max_queued_bytes=len(img) + 1,
        cache_dir=tmp_path / "qcap",
    )
    gate.clear()
    await svc.create_batch([(img, "one.png")])
    with pytest.raises(BatchCapacityError, match="queued byte cap"):
        await svc.create_batch([(img, "two.png")])
    gate.set()
    await svc.shutdown()
    assert list((tmp_path / "qcap" / "batch_spill").glob("item_*.bin")) == []


@pytest.mark.asyncio
async def test_result_cache_oserror_ttl_quota_and_key_invalidation(
    tmp_path: Path, sample_png_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    factory = SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.65)
    entity = factory.build_result(
        make_raw_extraction(),
        processing_ms=10,
        mode_used="clean_digital",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="abc123",
    )

    # 1) OSError during disk write does not crash ResultCache.set
    cache = ResultCache(cache_dir=cache_dir)
    monkeypatch.setattr(
        cache, "_write_json_entity", lambda *_a, **_kw: (_ for _ in ()).throw(OSError("disk full"))
    )
    await cache.set("safe_key", entity)
    assert await cache.get("safe_key") is not None
    monkeypatch.undo()

    # 2) TTL expiry + disk byte quota pruning
    bounded_dir = tmp_path / "bounded"
    bounded_cache = ResultCache(
        cache_dir=bounded_dir, max_memory_entries=10, ttl_seconds=60.0, max_disk_bytes=100_000
    )
    await bounded_cache.set("k_old", entity)
    old_file = bounded_dir / "k_old.json"
    assert old_file.is_file()
    old_time = time.time() - 120.0
    os.utime(old_file, (old_time, old_time))
    await bounded_cache.set("k_new", entity)
    assert not old_file.exists()

    # Byte quota evicts oldest file when total size exceeds max_disk_bytes
    quota_dir = tmp_path / "quota"
    quota_cache = ResultCache(
        cache_dir=quota_dir, max_memory_entries=10, ttl_seconds=600.0, max_disk_bytes=5000
    )
    await quota_cache.set("q1", entity)
    file_size = (quota_dir / "q1.json").stat().st_size
    quota_cache._max_disk_bytes = file_size + 10
    await quota_cache.set("q2", entity)
    assert not (quota_dir / "q1.json").exists()
    assert (quota_dir / "q2.json").is_file()

    # 3) SheetParserService cache key invalidation on reference_year / month / strictness / schema
    async with httpx.AsyncClient() as http_client:
        loader = AsyncImageLoader(http_client=http_client)
        cropper = PillowImageCropper(min_px=400, max_px=600, image_format="JPEG")
        vision = _FakeVisionClient()
        shared_cache = ResultCache(cache_dir=tmp_path / "svc_cache")

        svc_2026 = SheetParserService(
            loader,
            cropper,
            vision,
            SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.65),
            shared_cache,
            schema_version="v1",
        )
        svc_2027 = SheetParserService(
            loader,
            cropper,
            vision,
            SheetFactory(reference_year=2027, reference_month=11, default_auction_strictness=0.65),
            shared_cache,
            schema_version="v1",
        )
        svc_strict = SheetParserService(
            loader,
            cropper,
            vision,
            SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.80),
            shared_cache,
            schema_version="v1",
        )
        svc_v2 = SheetParserService(
            loader,
            cropper,
            vision,
            SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.65),
            shared_cache,
            schema_version="v2",
        )

        r1 = await svc_2026.parse_bytes(sample_png_bytes, "s.png")
        r1_hit = await svc_2026.parse_bytes(sample_png_bytes, "s.png")
        assert r1.meta.cached is False
        assert r1_hit.meta.cached is True
        assert vision.extract_calls == 1

        # Changing reference_year, strictness, or schema_version must miss cache
        assert (await svc_2027.parse_bytes(sample_png_bytes, "s.png")).meta.cached is False
        assert (await svc_strict.parse_bytes(sample_png_bytes, "s.png")).meta.cached is False
        assert (await svc_v2.parse_bytes(sample_png_bytes, "s.png")).meta.cached is False
        assert vision.extract_calls == 4
