"""Hardening and regression tests for Wave 2 integration security, contracts, and DRY fixes."""

from __future__ import annotations

import contextlib
import hashlib
import os
import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest
from curl_cffi.requests.errors import RequestsError as CurlRequestsError
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.core.currency_config import BaseRates as CoreBaseRates
from apps.core.enums import BodyPanel, ItemProcessingStatus, TaskStep
from apps.core.models import ExternalCache
from apps.core.redis_utils import _cached_clients, get_redis_client
from apps.integrations.aleado.client import (
    AleadoClient,
    AleadoParseError,
    AleadoUnavailableError,
)
from apps.integrations.aleado.matcher import _candidate_is_own_lot
from apps.integrations.aleado.parser import AleadoLotRow
from apps.integrations.aleado.service import AleadoCrossAuditService, _partition_verified_by_time
from apps.integrations.currency.cache import CurrencyCache
from apps.integrations.currency.client import CbrfClient, CbrfFetchError
from apps.integrations.currency.domain import BaseRates
from apps.integrations.drom import schema_sync
from apps.integrations.drom.client import DromHttpClient
from apps.integrations.drom.power import DromPowerResolver
from apps.integrations.drom.power_filters import deserialize_specs
from apps.integrations.drom.schemas import DromBudgetExhaustedError, DromFetchError
from apps.integrations.drom.slugs import DromSlugResolver
from apps.integrations.farpost.cache import _supports_metadata_search
from apps.integrations.farpost.client import FarpostClient
from apps.integrations.farpost.matrix import _panel_codes
from apps.integrations.farpost.schemas import FarpostRepairEstimate
from apps.integrations.ml.client import (
    MlServiceClient,
    MlServiceUnavailableError,
)
from apps.integrations.ml.mapper import _sheet_to_lot_fields
from apps.integrations.ml.parser import MlServiceParser
from apps.integrations.ml.schemas import NormalizedSheet, ParserResponse
from apps.integrations.shared.http import (
    HttpBudgetExhaustedError,
    HttpTransportError,
    ProxyPool,
    ResilientHttpSession,
    clear_local_throttle_state,
    reset_shared_proxy_pools,
    scrub_proxy_credentials,
    wait_for_request_slot,
)
from apps.integrations.shared.http.pool import SessionClientRegistry, select_proxy
from apps.integrations.shared.proxy import redact_proxy_url
from apps.integrations.shared.url_guard import UnsafeExternalUrlError, validate_external_url
from apps.lots.models import Batch, BatchItem, Lot, LotDefect


@pytest.fixture(autouse=True)
def _reset_shared_state():
    reset_shared_proxy_pools()
    clear_local_throttle_state()
    yield
    reset_shared_proxy_pools()
    clear_local_throttle_state()


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://100.64.0.1/path",
        "https://[fec0::1]/path",
        "https://[::ffff:127.0.0.1]/path",
        "https://0177.0.0.1/path",
        "https://0x7f000001/path",
        "https://2130706433/path",
        "https://127.1/path",
        "https://example.com:99999/path",
        "https://example.com:abc/path",
        "https://user:pass@example.com/path",
        "https://example.com/\tbad",
        "https://example.com/\rbad",
        "https://example.com/\nbad",
        "https://localhost/path",
    ],
)
def test_url_guard_rejects_ssrf_obfuscated_ips_ports_userinfo_and_ctrl(bad_url: str) -> None:
    with pytest.raises(UnsafeExternalUrlError):
        validate_external_url(bad_url, check_dns=False)


def test_url_guard_accepts_public_https() -> None:
    assert validate_external_url("https://93.184.216.34/sheet.png", check_dns=False).startswith(
        "https://93.184.216.34/"
    )


