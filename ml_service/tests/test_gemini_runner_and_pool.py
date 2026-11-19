"""Concurrency, failover, hedging, key-pool, and client-close tests (ML-MAJ-02,03; ML-MIN-01)."""

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError, ServerError

from ml_service.domains.enums import LayoutComplexity
from ml_service.infrastructure.chassis_ocr_client import ChassisOcrClient
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.main import create_app
from tests.conftest import make_image_bytes, make_settings, make_sliced_sheet
from tests.test_infrastructure_gemini_and_chassis import (
    _FakeGenaiClient,
    _valid_extraction_json,
)


@pytest.mark.asyncio
async def test_pre_hedge_401_403_fail_fast_without_fallback() -> None:
    for code in (401, 403):
        called_models: list[str] = []
        pool = GeminiKeyPool(["k1"], rpm_limit=4)
        client = AsyncGeminiVisionClient(
            key_pool=pool,
            flash_model="m1",
            fallback_models=["m2", "m3"],
            hedge_delay_seconds=1.0,
            request_deadline_seconds=10.0,
        )

        def _fail_auth(*, _models=called_models, _code=code, **kwargs):
            _models.append(kwargs["model"])
            raise ClientError(_code, {"error": {"message": "auth error"}})

        client.runner.set_client("k1", _FakeGenaiClient(models_handler=_fail_auth))
        with pytest.raises(ClientError):
            await client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
        assert called_models == ["m1"]


@pytest.mark.asyncio
async def test_active_hedge_simultaneous_finished_selects_winner_over_sibling_error() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=4)
    client = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="primary-fails",
        fallback_models=["hedge-wins"],
        hedge_delay_seconds=0.02,
        request_deadline_seconds=5.0,
    )
    release = asyncio.Event()

    async def _handler(**kwargs):
        model = kwargs["model"]
        if model == "primary-fails":
            await release.wait()
            raise ClientError(403, {"error": {"message": "forbidden on primary"}})
        # Release both tasks on the exact same event-loop turn so both enter `finished` together
        release.set()
        return SimpleNamespace(text=_valid_extraction_json())

    client.runner.set_client("k1", _FakeGenaiClient(models_handler=_handler))
    entity = await client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
    assert entity.model_used == "hedge-wins"


