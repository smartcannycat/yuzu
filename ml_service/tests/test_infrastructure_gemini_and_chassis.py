"""Offline tests for AsyncGeminiVisionClient, GeminiRunner, and ChassisOcrClient."""

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types
from google.genai.errors import ClientError, ServerError

from ml_service.domains.enums import LayoutComplexity
from ml_service.infrastructure.chassis_ocr_client import ChassisOcrClient, sanitize_chassis_read
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient
from ml_service.infrastructure.key_pool import GeminiKeyPool
from tests.conftest import make_image_bytes, make_sliced_sheet


def _valid_extraction_json() -> str:
    payload = {
        "auction_house_raw": "TAA",
        "lot_number_raw": "3142",
        "make_raw": "トヨタ",
        "model_raw": "カローラツーリング",
        "trim_raw": "W×B",
        "model_code_raw": "6AA-ZWE211W",
        "chassis_number_raw": "6012345",
        "first_reg_raw": "R4.05",
        "mileage_raw": "45000km",
        "engine_cc_raw": "1800",
        "transmission_raw": "CVT",
        "drive_type_raw": "2WD",
        "color_raw": "パール",
        "paint_code_raw": "070",
        "shaken_raw": "R8.05",
        "recycling_fee_raw": "11200",
        "overall_grade": "4.5",
        "exterior_grade": "B",
        "interior_grade": "B",
        "inspector_notes_raw": [],
        "seller_comments_raw": [],
        "auction_house": "TAA",
        "make_en": "Toyota",
        "model_en": "Corolla Touring",
        "trim_en": "W×B",
        "mileage_km": 45000,
        "odometer_status": "confirmed",
        "engine_cc": 1800,
        "transmission_ru": "вариатор",
        "drive_type": "2WD",
        "fuel_type": "hybrid",
        "color_ru": "Белый",
        "color_changed_ru": None,
        "shaken_ru": "05.2026",
        "recycling_fee_yen": 11200,
        "recycling_fee_paid": True,
        "equipment_ru": ["AAC"],
        "defects": [],
        "risk_flags": {
            "is_flooded": False,
            "airbag_deployed": False,
            "hail_damage": False,
            "underbody_rust": False,
            "underbody_corrosion": False,
            "core_support_repair": False,
            "pillar_or_frame_repair": False,
            "color_changed": False,
            "windshield_damage": False,
        },
        "inspector_notes_ru": [],
        "seller_comments_ru": [],
        "extra_ru": [],
        "unreadable_fields": [],
        "auction_branch": "Yokohama",
        "right_hand_drive": True,
        "name_change_deadline": None,
        "ocr_warnings": [],
    }
    return json.dumps(payload, ensure_ascii=False)


class _FakeAsyncDecisions:
    def __init__(self, handler):
        self._handler = handler

    async def create(self, **kwargs):
        result = self._handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


class _FakeAsyncModels:
    def __init__(self, handler):
        self._handler = handler

    async def generate_content(self, **kwargs):
        result = self._handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


class _FakeGenaiClient:
    def __init__(self, *, decisions_handler=None, models_handler=None) -> None:
        self.closed = False
        self.aclosed = False
        fake_models = _FakeAsyncModels(models_handler or (lambda **_kw: SimpleNamespace(text="")))
        fake_decisions = (
            _FakeAsyncDecisions(decisions_handler) if decisions_handler is not None else None
        )

        async def _aclose() -> None:
            self.aclosed = True

        self.aio = SimpleNamespace(
            models=fake_models,
            decisions=fake_decisions,
            aclose=_aclose,
        )

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_gatekeeper_disabled_accepted_and_fail_open() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)

    disabled_client = AsyncGeminiVisionClient(key_pool=pool, enable_gatekeeper=False)
    decision = await disabled_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert decision.is_accepted is True
    assert decision.complexity == LayoutComplexity.COMPLEX_OR_HANDWRITTEN

    ok_client = AsyncGeminiVisionClient(key_pool=pool, enable_gatekeeper=True)
    ok_client.runner.set_client(
        "k1",
        _FakeGenaiClient(
            decisions_handler=lambda **_kw: SimpleNamespace(
                answers={
                    "is_auction_sheet": SimpleNamespace(noul=0.95),
                    "is_readable": SimpleNamespace(noul=0.80),
                    "layout_complexity": SimpleNamespace(choice="clean_digital"),
                }
            )
        ),
    )
    accepted = await ok_client.check_sheet(make_image_bytes(fmt="JPEG"))
    assert accepted.is_accepted is True
    assert accepted.complexity == LayoutComplexity.CLEAN_DIGITAL

    fail_open_client = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=True
    )
    failing_fake = _FakeGenaiClient(
        decisions_handler=lambda **_kw: (_ for _ in ()).throw(
            ServerError(503, {"error": {"message": "overloaded"}})
        )
    )
    fail_open_client.runner.set_client("k1", failing_fake)
    fallback_decision = await fail_open_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert fallback_decision.is_accepted is True
    assert fallback_decision.warning == "gatekeeper_unavailable:ServerError"

    fail_closed_client = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=False
    )
    fail_closed_client.runner.set_client("k1", failing_fake)
    with pytest.raises(ServerError):
        await fail_closed_client.check_sheet(make_image_bytes(fmt="PNG"))