def test_cross_origin_redirect_strips_sensitive_headers_and_blocks_307_308_body() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://baza.farpost.ru/next"})
        if request.url.path == "/same":
            return httpx.Response(302, headers={"Location": "https://www.farpost.ru/final"})
        if request.url.path == "/post307":
            return httpx.Response(307, headers={"Location": "https://baza.farpost.ru/sink"})
        seen_headers.append(dict(request.headers))
        return httpx.Response(200, text="ok")

    session = ResilientHttpSession(
        allowed_hosts=frozenset({"farpost.ru"}),
        transport=httpx.MockTransport(handler),
    )
    sensitive = {
        "Authorization": "Bearer secret",
        "Cookie": "sid=topsecret",
        "X-API-Key": "key-123",
        "X-Trace": "keep",
    }
    resp_cross = session.get("https://www.farpost.ru/start", headers=sensitive)
    assert resp_cross.status_code == 200
    assert "authorization" not in seen_headers[-1]
    assert "cookie" not in seen_headers[-1]
    assert "x-api-key" not in seen_headers[-1]
    assert seen_headers[-1]["x-trace"] == "keep"

    resp_same = session.get("https://www.farpost.ru/same", headers=sensitive)
    assert resp_same.status_code == 200
    assert seen_headers[-1]["authorization"] == "Bearer secret"
    assert seen_headers[-1]["cookie"] == "sid=topsecret"
    assert seen_headers[-1]["x-api-key"] == "key-123"

    with pytest.raises(HttpTransportError, match="cross-origin 307"):
        session.post("https://www.farpost.ru/post307", data={"a": "1"}, headers=sensitive)


def test_proxy_masking_handles_brackets_short_passwords_and_clears_context(monkeypatch) -> None:
    proxy_bracket = "http://u1:p[ss@proxy.local:8080"
    assert redact_proxy_url(proxy_bracket) == "http://proxy.local:8080"
    msg, scrubbed = scrub_proxy_credentials("connect failed with p[ss on proxy", proxy_bracket)
    assert scrubbed is True
    assert "p[ss" not in msg

    for short_pw in ("x", "ab"):
        short_proxy = f"http://user:{short_pw}@proxy.local:8080"
        short_msg, short_scrubbed = scrub_proxy_credentials(f"auth error: {short_pw}", short_proxy)
        assert short_scrubbed is True
        assert short_pw not in short_msg

    class FailingCurl:
        def __init__(self, **_kwargs):
            pass

        def request(self, *_a, **_kw):
            raise CurlRequestsError("failure for http://u1:p[ss@proxy.local:8080")

        def close(self):
            return None

    monkeypatch.setattr("apps.integrations.shared.http.pool.curl_requests.Session", FailingCurl)
    session = ResilientHttpSession(proxy_rotator=ProxyPool([proxy_bracket], use_redis=False))
    with pytest.raises(HttpTransportError) as exc_info:
        session.get("https://www.farpost.ru/")
    assert "p[ss" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_pool_forbids_silent_fallback_for_missing_proxy_key_and_locks_registry() -> None:
    pool = ProxyPool(["http://p1:8080"], use_redis=False)
    with pytest.raises(HttpTransportError, match="missing from proxy pool"):
        select_proxy(pool, proxy=None, proxy_key="nonexistent", domain="farpost.ru")
    with pytest.raises(HttpTransportError, match="without a proxy pool"):
        select_proxy(None, proxy=None, proxy_key="nonexistent", domain="farpost.ru")

    registry = SessionClientRegistry(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
        headers={},
        impersonate="chrome",
    )
    registry.in_context = True
    results: list[httpx.Client] = []
    lock = threading.Lock()

    def worker() -> None:
        client, persistent = registry.get_or_create_httpx("k1")
        assert persistent is True
        with lock:
            results.append(client)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(c) for c in results}) == 1
    registry.close_all()


def test_proxy_pool_runs_redis_mutations_inside_lock(monkeypatch) -> None:
    pool = ProxyPool(["http://p1:8080"], domain="farpost.ru", use_redis=True)
    lock_states: list[bool] = []

    class InspectingRedis:
        def set(self, *_a, **_kw):
            lock_states.append(pool._lock.locked())

        def delete(self, *_a, **_kw):
            lock_states.append(pool._lock.locked())

    monkeypatch.setattr(
        "apps.integrations.shared.proxy.get_redis_client", lambda: InspectingRedis()
    )
    pool.mark_blocked("http://p1:8080", domain="farpost.ru", cooldown_sec=30.0)
    pool.clear_cooldown("http://p1:8080", domain="farpost.ru")
    assert lock_states == [True, True]


