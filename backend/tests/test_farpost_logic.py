"""Database-independent unit tests for Farpost/Drom HTTP helpers and repair service logic."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from apps.core.enums import WorkType
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.farpost import service as farpost_service
from apps.lots.integrations.farpost.client import FarpostClient, ParseResult, PartOffer
from apps.lots.integrations.farpost.service import (
    _body_code,
    _search_model,
    _select_best_offer,
    _work_label,
    estimate_repair,
)
from apps.lots.integrations.http_client import ProxyRotator, redact_proxy_url


def test_proxy_rotator_cycles_and_redacts_credentials():
    rotator = ProxyRotator(["http://u1:s1@proxy1.local:8080", "http://proxy2.local:3128"])
    assert len(rotator) == 2
    assert rotator.next_proxy() == "http://u1:s1@proxy1.local:8080"
    assert rotator.next_proxy() == "http://proxy2.local:3128"
    assert rotator.next_proxy() == "http://u1:s1@proxy1.local:8080"
    assert redact_proxy_url("http://u1:s1@proxy1.local:8080") == "http://proxy1.local:8080"
    assert redact_proxy_url(None) is None


def test_body_code_ignores_17_char_vin_and_uses_model_code():
    benz = SimpleNamespace(
        frame_id="WDD2050421F123456",
        chassis_number="",
        model_code="W205",
    )
    assert _body_code(benz) == "W205"

    euro_without_model_code = SimpleNamespace(
        frame_id="WBA3A510X0F123456",
        chassis_number="",
        model_code="",
    )
    assert _body_code(euro_without_model_code) == ""

    jdm = SimpleNamespace(frame_id="ZRE212-1002345", chassis_number="", model_code="3BA-ZRE212W")
    assert _body_code(jdm) == "ZRE212"


def test_search_model_strips_noisy_trims_only():
    assert _search_model("Stepwgn Spada e:HEV") == "Stepwgn"
    assert _search_model("Freed Crosstar Hybrid 4WD") == "Freed"
    assert _search_model("Impreza G4 2WD") == "Impreza"
    assert _search_model("Corolla Touring") == "Corolla Touring"


def test_select_best_offer_optimizes_part_plus_paint_cost():
    plain = PartOffer("1", "https://www.farpost.ru/1", "Дверь Toyota Corolla NRE210", 8000, False)
    colored_worth_it = PartOffer(
        "2",
        "https://www.farpost.ru/2",
        "Дверь Toyota Corolla NRE210",
        15000,
        False,
        snippet="Цвет 070 перламутр",
    )
    chosen, matched = _select_best_offer(
        [plain, colored_worth_it],
        paint_code="070",
        paint_cost_rub=10000,
        panel="front_left_door",
        stale=False,
    )
    assert chosen == colored_worth_it
    assert matched is True

    colored_too_expensive = PartOffer(
        "3",
        "https://www.farpost.ru/3",
        "Дверь Toyota Corolla NRE210 цвет 070",
        25000,
        False,
    )
    chosen_plain, matched_plain = _select_best_offer(
        [plain, colored_too_expensive],
        paint_code="070",
        paint_cost_rub=10000,
        panel="front_left_door",
        stale=False,
    )
    assert chosen_plain == plain
    assert matched_plain is False


def test_work_label_distinguishes_sto_norm_from_matrix_bodywork():
    assert _work_label(WorkType.MOUNT_DISMOUNT, "Передний бампер", "front_bumper").endswith(
        "(норматив СТО)"
    )
    assert _work_label(WorkType.PAINT, "Передний бампер", "front_bumper").endswith("(норматив СТО)")
    assert _work_label(WorkType.BODYWORK, "Крыша", "roof").endswith("(расчёт по матрице)")
    assert _work_label(WorkType.PAINT, "Заднее левое крыло", "rear_left_quarter").endswith(
        "(расчёт по матрице)"
    )


def test_search_cached_skips_negative_cache_when_exact_feed_exists(monkeypatch):
    monkeypatch.setattr(farpost_service, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)

    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "filter", lambda **_kw: filter_mock)
    update_mock = MagicMock()
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "update_or_create", update_mock)

    client = FarpostClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="")))
    monkeypatch.setattr(
        client,
        "search_with_metadata",
        lambda *_a, **_kw: ParseResult(offers=[], exact_feed_count=116),
    )

    offers, stale, reason = farpost_service._search_cached_with_reason(
        client,
        farpost_service.PartCriteria(
            "Subaru", "Impreza", "GP2", "front_left_fender", "крыло", "левое", "переднее", ""
        ),
        deadline=time.monotonic() + 10,
    )
    assert offers == []
    assert not stale
    assert reason == "not_found"
    update_mock.assert_not_called()


def test_estimate_repair_reports_specific_fallback_subtitles(monkeypatch):
    lot_no_body = SimpleNamespace(
        make="Toyota",
        model="Tank",
        frame_id="",
        chassis_number="",
        model_code="",
        paint_code="",
        defects=SimpleNamespace(
            all=lambda: [
                SimpleNamespace(
                    panel_id="front_bumper",
                    raw_code="X",
                    defect_types=["X"],
                    severity=None,
                )
            ]
        ),
    )
    res_missing = estimate_repair(lot_no_body, client=MagicMock())
    assert "не определён код кузова" in (res_missing.parts[0].subtitle_ru or "")

    lot_with_body = SimpleNamespace(
        make="Toyota",
        model="Corolla",
        frame_id="NRE210-001",
        chassis_number="",
        model_code="3BA-NRE210",
        paint_code="070",
        defects=lot_no_body.defects,
    )
    monkeypatch.setattr(
        farpost_service,
        "_search_cached_with_reason",
        lambda *_a, **_kw: ([], True, "rate_limited"),
    )
    res_limited = estimate_repair(lot_with_body, client=MagicMock())
    assert "ограничил выдачу" in (res_limited.parts[0].subtitle_ru or "")


def test_drom_http_client_retries_across_configured_proxies():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return httpx.Response(200, text="<html>ok</html>")

    client = DromHttpClient(
        max_retries=0,
        retry_backoff_sec=0.0,
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        transport=httpx.MockTransport(handler),
    )
    assert client.get_html("https://auto.drom.ru/toyota/corolla/") == "<html>ok</html>"
    assert calls == 2