@pytest.mark.asyncio
async def test_extract_fast_header_success_and_timeout() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)
    client = AsyncGeminiVisionClient(key_pool=pool, fast_header_timeout_seconds=0.2)
    client.runner.set_client(
        "k1",
        _FakeGenaiClient(
            models_handler=lambda **_kw: SimpleNamespace(
                text=json.dumps({"make_en": "Toyota", "model_en": "Aqua", "lot_number": "101"})
            )
        ),
    )
    preview = await client.extract_fast_header(make_sliced_sheet())
    assert preview is not None
    assert preview.preview_title == "Toyota Aqua #101"

    async def _slow(**_kw):
        await asyncio.sleep(0.5)
        return SimpleNamespace(text="{}")

    slow_client = AsyncGeminiVisionClient(key_pool=pool, fast_header_timeout_seconds=0.05)
    slow_client.runner.set_client("k1", _FakeGenaiClient(models_handler=_slow))
    assert await slow_client.extract_fast_header(make_sliced_sheet()) is None


@pytest.mark.asyncio
async def test_extract_sheet_downgrade_failover_and_hedging() -> None:
    pool = GeminiKeyPool(["k1", "k2"], rpm_limit=4)
    client = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="model-primary",
        fallback_models=["model-backup"],
        thinking_level="HIGH",
        hedge_delay_seconds=0.05,
        request_deadline_seconds=5.0,
    )

    seen_levels: list[types.ThinkingLevel] = []

    def _k1_handler(**kwargs):
        model = kwargs["model"]
        config = kwargs["config"]
        level = config.thinking_config.thinking_level
        seen_levels.append(level)
        if model == "model-primary" and level == types.ThinkingLevel.HIGH:
            raise ClientError(400, {"error": {"message": "Thinking level HIGH unsupported"}})
        if model == "model-primary":
            raise ClientError(429, {"error": {"message": "Quota exceeded"}})
        return SimpleNamespace(text=_valid_extraction_json())

    def _k2_handler(**kwargs):
        model = kwargs["model"]
        if model == "model-primary":
            raise ServerError(503, {"error": {"message": "Primary down"}})
        return SimpleNamespace(text=_valid_extraction_json())

    client.runner.set_client("k1", _FakeGenaiClient(models_handler=_k1_handler))
    client.runner.set_client("k2", _FakeGenaiClient(models_handler=_k2_handler))

    entity = await client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
    assert entity.model_used == "model-backup"
    assert entity.make_en == "Toyota"
    assert types.ThinkingLevel.LOW in seen_levels
    assert any(att.model == "model-backup" and att.status == "ok" for att in entity.attempts)


@pytest.mark.asyncio
async def test_extract_sheet_hedged_winner_cancels_loser() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=4)
    client = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="slow-primary",
        fallback_models=["fast-backup"],
        hedge_delay_seconds=0.05,
        request_deadline_seconds=5.0,
    )

    async def _handler(**kwargs):
        if kwargs["model"] == "slow-primary":
            await asyncio.sleep(0.35)
        return SimpleNamespace(text=_valid_extraction_json())

    client.runner.set_client("k1", _FakeGenaiClient(models_handler=_handler))
    entity = await client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
    assert entity.model_used == "fast-backup"
    assert any(
        att.model == "slow-primary" and att.status == "hedged_cancelled" for att in entity.attempts
    )