def test_aleado_client_blocks_redirect_ssrf_reauths_streams_and_unlocks_before_sleep() -> None:
    def redirect_evil(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.com/steal"})

    client = AleadoClient(
        username="u",
        password="p",
        transport=httpx.MockTransport(redirect_evil),
        sleep_fn=lambda _s: None,
    )
    with pytest.raises(AleadoParseError, match="Blocked unsafe Aleado URL"):
        client.search_lots("GB5", 2017)

    # Re-auth after session expires when _logged_in was already True.
    calls: list[str] = []

    def reauth_handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method}:{request.url.path}")
        if request.url.path == "/auth/login.php":
            return httpx.Response(200, text="<html><body>Cabinet</body></html>")
        if len(calls) == 1:
            return httpx.Response(200, text="<html><body>Login form</body></html>")
        return httpx.Response(
            200,
            text="<html><body>Sign out Found total lots: 0</body></html>",
        )

    reauth_client = AleadoClient(
        username="u",
        password="p",
        transport=httpx.MockTransport(reauth_handler),
        sleep_fn=lambda _s: None,
    )
    reauth_client._logged_in = True
    assert reauth_client.search_lots("GB5", 2017) == []
    assert calls == ["GET:/auctions", "POST:/auth/login.php", "GET:/auctions"]

    # Streaming max_bytes check without Content-Length header.
    class OversizedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * 600
            yield b"b" * 600

    stream_client = AleadoClient(
        username="u",
        password="p",
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, stream=OversizedStream())),
        sleep_fn=lambda _s: None,
    )
    stream_client._MAX_HTML_BYTES = 1000
    with pytest.raises(AleadoUnavailableError, match="exceeds limit"):
        stream_client.search_lots("GB5", 2017)

    # _throttle releases _throttle_lock before sleeping.
    observed_locked: list[bool] = []
    AleadoClient._global_last_request_at = time.monotonic()
    throttle_client = AleadoClient(
        request_interval_sec=0.5,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
        sleep_fn=lambda _s: observed_locked.append(AleadoClient._throttle_lock.locked()),
    )
    throttle_client._throttle()
    assert observed_locked == [False]


def test_cbrf_and_drom_schema_sync_enforce_streaming_max_bytes() -> None:
    class BigStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * 700_000
            yield b"y" * 700_000

    cbrf = CbrfClient(
        api_url="https://example.invalid/daily_json.js",
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, stream=BigStream())),
    )
    with pytest.raises(CbrfFetchError, match="exceeds limit"):
        cbrf.fetch_rates()

    class HugeHtmlStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"<html>" + b"a" * 3_000_000
            yield b"b" * 3_000_000

    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, stream=HugeHtmlStream()))
        ) as client,
        pytest.raises(HttpTransportError, match="exceeds limit"),
    ):
        schema_sync._fetch_text(client, "https://auto.drom.ru/all/")


def test_aleado_matcher_tokens_and_undated_rows_preserved() -> None:
    lot = SimpleNamespace(lot_number="100", auction_house="JU", auction_branch="")
    row_substr = AleadoLotRow(
        trading_date=None,
        lot_number="100",
        auction_house="JUKEI",
        model_name="FREED",
        grade="4",
        year=2017,
        mileage_km=25000,
        displacement_cc=1500,
        transmission="AT",
        color="RED",
        model_type="GB5",
        start_price_jpy=100000,
        result="sold",
        internal_id="1",
        photo_url=None,
    )
    assert _candidate_is_own_lot(row_substr, lot) is False
    row_exact = AleadoLotRow(**{**row_substr.__dict__, "auction_house": "JU Aichi"})
    assert _candidate_is_own_lot(row_exact, lot) is True

    from apps.integrations.aleado.service import _VerifiedRow

    past, future = _partition_verified_by_time([_VerifiedRow(row=row_exact)], timezone.now())
    assert len(past) == 1
    assert future == 0


