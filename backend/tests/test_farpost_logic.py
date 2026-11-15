"""Database-independent unit tests for Farpost/Drom HTTP helpers and repair service logic."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

from apps.core.enums import WorkType
from apps.lots.integrations.drom import schema_sync
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.schemas import DromBlockedError
from apps.lots.integrations.farpost import service as farpost_service
from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
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
from apps.lots.integrations.http_client import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ProxyPool,
    ProxyRotator,
    ResilientHttpSession,
    normalize_proxy_urls,
    redact_proxy_url,
    wait_for_request_slot,
)
from config.settings.config import AppSettings


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


def test_redact_proxy_url_and_transport_error_scrub_credentials(monkeypatch):
    assert redact_proxy_url("http://user:s3cr3t@127.0.0.1:abc") == "<proxy>"
    assert redact_proxy_url("http://user:p[ss@proxy.local:8080") == "<proxy>"

    class FailingCurlSession:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url, **_kwargs):
            raise CurlRequestsError(
                "Unsupported proxy syntax in 'http://myuser:topsecret@127.0.0.1:abc'"
            )

        def close(self):
            return None

    monkeypatch.setattr(
        "apps.lots.integrations.http_client.curl_requests.Session", FailingCurlSession
    )
    session = ResilientHttpSession(
        proxy_rotator=ProxyRotator(["http://myuser:topsecret@127.0.0.1:abc"])
    )
    with pytest.raises(HttpTransportError) as exc_info:
        session.get("https://www.farpost.ru/")
    assert "topsecret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_http_fetch_response_json_supports_bom_and_cp1251():
    bom_resp = HttpFetchResponse(200, "https://drom.ru", {}, b'\xef\xbb\xbf{"ok": true}')
    assert bom_resp.json() == {"ok": True}

    cp1251_resp = HttpFetchResponse(
        200,
        "https://drom.ru",
        {"content-type": "application/json; charset=windows-1251"},
        '{"name": "Тойота"}'.encode("cp1251"),
    )
    assert cp1251_resp.json() == {"name": "Тойота"}


def test_single_proxy_drom_blocked_raises_immediately():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    client = DromHttpClient(
        max_retries=2,
        retry_backoff_sec=0.0,
        proxy_urls=["http://p1:8080"],
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(DromBlockedError):
        client.get_html("https://auto.drom.ru/toyota/corolla/")
    assert calls == 1


def test_body_code_preserves_two_letter_jdm_suffixes():
    assert (
        _body_code(SimpleNamespace(frame_id="KE2FW-100234", chassis_number="", model_code=""))
        == "KE2FW"
    )
    assert (
        _body_code(SimpleNamespace(frame_id="", chassis_number="", model_code="LDA-BM5FS"))
        == "BM5FS"
    )


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


def test_mock_spec_farpost_client_and_frontend_subtitles(monkeypatch):
    monkeypatch.setattr(farpost_service, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)
    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "filter", lambda **_kw: filter_mock)
    update_mock = MagicMock()
    monkeypatch.setattr(farpost_service.ExternalCache.objects, "update_or_create", update_mock)

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
        farpost_service.PartCriteria(
            "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", ""
        ),
        deadline=time.monotonic() + 10,
    )
    assert len(offers) == 1
    assert not stale
    assert reason == ""
    mock_client.search.assert_called_once()
    mock_client.search_with_metadata.assert_not_called()

    vue_path = (
        Path(__file__).resolve().parents[2]
        / "frontend/src/components/lots/detail/print/LotPrintPageTechEconomics.vue"
    )
    vue_text = vue_path.read_text(encoding="utf-8")
    assert "временно недоступен" in vue_text
    assert "временно недоступен" in _FALLBACK_SUBTITLES["fetch_error"]
    assert "ограничил выдачу" in vue_text
    assert "ограничил выдачу" in _FALLBACK_SUBTITLES["rate_limited"]
    assert "не определён код кузова" in vue_text
    assert "не определён код кузова" in _FALLBACK_SUBTITLES["missing_identity"]
    assert "нет подходящих предложений" in vue_text
    assert "нет подходящих предложений" in vue_text
    assert "нет подходящих предложений" in _FALLBACK_SUBTITLES["not_found"]


def test_proxy_pool_isolates_quarantine_by_domain_and_falls_back_gracefully():
    assert normalize_proxy_urls(
        ["http://p1:8080", ""],
        ["http://p1:8080", " http://p2:8080 "],
    ) == ("http://p1:8080", "http://p2:8080")

    pool = ProxyPool(
        ["http://u:secret@p1:8080", "http://u:secret@p2:8080"],
        ban_cooldown_sec=60.0,
        use_redis=False,
    )
    first = pool.next_proxy(domain="www.farpost.ru")
    assert first == "http://u:secret@p1:8080"
    pool.mark_blocked(first, domain="www.farpost.ru", cooldown_sec=60.0)

    # Quarantined for farpost.ru, so subsequent farpost calls skip p1...
    assert pool.next_proxy(domain="www.farpost.ru") == "http://u:secret@p2:8080"
    assert pool.next_proxy(domain="www.farpost.ru") == "http://u:secret@p2:8080"
    # ...while drom.ru still treats p1 as healthy.
    assert pool.is_quarantined("http://u:secret@p1:8080", domain="www.farpost.ru") is True
    assert pool.is_quarantined("http://u:secret@p1:8080", domain="drom.ru") is False
    assert pool.next_proxy(domain="drom.ru") == "http://u:secret@p1:8080"

    # When every proxy is quarantined, next_proxy falls back to the earliest-expiring one.
    pool.mark_blocked("http://u:secret@p2:8080", domain="www.farpost.ru", cooldown_sec=120.0)
    assert pool.next_proxy(domain="www.farpost.ru") == "http://u:secret@p1:8080"

    pool.clear_cooldown("http://u:secret@p1:8080", domain="www.farpost.ru")
    assert pool.is_quarantined("http://u:secret@p1:8080", domain="www.farpost.ru") is False


def test_proxy_pool_redis_quarantine_uses_hashed_keys_without_credentials(monkeypatch):
    stored: dict[str, str] = {}

    class FakeRedis:
        def mget(self, keys):
            return [stored.get(k) for k in keys]

        def set(self, key, value, ex=None):
            stored[key] = str(value)

        def delete(self, key):
            stored.pop(key, None)

    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: FakeRedis())

    pool_worker_a = ProxyPool(["http://user:topsecret@p1:8080", "http://user:topsecret@p2:8080"])
    pool_worker_b = ProxyPool(["http://user:topsecret@p1:8080", "http://user:topsecret@p2:8080"])
    pool_worker_a.mark_blocked("http://user:topsecret@p1:8080", domain="www.farpost.ru")

    assert stored
    assert all("topsecret" not in key for key in stored)
    assert pool_worker_b.next_proxy(domain="www.farpost.ru") == "http://user:topsecret@p2:8080"


def test_app_settings_merges_shared_scraper_defaults_and_preserves_overrides():
    shared = AppSettings(
        _env_file=None,
        SCRAPER_PROXY_URLS="http://u:p@shared1:8080, http://shared2:8080",
        SCRAPER_PROXY_BAN_SEC=180,
        SCRAPER_TIMEOUT_SEC=14.0,
        SCRAPER_REQUEST_INTERVAL_SEC=2.5,
        SCRAPER_REQUEST_JITTER_SEC=0.7,
        SCRAPER_COOLDOWN_SEC=90,
    )
    assert shared.HTTP_CLIENT_TIMEOUT_SEC == 14.0
    assert shared.FARPOST_TIMEOUT_SEC == 14.0
    assert shared.DROM_TIMEOUT_SEC == 14.0
    assert shared.FARPOST_REQUEST_INTERVAL_SEC == 2.5
    assert shared.DROM_REQUEST_INTERVAL_SEC == 2.5
    assert shared.FARPOST_REQUEST_JITTER_SEC == 0.7
    assert shared.DROM_REQUEST_JITTER_SEC == 0.7
    assert shared.FARPOST_COOLDOWN_SEC == 90
    assert shared.SCRAPER_PROXY_BAN_SEC == 180
    assert shared.proxy_urls_for("farpost") == ("http://u:p@shared1:8080", "http://shared2:8080")
    assert shared.proxy_urls_for("drom") == ("http://u:p@shared1:8080", "http://shared2:8080")

    overridden = AppSettings(
        _env_file=None,
        SCRAPER_PROXY_URLS=["http://shared1:8080", "http://shared2:8080"],
        FARPOST_PROXY_URLS=["http://dedicated-fp:8080", "http://shared1:8080"],
        SCRAPER_TIMEOUT_SEC=12.0,
        FARPOST_TIMEOUT_SEC=6.0,
    )
    assert overridden.proxy_urls_for("farpost") == (
        "http://dedicated-fp:8080",
        "http://shared1:8080",
        "http://shared2:8080",
    )
    assert overridden.proxy_urls_for("drom") == ("http://shared1:8080", "http://shared2:8080")
    assert overridden.FARPOST_TIMEOUT_SEC == 6.0
    assert overridden.DROM_TIMEOUT_SEC == 12.0


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


def test_wait_for_request_slot_raises_on_budget_exhausted(monkeypatch):
    monkeypatch.setattr(
        "apps.lots.integrations.http_client.acquire_distributed_interval_slot", lambda *_a: 5.0
    )
    with pytest.raises(HttpBudgetExhaustedError):
        wait_for_request_slot("yuzu:test:throttle", 1.0, deadline=time.monotonic() + 0.5)

    client = FarpostClient(
        request_interval_sec=1.0,
        transport=None,
    )
    with pytest.raises(FarpostFetchError, match="budget"):
        client._fetch_and_parse_page(
            PartCriteria("Toyota", "Corolla", "NRE210", "front_left_door", "дверь"),
            deadline=time.monotonic() + 0.5,
        )