@pytest.mark.asyncio
async def test_extract_sheet_all_models_fail_raises_runtime_error() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)
    client = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="m1",
        fallback_models=["m2"],
        hedge_delay_seconds=5.0,
        request_deadline_seconds=5.0,
    )
    client.runner.set_client(
        "k1",
        _FakeGenaiClient(
            models_handler=lambda **_kw: (_ for _ in ()).throw(
                ServerError(503, {"error": {"message": "down"}})
            )
        ),
    )
    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        await client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)


def test_sanitize_chassis_read() -> None:
    assert sanitize_chassis_read(" gb5 - 1025108 ") == ("GB5-1025108", "GB5-1025108")
    assert sanitize_chassis_read("1025108") == ("1025108", "1025108")
    assert sanitize_chassis_read("blurry text") == (None, "BLURRYTEXT")
    assert sanitize_chassis_read("   ") == (None, None)


@pytest.mark.asyncio
async def test_chassis_ocr_client_caches_success_but_not_transient_outage(tmp_path: Path) -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)
    vision = AsyncGeminiVisionClient(key_pool=pool, flash_model="m1", fallback_models=["m2"])
    chassis_client = ChassisOcrClient(runner=vision.runner, cache_dir=tmp_path / "cache")
    img = make_image_bytes(fmt="JPEG", size=(120, 40))

    # First: simulate transient outage across all models -> must NOT write poison cache
    vision.runner.set_client(
        "k1",
        _FakeGenaiClient(
            models_handler=lambda **_kw: (_ for _ in ()).throw(
                ServerError(503, {"error": {"message": "down"}})
            )
        ),
    )
    failed = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert failed.frame_id is None
    assert failed.cached is False
    assert list((tmp_path / "cache").glob("*.json")) == []

    # Next: model m2 succeeds -> writes cache; second call hits cache
    vision.runner.clear_model_cooldowns()

    def _ok_on_m2(**kwargs):
        if kwargs["model"] == "m1":
            raise ServerError(503, {"error": {"message": "m1 down"}})
        return SimpleNamespace(text=json.dumps({"frame_id": "gb5-1025108", "confidence": "high"}))

    vision.runner.set_client("k1", _FakeGenaiClient(models_handler=_ok_on_m2))
    ok = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert ok.frame_id == "GB5-1025108"
    assert ok.confidence == "high"
    assert ok.cached is False

    cached = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert cached.frame_id == "GB5-1025108"
    assert cached.cached is True


@pytest.mark.asyncio
async def test_gatekeeper_decisions_none_429_and_unreadable_rejection() -> None:
    pool = GeminiKeyPool(["k1", "k2"], rpm_limit=4)

    no_decisions_open = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=True
    )
    no_decisions_open.runner.set_client("k1", _FakeGenaiClient(decisions_handler=None))
    no_decisions_open.runner.set_client("k2", _FakeGenaiClient(decisions_handler=None))
    open_dec = await no_decisions_open.check_sheet(make_image_bytes(fmt="PNG"))
    assert open_dec.is_accepted is True
    assert open_dec.warning == "gatekeeper_unavailable:RuntimeError"

    no_decisions_closed = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=False
    )
    no_decisions_closed.runner.set_client("k1", _FakeGenaiClient(decisions_handler=None))
    no_decisions_closed.runner.set_client("k2", _FakeGenaiClient(decisions_handler=None))
    with pytest.raises(RuntimeError, match=r"decisions"):
        await no_decisions_closed.check_sheet(make_image_bytes(fmt="PNG"))

    rate_limited_open = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        enable_gatekeeper=True,
        gatekeeper_fail_open=True,
    )
    rate_limited_open.runner.set_client(
        "k1",
        _FakeGenaiClient(
            decisions_handler=lambda **_kw: (_ for _ in ()).throw(
                ClientError(429, {"error": {"message": "rate limit"}})
            )
        ),
    )
    limited_dec = await rate_limited_open.check_sheet(make_image_bytes(fmt="PNG"))
    assert limited_dec.warning == "gatekeeper_unavailable:ClientError"
    assert rate_limited_open.key_pool.is_key_in_cooldown("k1") is True

    unreadable_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        enable_gatekeeper=True,
    )
    unreadable_client.runner.set_client(
        "k1",
        _FakeGenaiClient(
            decisions_handler=lambda **_kw: SimpleNamespace(
                answers={
                    "is_auction_sheet": SimpleNamespace(noul=0.95),
                    "is_readable": SimpleNamespace(noul=0.10),
                    "layout_complexity": SimpleNamespace(choice="complex_or_handwritten"),
                }
            )
        ),
    )
    rejected = await unreadable_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert rejected.is_auction_sheet is True
    assert rejected.is_readable is False
    assert rejected.is_accepted is False


