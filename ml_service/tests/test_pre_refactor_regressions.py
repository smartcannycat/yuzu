"""Regression tests for pre-refactor ML service fixes."""

from __future__ import annotations

import time

import pytest

from ml_service.domains.entities import RawRiskFlagsEntity
from ml_service.domains.enums import AuctionHouse, FrameIdConfidence
from ml_service.factories.normalizers import synthesize_frame_id
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.key_pool import GeminiKeyPool
from tests.conftest import make_raw_extraction


def test_synthesize_frame_id_supports_three_part_and_short_codes() -> None:
    assert synthesize_frame_id("3BA-NRE210W-AWXNB", "2005418") == (
        "NRE210-2005418",
        FrameIdConfidence.SYNTHESIZED,
    )
    assert synthesize_frame_id("GB5-100", "1025108") == (
        "GB5-1025108",
        FrameIdConfidence.SYNTHESIZED,
    )


def test_sheet_factory_auction_house_fallback_from_other_and_color_changed_ru() -> None:
    raw = make_raw_extraction(
        auction_house="USS",
        auction_house_raw="Неизвестный зал",
        make_en="Toyota",
        model_en="Vitz",
        color_changed_ru="Перекрашен из белого в чёрный",
        risk_flags=RawRiskFlagsEntity(
            is_flooded=False,
            airbag_deployed=False,
            hail_damage=False,
            underbody_rust=False,
            underbody_corrosion=False,
            core_support_repair=False,
            pillar_or_frame_repair=False,
            color_changed=True,
            windshield_damage=False,
        ),
    )
    assert raw.to_raw_dict()["color_changed_ru"] == "Перекрашен из белого в чёрный"

    result = SheetFactory().build_result(
        raw,
        processing_ms=10,
        mode_used="clean_digital",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="abc123",
    )
    assert result.sheet is not None
    assert result.sheet.auction_house == AuctionHouse.USS.value
    assert "Перекрашен из белого в чёрный" in result.sheet.extra_ru


@pytest.mark.asyncio
async def test_gemini_key_pool_sliding_window_rpm_throttling() -> None:
    pool = GeminiKeyPool(["k1"], rpm_limit=2, rpm_window_seconds=0.12)
    t0 = time.monotonic()
    for _ in range(3):
        async with pool.acquire():
            pass
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.10