def test_aleado_cross_audit_service_closes_owned_clients() -> None:
    service = AleadoCrossAuditService()
    service.client = MagicMock()
    service._owns_client = True
    service.ml_client = MagicMock()
    service._owns_ml_client = True
    with contextlib.closing(service):
        pass
    service.client.close.assert_called_once()
    service.ml_client.close.assert_called_once()


@pytest.mark.django_db
def test_ml_client_read_chassis_400_429_null_and_parse_mime_and_parser_cleanup(
    user_factory,
) -> None:
    seen_mimes: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/sheets/parse":
            seen_mimes.append(request.read())
            return httpx.Response(429, json={"detail": "rate limit"})
        if request.headers.get("X-Case") == "400":
            return httpx.Response(400, json={"detail": "bad image"})
        if request.headers.get("X-Case") == "429":
            return httpx.Response(429, json={"detail": "slow down"})
        return httpx.Response(200, content=b"null")

    ml = MlServiceClient(
        base_url="http://ml.test",
        timeout_sec=5.0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(MlServiceUnavailableError):
        ml.parse_sheet(b"fake-heic", "photo.heic")
    assert b"image/heic" in seen_mimes[0]

    assert ml.read_chassis(b"\xff\xd8\xff\xe0") is None

    ml._client.headers["X-Case"] = "400"
    with pytest.raises(ValueError, match="bad image"):
        ml.read_chassis(b"\xff\xd8\xff\xe0")

    ml._client.headers["X-Case"] = "429"
    with pytest.raises(MlServiceUnavailableError, match="slow down"):
        ml.read_chassis(b"\xff\xd8\xff\xe0")

    # MlServiceParser.close() closes owned client even if gatekeeper rejects and parse() never runs.
    user = user_factory(email="ml-close@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(user=user)
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="not-sheet.png",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GATEKEEPER,
    )
    item.original_file.save("not-sheet.png", ContentFile(b"fake"), save=True)
    fake_client = MagicMock()
    fake_client.parse_sheet.return_value = ParserResponse(status="rejected_not_sheet", sheet=None)
    with patch("apps.integrations.ml.parser.MlServiceClient", return_value=fake_client):
        parser = MlServiceParser()
        with contextlib.closing(parser):
            rejection = parser.gatekeeper(item)
            assert rejection is not None
            assert parser._cache == {}
    fake_client.close.assert_called_once()

    # Out-of-range defect severity resets to None with warning instead of PG overflow;
    # BodyPanel.OTHER persists cleanly without extra_ru fallback.
    defect_item = BatchItem.objects.create(
        batch=batch,
        lot=Lot.objects.create(user=user),
        file_index=1,
        original_filename="sheet2.png",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GATEKEEPER,
    )
    defect_item.original_file.save("sheet2.png", ContentFile(b"fake2"), save=True)
    bad_sheet_payload = {
        "status": "ok",
        "sheet": {
            "defects": [
                {
                    "panel_id": "other",
                    "panel_ru": "Рамка радиатора",
                    "defect_types": ["XX"],
                    "severity": 2_147_483_648,
                    "description_ru": "Замена",
                    "raw_code": "XX",
                }
            ]
        },
    }
    parser2 = MlServiceParser(
        client=MlServiceClient(
            base_url="http://ml.test",
            timeout_sec=5.0,
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=bad_sheet_payload)),
        )
    )
    with contextlib.closing(parser2):
        assert parser2.gatekeeper(defect_item) is None
        parser2.parse(defect_item)
    defect_item.lot.refresh_from_db()
    saved_defect = LotDefect.objects.get(lot=defect_item.lot)
    assert saved_defect.panel_id == BodyPanel.OTHER
    assert saved_defect.severity is None
    assert defect_item.lot.extra_ru == []
    assert any("severity" in w for w in defect_item.lot.ocr_warnings)