@pytest.mark.asyncio
async def test_extract_sheet_complex_parts_valueerror_failover_403_and_deadline() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=4)
    seen_contents_len: list[int] = []
    client = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="m-empty",
        fallback_models=["m-valid"],
        hedge_delay_seconds=5.0,
        request_deadline_seconds=5.0,
    )

    def _failover_handler(**kwargs):
        seen_contents_len.append(len(kwargs["contents"]))
        if kwargs["model"] == "m-empty":
            return SimpleNamespace(text="")
        return SimpleNamespace(text=_valid_extraction_json())

    client.runner.set_client("k1", _FakeGenaiClient(models_handler=_failover_handler))
    entity = await client.extract_sheet(
        make_sliced_sheet(), LayoutComplexity.COMPLEX_OR_HANDWRITTEN
    )
    assert entity.model_used == "m-valid"
    assert seen_contents_len == [11, 11]
    assert client.runner.is_model_cooled_down("m-empty") is True

    bad_json_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        flash_model="m1",
        fallback_models=["m2"],
        hedge_delay_seconds=5.0,
        request_deadline_seconds=5.0,
    )
    bad_json_client.runner.set_client(
        "k1",
        _FakeGenaiClient(models_handler=lambda **_kw: SimpleNamespace(text="{not-json")),
    )
    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        await bad_json_client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)

    called_models: list[str] = []
    forbidden_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        flash_model="m1",
        fallback_models=["m2"],
        hedge_delay_seconds=5.0,
        request_deadline_seconds=5.0,
    )

    def _forbidden(**kwargs):
        called_models.append(kwargs["model"])
        raise ClientError(403, {"error": {"message": "API key invalid"}})

    forbidden_client.runner.set_client("k1", _FakeGenaiClient(models_handler=_forbidden))
    with pytest.raises(ClientError):
        await forbidden_client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
    assert called_models == ["m1"]

    timeout_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        flash_model="m1",
        fallback_models=[],
        request_deadline_seconds=0.05,
    )

    async def _very_slow(**_kw):
        await asyncio.sleep(0.25)
        return SimpleNamespace(text=_valid_extraction_json())

    timeout_client.runner.set_client("k1", _FakeGenaiClient(models_handler=_very_slow))
    with pytest.raises(TimeoutError):
        await timeout_client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)


