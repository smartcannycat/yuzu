"""Offline tests for AsyncGeminiVisionClient and ChassisOcrClient using fake genai clients."""

import json
import time
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


class _FakeDecisions:
    def __init__(self, handler):
        self._handler = handler

    def create(self, **kwargs):
        return self._handler(**kwargs)


class _FakeModels:
    def __init__(self, handler):
        self._handler = handler

    def generate_content(self, **kwargs):
        return self._handler(**kwargs)


class _FakeGenaiClient:
    def __init__(self, *, decisions_handler=None, models_handler=None) -> None:
        if decisions_handler is not None:
            self.decisions = _FakeDecisions(decisions_handler)
        self.models = _FakeModels(models_handler or (lambda **_kw: SimpleNamespace(text="")))


@pytest.mark.asyncio
async def test_gatekeeper_disabled_accepted_and_fail_open() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)

    disabled_client = AsyncGeminiVisionClient(key_pool=pool, enable_gatekeeper=False)
    decision = await disabled_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert decision.is_accepted is True
    assert decision.complexity == LayoutComplexity.COMPLEX_OR_HANDWRITTEN

    ok_client = AsyncGeminiVisionClient(key_pool=pool, enable_gatekeeper=True)
    ok_client._clients["k1"] = _FakeGenaiClient(
        decisions_handler=lambda **_kw: SimpleNamespace(
            answers={
                "is_auction_sheet": SimpleNamespace(noul=0.95),
                "is_readable": SimpleNamespace(noul=0.80),
                "layout_complexity": SimpleNamespace(choice="clean_digital"),
            }
        )
    )
    accepted = await ok_client.check_sheet(make_image_bytes(fmt="JPEG"))
    assert accepted.is_accepted is True
    assert accepted.complexity == LayoutComplexity.CLEAN_DIGITAL

    fail_open_client = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=True
    )
    fail_open_client._clients["k1"] = _FakeGenaiClient(
        decisions_handler=lambda **_kw: (_ for _ in ()).throw(
            ServerError(503, {"error": {"message": "overloaded"}})
        )
    )
    fallback_decision = await fail_open_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert fallback_decision.is_accepted is True
    assert fallback_decision.warning == "gatekeeper_unavailable:ServerError"

    fail_closed_client = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=False
    )
    fail_closed_client._clients["k1"] = fail_open_client._clients["k1"]
    with pytest.raises(ServerError):
        await fail_closed_client.check_sheet(make_image_bytes(fmt="PNG"))


@pytest.mark.asyncio
async def test_extract_fast_header_success_and_timeout() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2)
    client = AsyncGeminiVisionClient(key_pool=pool, fast_header_timeout_seconds=0.2)
    client._clients["k1"] = _FakeGenaiClient(
        models_handler=lambda **_kw: SimpleNamespace(
            text=json.dumps({"make_en": "Toyota", "model_en": "Aqua", "lot_number": "101"})
        )
    )
    preview = await client.extract_fast_header(make_sliced_sheet())
    assert preview is not None
    assert preview.preview_title == "Toyota Aqua #101"

    def _slow(**_kw):
        time.sleep(0.5)
        return SimpleNamespace(text="{}")

    slow_client = AsyncGeminiVisionClient(key_pool=pool, fast_header_timeout_seconds=0.05)
    slow_client._clients["k1"] = _FakeGenaiClient(models_handler=_slow)
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

    client._clients["k1"] = _FakeGenaiClient(models_handler=_k1_handler)
    client._clients["k2"] = _FakeGenaiClient(models_handler=_k2_handler)

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

    def _handler(**kwargs):
        if kwargs["model"] == "slow-primary":
            time.sleep(0.35)
        return SimpleNamespace(text=_valid_extraction_json())

    client._clients["k1"] = _FakeGenaiClient(models_handler=_handler)
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
    client._clients["k1"] = _FakeGenaiClient(
        models_handler=lambda **_kw: (_ for _ in ()).throw(
            ServerError(503, {"error": {"message": "down"}})
        )
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
    chassis_client = ChassisOcrClient(vision_client=vision, cache_dir=tmp_path / "cache")
    img = make_image_bytes(fmt="JPEG", size=(120, 40))

    # First: simulate transient outage across all models -> must NOT write poison cache
    vision._clients["k1"] = _FakeGenaiClient(
        models_handler=lambda **_kw: (_ for _ in ()).throw(
            ServerError(503, {"error": {"message": "down"}})
        )
    )
    failed = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert failed.frame_id is None
    assert failed.cached is False
    assert list((tmp_path / "cache").glob("*.json")) == []

    # Next: model m2 succeeds -> writes cache; second call hits cache
    vision._model_cooldown_until.clear()

    def _ok_on_m2(**kwargs):
        if kwargs["model"] == "m1":
            raise ServerError(503, {"error": {"message": "m1 down"}})
        return SimpleNamespace(text=json.dumps({"frame_id": "gb5-1025108", "confidence": "high"}))

    vision._clients["k1"] = _FakeGenaiClient(models_handler=_ok_on_m2)
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
    no_decisions_open._clients["k1"] = _FakeGenaiClient(decisions_handler=None)
    no_decisions_open._clients["k2"] = _FakeGenaiClient(decisions_handler=None)
    open_dec = await no_decisions_open.check_sheet(make_image_bytes(fmt="PNG"))
    assert open_dec.is_accepted is True
    assert open_dec.warning == "gatekeeper_unavailable:RuntimeError"

    no_decisions_closed = AsyncGeminiVisionClient(
        key_pool=pool, enable_gatekeeper=True, gatekeeper_fail_open=False
    )
    no_decisions_closed._clients["k1"] = _FakeGenaiClient(decisions_handler=None)
    no_decisions_closed._clients["k2"] = _FakeGenaiClient(decisions_handler=None)
    with pytest.raises(RuntimeError, match=r"client\.decisions"):
        await no_decisions_closed.check_sheet(make_image_bytes(fmt="PNG"))

    rate_limited_open = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        enable_gatekeeper=True,
        gatekeeper_fail_open=True,
    )
    rate_limited_open._clients["k1"] = _FakeGenaiClient(
        decisions_handler=lambda **_kw: (_ for _ in ()).throw(
            ClientError(429, {"error": {"message": "rate limit"}})
        )
    )
    limited_dec = await rate_limited_open.check_sheet(make_image_bytes(fmt="PNG"))
    assert limited_dec.warning == "gatekeeper_unavailable:ClientError"
    assert rate_limited_open.key_pool._key_cooldown_until["k1"] > time.monotonic()

    unreadable_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        enable_gatekeeper=True,
    )
    unreadable_client._clients["k1"] = _FakeGenaiClient(
        decisions_handler=lambda **_kw: SimpleNamespace(
            answers={
                "is_auction_sheet": SimpleNamespace(noul=0.95),
                "is_readable": SimpleNamespace(noul=0.10),
                "layout_complexity": SimpleNamespace(choice="complex_or_handwritten"),
            }
        )
    )
    rejected = await unreadable_client.check_sheet(make_image_bytes(fmt="PNG"))
    assert rejected.is_auction_sheet is True
    assert rejected.is_readable is False
    assert rejected.is_accepted is False