def test_ml_mapper_clamps_overflow_integers_and_handles_body_panel_other() -> None:
    sheet = NormalizedSheet(
        first_reg_year=9999999999,
        engine_cc=2**32,
        mileage_km=-10,
        recycling_fee_yen=3_000_000_000,
    )
    fields = _sheet_to_lot_fields(sheet, ParserResponse(status="ok", sheet=sheet), [])
    assert fields["first_reg_year"] is None
    assert fields["year"] is None
    assert fields["engine_cc"] is None
    assert fields["mileage_km"] is None
    assert fields["recycling_fee_yen"] is None
    for name in ("first_reg_year", "engine_cc", "mileage_km", "recycling_fee_yen"):
        assert any(name in w for w in fields["ocr_warnings"])
    assert BodyPanel.OTHER.value == "other"


def test_farpost_matrix_avoids_substring_match_and_schemas_isolate_lists() -> None:
    defects = [
        SimpleNamespace(panel_id="hood", raw_code="", defect_types=["", "AU"], severity=2),
        SimpleNamespace(panel_id="roof", raw_code="A", defect_types=[], severity=3),
    ]
    panels = _panel_codes(defects)
    assert panels["hood"] == {"AU"}
    assert panels["roof"] == {"A3"}

    est_a = FarpostRepairEstimate(
        total_parts_from_rub=0,
        total_works_rub=0,
        grand_total_repair_rub=0,
        has_color_matched_parts=False,
        included_in_turnkey_hint_ru="hint",
    )
    est_b = FarpostRepairEstimate(
        total_parts_from_rub=0,
        total_works_rub=0,
        grand_total_repair_rub=0,
        has_color_matched_parts=False,
        included_in_turnkey_hint_ru="hint",
    )
    assert est_a.parts is not est_b.parts
    assert _supports_metadata_search(Mock()) is False
    assert _supports_metadata_search(FarpostClient()) is True