@pytest.mark.asyncio
async def test_chassis_ocr_429_does_not_cooldown_model_whitespace_and_corrupt_disk(
    tmp_path: Path,
) -> None:
    pool = GeminiKeyPool(["k1", "k2"], rpm_limit=4)
    vision = AsyncGeminiVisionClient(key_pool=pool, flash_model="m1", fallback_models=["m2"])
    chassis_client = ChassisOcrClient(vision_client=vision, cache_dir=tmp_path / "cache")
    img = make_image_bytes(fmt="JPEG", size=(120, 40))

    def _429_then_whitespace(key: str):
        def _inner(**_kw):
            if key == "k1":
                raise ClientError(429, {"error": {"message": "Too many requests"}})
            return SimpleNamespace(text=json.dumps({"frame_id": "   ", "confidence": "low"}))

        return _inner

    vision.runner.set_client("k1", _FakeGenaiClient(models_handler=_429_then_whitespace("k1")))
    vision.runner.set_client("k2", _FakeGenaiClient(models_handler=_429_then_whitespace("k2")))

    res = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert vision.runner.is_model_cooled_down("m1") is False
    assert pool.is_key_in_cooldown("k1") is True
    assert res.frame_id is None
    assert res.raw is None

    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert cache_files == []

    cache_path = chassis_client._cache_path(img)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{corrupt", encoding="utf-8")

    vision.runner.set_client(
        "k2",
        _FakeGenaiClient(
            models_handler=lambda **_kw: SimpleNamespace(
                text=json.dumps({"frame_id": "NRE210-1234567", "confidence": "high"})
            )
        ),
    )
    recovered = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert recovered.frame_id == "NRE210-1234567"
    assert recovered.cached is False


def _make_plaque_jpeg_bytes() -> bytes:
    import io

    from PIL import Image, ImageDraw

    img = Image.new("L", (240, 80), 255)
    draw = ImageDraw.Draw(img)
    draw.line([(0, 4), (239, 4)], fill=0, width=2)
    draw.line([(0, 29), (239, 29)], fill=0, width=2)
    draw.text((40, 10), "FL4-1001524", fill=0)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_local_chassis_ocr_fast_path_skips_gemini_and_falls_back_on_low_conf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ml_service.infrastructure.chassis_local_ocr import LocalChassisOcrReader

    plaque_bytes = _make_plaque_jpeg_bytes()
    gemini_calls = 0

    def _never_called(**_kw):
        nonlocal gemini_calls
        gemini_calls += 1
        return SimpleNamespace(text=json.dumps({"frame_id": "GB5-3108038", "confidence": "high"}))

    pool = GeminiKeyPool(["k1"], rpm_limit=2)
    vision = AsyncGeminiVisionClient(key_pool=pool, flash_model="m1", fallback_models=["m2"])
    vision.runner.set_client("k1", _FakeGenaiClient(models_handler=_never_called))

    reader = LocalChassisOcrReader(enabled=True, min_confidence=80.0)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/tesseract")
    monkeypatch.setattr(
        reader,
        "_run_tesseract_tsv",
        lambda _band: (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t10\t100\t20\t91.4\tFL4-1001524\n"
        ),
    )

    chassis_client = ChassisOcrClient(
        vision_client=vision, local_ocr=reader, cache_dir=tmp_path / "cache"
    )
    fast = await chassis_client.read_chassis_number(plaque_bytes, mime_type="image/jpeg")
    assert fast.frame_id == "FL4-1001524"
    assert fast.confidence == "high"
    assert fast.cached is False
    assert gemini_calls == 0

    cached = await chassis_client.read_chassis_number(plaque_bytes, mime_type="image/jpeg")
    assert cached.frame_id == "FL4-1001524"
    assert cached.cached is True
    assert gemini_calls == 0

    # Low-confidence handwritten/noisy output falls back to Gemini seamlessly.
    monkeypatch.setattr(
        reader,
        "_run_tesseract_tsv",
        lambda _band: (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t10\t100\t20\t35.0\tZLEFQJJT5\n"
        ),
    )
    noisy_bytes = _make_plaque_jpeg_bytes() + b"\x00"
    fallback = await chassis_client.read_chassis_number(noisy_bytes, mime_type="image/jpeg")
    assert fallback.frame_id == "GB5-3108038"
    assert gemini_calls == 1


@pytest.mark.asyncio
async def test_chassis_ocr_downgrades_minimal_thinking_level_and_cools_down_bad_models(
    tmp_path: Path,
) -> None:
    seen_levels: list[tuple[str, types.ThinkingLevel | None]] = []

    def _handler(**kw):
        model = kw["model"]
        level = kw["config"].thinking_config.thinking_level
        seen_levels.append((model, level))
        if model == "m-bad":
            raise ClientError(404, {"error": {"message": "Not found"}})
        if level == types.ThinkingLevel.MINIMAL:
            raise ClientError(
                400,
                {"error": {"message": "Thinking level MINIMAL is not supported for this model."}},
            )
        return SimpleNamespace(text=json.dumps({"frame_id": "RV3-1005521", "confidence": "high"}))

    pool = GeminiKeyPool(["k1"], rpm_limit=5)
    vision = AsyncGeminiVisionClient(
        key_pool=pool,
        flash_model="m-bad",
        fallback_models=["m-low-only"],
        client_error_cooldown_seconds=120.0,
    )
    vision.runner.set_client("k1", _FakeGenaiClient(models_handler=_handler))
    chassis_client = ChassisOcrClient(vision_client=vision, cache_dir=tmp_path / "cache")

    res = await chassis_client.read_chassis_number(make_image_bytes(fmt="JPEG", size=(120, 40)))
    assert res.frame_id == "RV3-1005521"
    assert vision.runner.is_model_cooled_down("m-bad") is False
    assert ("m-low-only", types.ThinkingLevel.MINIMAL) in seen_levels
    assert ("m-low-only", types.ThinkingLevel.LOW) in seen_levels