@pytest.mark.asyncio
async def test_extract_sheet_complex_parts_valueerror_failover_403_and_deadline() -> None:
    # 1) COMPLEX_OR_HANDWRITTEN sends 11 contents (prompt + labeled full image + 4 labeled crops)
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

    client._clients["k1"] = _FakeGenaiClient(models_handler=_failover_handler)
    entity = await client.extract_sheet(
        make_sliced_sheet(), LayoutComplexity.COMPLEX_OR_HANDWRITTEN
    )
    assert entity.model_used == "m-valid"
    assert seen_contents_len == [11, 11]
    assert client._model_cooldown_until["m-empty"] > time.monotonic()

    # 2) All models raising ValueError (bad JSON) -> RuntimeError (503 path), not ValueError (400)
    bad_json_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        flash_model="m1",
        fallback_models=["m2"],
        hedge_delay_seconds=5.0,
        request_deadline_seconds=5.0,
    )
    bad_json_client._clients["k1"] = _FakeGenaiClient(
        models_handler=lambda **_kw: SimpleNamespace(text="{not-json")
    )
    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        await bad_json_client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)

    # 3) Non-retryable ClientError (403) raises immediately without trying fallback model
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

    forbidden_client._clients["k1"] = _FakeGenaiClient(models_handler=_forbidden)
    with pytest.raises(ClientError):
        await forbidden_client.extract_sheet(make_sliced_sheet(), LayoutComplexity.CLEAN_DIGITAL)
    assert called_models == ["m1"]

    # 4) Request deadline exceeded raises TimeoutError
    timeout_client = AsyncGeminiVisionClient(
        key_pool=GeminiKeyPool(["k1"], rpm_limit=4),
        flash_model="m1",
        fallback_models=[],
        request_deadline_seconds=0.05,
    )

    def _very_slow(**_kw):
        time.sleep(0.25)
        return SimpleNamespace(text=_valid_extraction_json())

    timeout_client._clients["k1"] = _FakeGenaiClient(models_handler=_very_slow)
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

    # 429 on k1 must cool down key k1, NOT mark m1 on shared vision._model_cooldown_until
    def _429_then_whitespace(key: str):
        def _inner(**_kw):
            if key == "k1":
                raise ClientError(429, {"error": {"message": "Too many requests"}})
            return SimpleNamespace(text=json.dumps({"frame_id": "   ", "confidence": "low"}))

        return _inner

    vision._clients["k1"] = _FakeGenaiClient(models_handler=_429_then_whitespace("k1"))
    vision._clients["k2"] = _FakeGenaiClient(models_handler=_429_then_whitespace("k2"))

    res = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert "m1" not in vision._model_cooldown_until
    assert pool._key_cooldown_until["k1"] > time.monotonic()
    assert res.frame_id is None
    assert res.raw is None

    # Unreadable/null frame_id is not cached permanently on disk
    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert cache_files == []

    # Corrupted disk cache file falls back cleanly to Gemini instead of crashing
    cache_path = chassis_client._cache_path(img)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{corrupt", encoding="utf-8")

    vision._clients["k2"] = _FakeGenaiClient(
        models_handler=lambda **_kw: SimpleNamespace(
            text=json.dumps({"frame_id": "NRE210-1234567", "confidence": "high"})
        )
    )
    recovered = await chassis_client.read_chassis_number(img, mime_type="image/jpeg")
    assert recovered.frame_id == "NRE210-1234567"
    assert recovered.cached is False