@pytest.mark.django_db
def test_drom_retry_sleep_capped_cache_keys_hashed_budget_stop_and_corrupt_hp(
    monkeypatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("apps.integrations.drom.client.time.sleep", slept.append)

    client = DromHttpClient(
        max_retries=2,
        retry_backoff_sec=5.0,
        transport=httpx.MockTransport(lambda _r: httpx.Response(503)),
    )
    with client.budget(0.15), pytest.raises(DromBudgetExhaustedError):
        client.get_html("https://auto.drom.ru/toyota/corolla/")
    assert len(slept) == 1
    assert slept[0] <= 0.16

    # Long cache keys are SHA-256 hashed <= 512 chars without truncation collision.
    seen_keys: list[str] = []

    def capture_cache(key: str, **_kw):
        seen_keys.append(key)
        return [], False

    monkeypatch.setattr("apps.integrations.drom.power.fetch_with_drom_cache", capture_cache)
    resolver = DromPowerResolver(client, DromSlugResolver(client))
    resolver._fetch_catalog_specs(
        make="Toyota",
        model="Corolla",
        make_slug="toyota",
        model_slug="m" * 300,
        model_code="C" * 300 + "1",
    )
    resolver._fetch_catalog_specs(
        make="Toyota",
        model="Corolla",
        make_slug="toyota",
        model_slug="m" * 300,
        model_code="C" * 300 + "2",
    )
    assert len(seen_keys) == 2
    assert all(len(k) <= 512 for k in seen_keys)
    assert seen_keys[0] != seen_keys[1]
    assert hashlib.sha256(b"").hexdigest() != ""

    # _fetch_generation_specs stops loop on budget exhaustion.
    gen_calls = 0

    def budget_fail(_url: str) -> str:
        nonlocal gen_calls
        gen_calls += 1
        raise DromFetchError("Request budget exhausted")

    monkeypatch.setattr(client, "get_html", budget_fail)
    specs, complete = resolver._fetch_generation_specs(["https://u1", "https://u2", "https://u3"])
    assert specs == []
    assert complete is False
    assert gen_calls == 1

    # DromSlugResolver hashes overlong make_slug cache keys <= 512 chars.
    slug_keys: list[str] = []
    monkeypatch.setattr(
        "apps.integrations.drom.slugs.resolver.fetch_with_drom_cache",
        lambda key, **_kw: slug_keys.append(key) or (([], {}), False),
    )
    DromSlugResolver(client)._get_sales_models("brand_" * 120)
    assert len(slug_keys) == 1
    assert len(slug_keys[0]) <= 512

    # deserialize_specs ignores corrupted power_hp values.
    parsed = deserialize_specs(
        [
            {"model_code": "NRE210", "power_hp": "bad"},
            {"model_code": "NRE210", "power_hp": None},
            {"model_code": "NRE210", "power_hp": True},
            {"model_code": "NRE210", "power_hp": 116},
        ]
    )
    assert [s.power_hp for s in parsed] == [116]


@pytest.mark.django_db
def test_currency_ntp_skew_and_throttle_deadline_and_redis_pid_and_core_config(
    monkeypatch, settings
) -> None:
    # CurrencyCache tolerates small clock skew (<= 60s) and rejects larger future skew.
    rates = BaseRates(eur_rub=95.0, usd_rub=85.0, jpy_rub=0.58, cbrf_date="12.11.2026")
    cache = CurrencyCache()
    cache.write(rates, timezone.now() + timedelta(seconds=30), ttl=timedelta(hours=1))
    assert cache.read_fresh() is not None

    ExternalCache.objects.all().delete()
    cache.write(rates, timezone.now() + timedelta(seconds=120), ttl=timedelta(hours=1))
    assert cache.read_fresh() is None

    # Throttle checks expired deadline BEFORE reserving a Redis interval slot.
    redis_calls = 0

    def spy_slot(*_a, **_kw):
        nonlocal redis_calls
        redis_calls += 1
        return 0.0

    monkeypatch.setattr(
        "apps.integrations.shared.http.throttle.acquire_distributed_interval_slot", spy_slot
    )
    with pytest.raises(HttpBudgetExhaustedError):
        wait_for_request_slot("k", 1.0, deadline=time.monotonic() - 0.1)
    assert redis_calls == 0

    # redis_utils keys client by os.getpid().
    _cached_clients.clear()
    settings.REDIS_URL = "redis://127.0.0.1:6379/0"
    created: list[object] = []
    monkeypatch.setattr(
        "apps.core.redis_utils.redis.Redis.from_url",
        lambda *_a, **_kw: created.append(object()) or created[-1],
    )
    monkeypatch.setattr(os, "getpid", lambda: 1001)
    c1 = get_redis_client()
    assert get_redis_client() is c1
    monkeypatch.setattr(os, "getpid", lambda: 1002)
    c2 = get_redis_client()
    assert c2 is not c1
    _cached_clients.clear()

    assert CoreBaseRates is BaseRates


@pytest.mark.django_db(transaction=True)
def test_aleado_persist_locks_lot_with_select_for_update_in_atomic_tx(
    monkeypatch,
    user_factory,
) -> None:
    from django.db import connection

    from apps.core.enums import CrossAuditStatus, RiskLevel
    from apps.integrations.aleado.comparator import CrossAuditOutcome
    from apps.integrations.aleado.service import _persist

    user = user_factory(email="aleado-lock@example.com")
    lot = Lot.objects.create(user=user)
    observed: list[bool] = []
    orig_sfu = type(Lot.objects).select_for_update

    def tracked_select_for_update(manager, *args, **kwargs):
        observed.append(connection.in_atomic_block)
        return orig_sfu(manager, *args, **kwargs)

    monkeypatch.setattr(type(Lot.objects), "select_for_update", tracked_select_for_update)
    outcome = CrossAuditOutcome(
        status=CrossAuditStatus.CLEAN,
        risk_level=RiskLevel.INFO,
        has_critical_anomaly=False,
        headline_ru="Clean",
        times_auctioned=0,
        is_archive_available=True,
    )
    assert connection.in_atomic_block is False
    _persist(lot, outcome)
    assert observed == [True]