@pytest.mark.asyncio
async def test_gemini_key_pool_per_key_rpm_and_sleep_outside_locks() -> None:
    # 2 keys, 1 RPM each: first two acquires must complete immediately without waiting on k1
    pool = GeminiKeyPool(["k1", "k2"], rpm_limit=1, rpm_window_seconds=0.25)
    t0 = time.monotonic()
    acquired_keys: list[str] = []
    async with asyncio.timeout(2.0):
        async with pool.acquire() as key1:
            acquired_keys.append(key1)
            async with pool.acquire() as key2:
                acquired_keys.append(key2)
    assert set(acquired_keys) == {"k1", "k2"}
    assert time.monotonic() - t0 < 0.08

    # Third acquire sleeps outside semaphore/rate_lock; semaphore must be unlocked while sleeping
    ctx = pool.acquire()
    waiting_task = asyncio.create_task(ctx.__aenter__())
    await asyncio.sleep(0.02)
    assert pool.semaphore.locked() is False
    assert pool._rate_lock.locked() is False
    waiting_task.cancel()
    await asyncio.gather(waiting_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_lifespan_shutdown_closes_gemini_sdk_clients(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    fake_client = _FakeGenaiClient()

    async with app.router.lifespan_context(app):
        vision = app.state.parser_service._vision_client
        vision.runner.set_client("gemini-key-1", fake_client)
        assert fake_client.aclosed is False
        assert fake_client.closed is False

    assert fake_client.aclosed is True
    assert fake_client.closed is True


@pytest.mark.asyncio
async def test_chassis_ocr_no_cooldown_on_400_403_404_and_invalid_cached_confidence(
    tmp_path: Path,
) -> None:
    img = make_image_bytes(fmt="JPEG", size=(120, 40))

    # 1) 400 / 404 do not cool down shared model and fall back to next model
    for status_code in (400, 404):
        pool = GeminiKeyPool(["k1"], rpm_limit=4)
        vision = AsyncGeminiVisionClient(key_pool=pool, flash_model="m1", fallback_models=["m2"])
        chassis = ChassisOcrClient(runner=vision.runner, cache_dir=tmp_path / f"c_{status_code}")

        def _err_then_ok(*, _status=status_code, **kwargs):
            if kwargs["model"] == "m1":
                raise ClientError(_status, {"error": {"message": "bad model"}})
            return SimpleNamespace(
                text=json.dumps({"frame_id": "GB5-1025108", "confidence": "high"})
            )

        vision.runner.set_client("k1", _FakeGenaiClient(models_handler=_err_then_ok))
        res = await chassis.read_chassis_number(img, mime_type="image/jpeg")
        assert res.frame_id == "GB5-1025108"
        assert vision.runner.is_model_cooled_down("m1") is False

    # 2) 403 does not cool down shared model
    pool_403 = GeminiKeyPool(["k1"], rpm_limit=4)
    vision_403 = AsyncGeminiVisionClient(
        key_pool=pool_403, flash_model="m1", fallback_models=["m2"]
    )
    chassis_403 = ChassisOcrClient(runner=vision_403.runner, cache_dir=tmp_path / "c_403")
    vision_403.runner.set_client(
        "k1",
        _FakeGenaiClient(
            models_handler=lambda **_kw: (_ for _ in ()).throw(
                ClientError(403, {"error": {"message": "forbidden"}})
            )
        ),
    )
    res_403 = await chassis_403.read_chassis_number(img, mime_type="image/jpeg")
    assert res_403.frame_id is None
    assert vision_403.runner.is_model_cooled_down("m1") is False

    # 3) 429 tries remaining healthy keys on the SAME model m1 before falling back
    pool_429 = GeminiKeyPool(["k1", "k2"], rpm_limit=4)
    vision_429 = AsyncGeminiVisionClient(
        key_pool=pool_429, flash_model="m1", fallback_models=["m2"]
    )
    chassis_429 = ChassisOcrClient(runner=vision_429.runner, cache_dir=tmp_path / "c_429")
    seen_calls: list[tuple[str, str]] = []

    def _429_handler(key: str):
        def _inner(**kwargs):
            seen_calls.append((key, kwargs["model"]))
            if key == "k1":
                raise ClientError(429, {"error": {"message": "rate limit"}})
            return SimpleNamespace(
                text=json.dumps({"frame_id": "ZWE211-6012345", "confidence": "medium"})
            )

        return _inner

    vision_429.runner.set_client("k1", _FakeGenaiClient(models_handler=_429_handler("k1")))
    vision_429.runner.set_client("k2", _FakeGenaiClient(models_handler=_429_handler("k2")))
    res_429 = await chassis_429.read_chassis_number(img, mime_type="image/jpeg")
    assert res_429.frame_id == "ZWE211-6012345"
    assert seen_calls == [("k1", "m1"), ("k2", "m1")]
    assert vision_429.runner.is_model_cooled_down("m1") is False

    # 4) Invalid cached confidence fails validation cleanly and falls back instead of 500
    cache_path = chassis_429._cache_path(img)
    cache_path.write_text(
        json.dumps({"frame_id": "OLD-1234", "raw": "OLD-1234", "confidence": "bogus"}),
        encoding="utf-8",
    )
    vision_429.runner.set_client(
        "k2",
        _FakeGenaiClient(
            models_handler=lambda **_kw: (_ for _ in ()).throw(
                ServerError(503, {"error": {"message": "down"}})
            )
        ),
    )
    fallback_res = await chassis_429.read_chassis_number(img, mime_type="image/jpeg")
    assert fallback_res.confidence == "low"
    assert fallback_res.cached is False

    # 5) Chassis cache write OSError degrades gracefully without failing request
    def _fail_write(*_a, **_kw):
        raise OSError("read-only cache dir")

    chassis_429._write_cached_sync = _fail_write  # type: ignore[method-assign]
    vision_429.runner.set_client(
        "k2",
        _FakeGenaiClient(
            models_handler=lambda **_kw: SimpleNamespace(
                text=json.dumps({"frame_id": "GB5-1025108", "confidence": "high"})
            )
        ),
    )
    ok_despite_oserror = await chassis_429.read_chassis_number(img, mime_type="image/jpeg")
    assert ok_despite_oserror.frame_id == "GB5-1025108"
