"""Database-independent unit tests for Farpost/Drom service logic and settings wiring."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

import httpx
import pytest

from apps.core.enums import WorkType
from apps.lots.integrations.drom import schema_sync
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.schemas import DromBlockedError
from apps.lots.integrations.drom.service import DromMarketService
from apps.lots.integrations.farpost import service as farpost_service
from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostRateLimitedError,
    ParseResult,
    PartCriteria,
    PartOffer,
)
from apps.lots.integrations.farpost.service import (
    _FALLBACK_SUBTITLES,
    _body_code,
    _search_model,
    _select_best_offer,
    _work_label,
    estimate_repair,
)
from apps.lots.integrations.http_client import clear_local_throttle_state, reset_shared_proxy_pools
from config.settings.config import AppSettings


@pytest.fixture(autouse=True)
def _reset_shared_scraper_state():
    reset_shared_proxy_pools()
    clear_local_throttle_state()
    yield
    reset_shared_proxy_pools()
    clear_local_throttle_state()


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


def test_body_code_preserves_two_letter_jdm_suffixes():
    assert (
        _body_code(SimpleNamespace(frame_id="KE2FW-100234", chassis_number="", model_code=""))
        == "KE2FW"
    )
    assert (
        _body_code(SimpleNamespace(frame_id="", chassis_number="", model_code="LDA-BM5FS"))
        == "BM5FS"
    )


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


def test_select_best_offer_never_color_matches_windshield():
    glass = PartOffer(
        "1", "https://www.farpost.ru/1", "Стекло лобовое Honda Fit GE6 070", 9000, False
    )
    chosen, matched = _select_best_offer(
        [glass],
        paint_code="070",
        paint_cost_rub=10000,
        panel="windshield",
        stale=False,
    )
    assert chosen == glass
    assert matched is False


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
        PartCriteria(
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


def test_mock_spec_farpost_client_and_frontend_subtitles(monkeypatch):
    monkeypatch.setattr(farpost_service, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)
    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "filter", lambda **_kw: filter_mock)
    upsert_mock = MagicMock()
    monkeypatch.setattr(farpost_service, "upsert_external_cache", upsert_mock)

    mock_client = MagicMock(spec=FarpostClient)
    mock_client.search.return_value = [
        PartOffer(
            "1",
            "https://www.farpost.ru/1",
            "Дверь передняя левая Toyota Corolla NRE210",
            8000,
            False,
        )
    ]
    offers, stale, reason = farpost_service._search_cached_with_reason(
        mock_client,
        PartCriteria(
            "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
        ),
        deadline=time.monotonic() + 10,
    )
    assert len(offers) == 1
    assert not stale
    assert reason == ""
    mock_client.search.assert_called_once()
    mock_client.search_with_metadata.assert_not_called()

    assert "временно недоступен" in _FALLBACK_SUBTITLES["fetch_error"]
    assert "ограничил выдачу" in _FALLBACK_SUBTITLES["rate_limited"]
    assert "не определён код кузова" in _FALLBACK_SUBTITLES["missing_identity"]
    assert "нет подходящих предложений" in _FALLBACK_SUBTITLES["not_found"]


def test_drom_http_client_retries_and_single_proxy_blocked_raises_immediately():
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

    single_calls = 0

    def single_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal single_calls
        single_calls += 1
        return httpx.Response(429)

    single_client = DromHttpClient(
        max_retries=2,
        retry_backoff_sec=0.0,
        proxy_urls=["http://p1:8080"],
        transport=httpx.MockTransport(single_handler),
    )
    with pytest.raises(DromBlockedError):
        single_client.get_html("https://auto.drom.ru/toyota/corolla/")
    assert single_calls == 1


def test_schema_sync_imports_and_decodes_cp1251():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content="<html><title>Тойота</title></html>".encode("cp1251"),
            headers={"content-type": "text/html; charset=windows-1251"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        status, _final_url, html = schema_sync._fetch_text(client, "https://auto.drom.ru/all/")
    assert status == 200
    assert "Тойота" in html
    assert "User-Agent" in schema_sync._SCHEMA_SYNC_HEADERS


def test_app_settings_shared_scraper_configuration():
    shared = AppSettings(
        _env_file=None,
        SCRAPER_PROXY_URLS="http://u:p@shared1:8080, http://shared2:8080",
        SCRAPER_PROXY_BAN_SEC=180,
        SCRAPER_TIMEOUT_SEC=14.0,
        SCRAPER_REQUEST_INTERVAL_SEC=2.5,
        SCRAPER_REQUEST_JITTER_SEC=0.7,
        FARPOST_BUDGET_SEC=40.0,
        FARPOST_COOLDOWN_SEC=90,
        FARPOST_CACHE_TTL_HOURS=12,
    )
    assert shared.SCRAPER_PROXY_URLS == ["http://u:p@shared1:8080", "http://shared2:8080"]
    assert shared.SCRAPER_PROXY_BAN_SEC == 180
    assert shared.SCRAPER_TIMEOUT_SEC == 14.0
    assert shared.SCRAPER_REQUEST_INTERVAL_SEC == 2.5
    assert shared.SCRAPER_REQUEST_JITTER_SEC == 0.7
    assert shared.FARPOST_BUDGET_SEC == 40.0
    assert shared.FARPOST_COOLDOWN_SEC == 90
    assert shared.FARPOST_CACHE_TTL_HOURS == 12
    assert not hasattr(AppSettings, "FARPOST_PROXY_URLS")
    assert not hasattr(AppSettings, "DROM_PROXY_URLS")
    assert not hasattr(AppSettings, "HTTP_CLIENT_TIMEOUT_SEC")


def test_farpost_and_drom_rotate_and_quarantine_proxies_on_blocks_and_transport_errors(monkeypatch):
    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: None)
    fp_attempts = 0

    def fp_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal fp_attempts
        fp_attempts += 1
        if fp_attempts == 1:
            raise httpx.ConnectTimeout("proxy 1 hung")
        return httpx.Response(
            200,
            text="""<html><title>Запчасти</title>
            <input name="goodPresentState" value="present" checked>
            <div class="bull-item" data-good-id="10">
              <a data-role="bulletin-link" href="/vladivostok/zapchasti/10.html">
                Дверь передняя левая Toyota Corolla NRE210
              </a>
              <div class="price-block__final-price"><div data-role="price">12 000₽</div></div>
            </div></html>""",
        )

    fp_client = FarpostClient(
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        proxy_ban_sec=60.0,
        transport=httpx.MockTransport(fp_handler),
    )
    criteria = PartCriteria(
        "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
    )
    with fp_client:
        offers = fp_client.search(criteria, deadline=time.monotonic() + 20)
        assert len(offers) == 1
        assert fp_attempts == 2
        assert fp_client._proxy_rotator is not None
        assert fp_client._proxy_rotator.is_quarantined("http://p1:8080", domain="www.farpost.ru")
        # Subsequent call skips quarantined p1 and immediately uses p2.
        assert fp_client._proxy_rotator.next_proxy(domain="www.farpost.ru") == "http://p2:8080"

    drom_attempts = 0

    def drom_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal drom_attempts
        drom_attempts += 1
        if drom_attempts == 1:
            return httpx.Response(403)
        return httpx.Response(200, text="<html>ok</html>")

    drom_client = DromHttpClient(
        max_retries=0,
        retry_backoff_sec=0.0,
        proxy_ban_sec=60.0,
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        transport=httpx.MockTransport(drom_handler),
    )
    assert drom_client.get_html("https://auto.drom.ru/toyota/corolla/") == "<html>ok</html>"
    assert drom_client._proxy_rotator is not None
    assert drom_client._proxy_rotator.is_quarantined("http://p1:8080", domain="drom.ru")


def test_shared_proxy_pool_and_http_200_captcha_5xx_rotation(monkeypatch):
    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: None)

    valid_farpost_html = """<html><title>Запчасти</title>
    <input name="goodPresentState" value="present" checked>
    <div class="bull-item" data-good-id="10">
      <a data-role="bulletin-link" href="/vladivostok/zapchasti/10.html">
        Дверь передняя левая Toyota Corolla NRE210
      </a>
      <div class="price-block__final-price"><div data-role="price">12 000₽</div></div>
    </div></html>"""

    criteria = PartCriteria(
        "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
    )

    # Farpost rotates on HTTP 200 CAPTCHA and shares quarantine across client instances.
    fp_calls = 0

    def fp_captcha_then_ok(_request: httpx.Request) -> httpx.Response:
        nonlocal fp_calls
        fp_calls += 1
        if fp_calls == 1:
            return httpx.Response(200, text="<html><title>Вы не робот</title></html>")
        return httpx.Response(200, text=valid_farpost_html)

    proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
    c1 = FarpostClient(
        proxy_urls=proxies,
        proxy_ban_sec=60.0,
        transport=httpx.MockTransport(fp_captcha_then_ok),
    )
    with c1:
        assert len(c1.search(criteria, deadline=time.monotonic() + 20)) == 1
    assert fp_calls == 2
    assert c1._proxy_rotator is not None
    assert c1._proxy_rotator.is_quarantined("http://p1:8080", domain="www.farpost.ru")

    # A new client instance (next lot) reuses the shared pool and sees p1 is still quarantined.
    c2 = FarpostClient(proxy_urls=proxies, proxy_ban_sec=60.0)
    assert c2._proxy_rotator is c1._proxy_rotator
    assert c2._proxy_rotator.is_quarantined("http://p1:8080", domain="farpost.ru")

    # Farpost rotates on 502 Bad Gateway too.
    fp_502_calls = 0

    def fp_502_then_ok(_request: httpx.Request) -> httpx.Response:
        nonlocal fp_502_calls
        fp_502_calls += 1
        if fp_502_calls == 1:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(200, text=valid_farpost_html)

    c3 = FarpostClient(
        proxy_urls=proxies,
        proxy_ban_sec=60.0,
        transport=httpx.MockTransport(fp_502_then_ok),
    )
    with c3:
        assert len(c3.search(criteria, deadline=time.monotonic() + 20)) == 1
    assert fp_502_calls == 2
    assert c3._proxy_rotator.is_quarantined("http://p3:8080", domain="farpost.ru")

    # Drom rotates on HTTP 200 SmartCaptcha/Qrator HTML and quarantines the offending proxy.
    drom_calls = 0

    def drom_captcha_then_ok(_request: httpx.Request) -> httpx.Response:
        nonlocal drom_calls
        drom_calls += 1
        if drom_calls == 1:
            return httpx.Response(200, text="<html><body>Qrator SmartCaptcha</body></html>")
        return httpx.Response(200, text="<html>ok</html>")

    drom_client = DromHttpClient(
        max_retries=0,
        retry_backoff_sec=0.0,
        proxy_ban_sec=60.0,
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        transport=httpx.MockTransport(drom_captcha_then_ok),
    )
    with drom_client:
        assert drom_client.get_html("https://auto.drom.ru/toyota/corolla/") == "<html>ok</html>"
    assert drom_calls == 2
    assert drom_client._proxy_rotator is not None
    assert drom_client._proxy_rotator.is_quarantined("http://p1:8080", domain="drom.ru")


def test_farpost_client_marks_blocked_proxy_once_per_429_failure(monkeypatch):
    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: None)
    client = FarpostClient(
        proxy_urls=["http://p1:8080"],
        proxy_ban_sec=60.0,
        transport=httpx.MockTransport(lambda _r: httpx.Response(429)),
    )
    mark_calls = 0
    original = client._proxy_rotator.mark_blocked

    def counting_mark_blocked(*args, **kwargs):
        nonlocal mark_calls
        mark_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(client._proxy_rotator, "mark_blocked", counting_mark_blocked)
    criteria = PartCriteria(
        "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
    )
    with pytest.raises(FarpostRateLimitedError):
        client.search(criteria, deadline=time.monotonic() + 20)
    assert mark_calls == 1


def test_services_read_shared_scraper_settings(monkeypatch):
    fake_settings = AppSettings(
        _env_file=None,
        SCRAPER_PROXY_URLS=["http://shared-proxy:8080"],
        SCRAPER_PROXY_BAN_SEC=95,
        SCRAPER_TIMEOUT_SEC=13.5,
        SCRAPER_REQUEST_INTERVAL_SEC=1.8,
        SCRAPER_REQUEST_JITTER_SEC=0.3,
    )
    monkeypatch.setattr("apps.lots.integrations.drom.service.get_settings", lambda: fake_settings)
    monkeypatch.setattr(
        "apps.lots.integrations.farpost.service.get_settings", lambda: fake_settings
    )

    drom_svc = DromMarketService()
    assert drom_svc._client._timeout_sec == 13.5
    assert drom_svc._client._request_interval_sec == 1.8
    assert drom_svc._client._request_jitter_sec == 0.3
    assert drom_svc._client._proxy_ban_sec == 95.0
    assert drom_svc._client._proxy_rotator is not None
    assert drom_svc._client._proxy_rotator.next_proxy() == "http://shared-proxy:8080"

    captured_fp_kwargs: dict[str, object] = {}

    class DummyFarpostClient:
        def __init__(self, **kwargs):
            captured_fp_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return None

    monkeypatch.setattr("apps.lots.integrations.farpost.service.FarpostClient", DummyFarpostClient)
    dummy_lot = SimpleNamespace(
        make="Toyota",
        model="Corolla",
        model_code="NRE210",
        frame_id="",
        chassis_number="",
        paint_code="",
        defects=SimpleNamespace(all=lambda: []),
    )
    estimate_repair(dummy_lot)
    assert captured_fp_kwargs == {
        "timeout_sec": 13.5,
        "request_interval_sec": 1.8,
        "request_jitter_sec": 0.3,
        "proxy_ban_sec": 95,
        "proxy_urls": ["http://shared-proxy:8080"],
        "captcha_solver": ANY,
    }


def test_estimate_repair_forwards_captcha_and_ocr_settings(monkeypatch):
    from apps.lots.integrations.captcha import FarpostCaptchaSolver, TesseractImageCaptchaSolver

    fake_settings = AppSettings(
        _env_file=None,
        FARPOST_CAPTCHA_MAX_ATTEMPTS=4,
        FARPOST_CAPTCHA_SOLVE_BUDGET_SEC=12.5,
        FARPOST_CAPTCHA_MAX_WORKERS=3,
        FARPOST_CAPTCHA_OCR_ENABLED=True,
        FARPOST_CAPTCHA_OCR_COMMAND="/opt/bin/tesseract",
        SCRAPER_TIMEOUT_SEC=11.0,
    )
    monkeypatch.setattr(
        "apps.lots.integrations.farpost.service.get_settings", lambda: fake_settings
    )
    captured_kwargs: dict[str, object] = {}

    class CapturingFarpostClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return None

    monkeypatch.setattr(
        "apps.lots.integrations.farpost.service.FarpostClient", CapturingFarpostClient
    )
    dummy_lot = SimpleNamespace(
        make="Toyota",
        model="Corolla",
        model_code="NRE210",
        frame_id="",
        chassis_number="",
        paint_code="",
        defects=SimpleNamespace(all=lambda: []),
    )
    estimate_repair(dummy_lot)

    solver = captured_kwargs["captcha_solver"]
    assert isinstance(solver, FarpostCaptchaSolver)
    assert solver.max_attempts == 4
    assert solver.solve_budget_sec == 12.5
    assert solver.max_workers == 3
    assert solver.request_timeout_sec == 11.0
    assert isinstance(solver.image_solver, TesseractImageCaptchaSolver)
    assert solver.image_solver.command == "/opt/bin/tesseract"


def test_farpost_image_captcha_failure_does_not_activate_global_cooldown(monkeypatch):
    farpost_service.reset_farpost_cooldown()
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)
    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "filter", lambda **_kw: filter_mock)

    def image_challenge_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/vladivostok/zapchasti/":
            return httpx.Response(302, headers={"Location": "https://www.farpost.ru/verify?u=test"})
        return httpx.Response(
            200,
            text=(
                '<html><div class="cap4"><img src="?i=tok">'
                '<form action="/verify"><input name="s" value="tok"></form></div></html>'
            ),
        )

    client = FarpostClient(transport=httpx.MockTransport(image_challenge_handler))
    offers, stale, reason = farpost_service._search_cached_with_reason(
        client,
        PartCriteria(
            "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
        ),
        deadline=time.monotonic() + 20,
    )
    assert offers == []
    assert stale is True
    assert reason == "fetch_error"
    assert farpost_service._is_rate_limit_cooldown_active() is False


def test_part_source_kind_matches_frontend_labels():
    from apps.core.enums import PartSourceKind

    vue_path = (
        Path(__file__).resolve().parents[2]
        / "frontend/src/components/lots/detail/print/LotPrintPageTechEconomics.vue"
    )
    if not vue_path.is_file():
        pytest.skip("Frontend sources are not mounted inside standalone backend container")
    vue_text = vue_path.read_text(encoding="utf-8")
    for kind in PartSourceKind:
        assert kind.value in vue_text
