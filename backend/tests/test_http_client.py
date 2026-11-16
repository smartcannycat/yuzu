"""Tests for ResilientHttpSession GET/POST, throttling, deadlines, and error scrubbing."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import httpx
import pytest
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

from apps.lots.integrations.farpost.client import FarpostClient, FarpostFetchError, PartCriteria
from apps.lots.integrations.http_client import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ProxyPool,
    ProxyRotator,
    ResilientHttpSession,
    clear_local_throttle_state,
    proxy_fingerprint,
    reset_shared_proxy_pools,
    wait_for_request_slot,
)


@pytest.fixture(autouse=True)
def _reset_transport_state():
    reset_shared_proxy_pools()
    clear_local_throttle_state()
    yield
    reset_shared_proxy_pools()
    clear_local_throttle_state()


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


def test_wait_for_request_slot_raises_on_budget_exhausted(monkeypatch):
    monkeypatch.setattr(
        "apps.lots.integrations.http_client.acquire_distributed_interval_slot",
        lambda *_a, **_kw: -1.0,
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


def test_wait_for_request_slot_local_fallback_does_not_leak_slot_and_scopes_per_proxy(monkeypatch):
    monkeypatch.setattr(
        "apps.lots.integrations.http_client.acquire_distributed_interval_slot",
        lambda *_a, **_kw: None,
    )
    key = "yuzu:test:no-leak"
    # First call reserves immediate slot; next call would wait ~2s.
    wait_for_request_slot(key, 2.0, deadline=time.monotonic() + 5.0)
    with pytest.raises(HttpBudgetExhaustedError):
        wait_for_request_slot(key, 2.0, deadline=time.monotonic() + 0.2)

    # Rejected call must not push _local_next_request_at forward (slot stays at +2s, not +4s).
    monkeypatch.setattr("apps.lots.integrations.http_client.time.sleep", lambda _sec: None)
    # Only one 2s wait remains before budget 3.0s expires; if leaked twice, this would raise.
    wait_for_request_slot(key, 2.0, deadline=time.monotonic() + 3.0)


def test_oversized_response_does_not_quarantine_healthy_proxy(monkeypatch):
    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: None)
    pool = ProxyPool(
        ["http://p1:8080"], domain="farpost.ru", ban_cooldown_sec=60.0, use_redis=False
    )
    session = ResilientHttpSession(
        proxy_rotator=pool,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=b"x" * 100)),
    )
    with session, pytest.raises(HttpTransportError) as exc_info:
        session.get("https://www.farpost.ru/", max_bytes=10)
    assert exc_info.value.proxy_key == ""
    assert not pool.is_quarantined("http://p1:8080", domain="farpost.ru")


def test_resilient_http_session_get_enforces_deadline_and_throttles_per_proxy(monkeypatch):
    session = ResilientHttpSession(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="ok")),
    )
    with session, pytest.raises(HttpBudgetExhaustedError):
        session.get("https://www.farpost.ru/", deadline=time.monotonic() - 0.1)

    seen_proxy_keys: list[str] = []

    def _capture_slot(key: str, *_a, **_kw):
        seen_proxy_keys.append(key)
        return None

    monkeypatch.setattr(
        "apps.lots.integrations.http_client.acquire_distributed_interval_slot", _capture_slot
    )
    pool = ProxyPool(["http://p1:8080", "http://p2:8080"], domain="farpost.ru", use_redis=False)
    curl_session = ResilientHttpSession(proxy_rotator=pool)
    mock_ok = MagicMock(status_code=200, url="https://www.farpost.ru/", headers={}, content=b"ok")
    monkeypatch.setattr(curl_session, "_send_curl", lambda *_a, **_kw: mock_ok)
    with curl_session:
        curl_session.get("https://www.farpost.ru/", throttle_key="yuzu:test", interval_sec=1.0)
        curl_session.get("https://www.farpost.ru/", throttle_key="yuzu:test", interval_sec=1.0)

    assert seen_proxy_keys == [
        f"yuzu:test:{proxy_fingerprint('http://p1:8080')}",
        f"yuzu:test:{proxy_fingerprint('http://p2:8080')}",
    ]


def test_resilient_http_session_post_proxy_pinning_and_curl_error_scrubbing(monkeypatch):
    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: None)
    pool = ProxyPool(
        ["http://u:secret@p1:8080", "http://u:secret@p2:8080"],
        domain="farpost.ru",
        use_redis=False,
    )
    p1_key = proxy_fingerprint("http://u:secret@p1:8080")

    def post_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oversized":
            return httpx.Response(200, content=b"x" * 64)
        return httpx.Response(200, text=f"posted:{request.content.decode()}")

    session = ResilientHttpSession(
        proxy_rotator=pool,
        transport=httpx.MockTransport(post_handler),
    )
    with session:
        resp = session.post(
            "https://www.farpost.ru/verify",
            data={"s": "tok", "altcha": "sol"},
            proxy_key=p1_key,
            deadline=time.monotonic() + 10,
        )
        assert resp.status_code == 200
        assert resp.proxy_key == p1_key
        assert "s=tok" in resp.content.decode()
        assert p1_key in session._httpx_clients

        with pytest.raises(HttpTransportError, match="exceeds limit"):
            session.post(
                "https://www.farpost.ru/oversized",
                data={"a": "1"},
                max_bytes=10,
                proxy_key=p1_key,
            )

        with pytest.raises(HttpBudgetExhaustedError):
            session.post(
                "https://www.farpost.ru/verify",
                data={"a": "1"},
                deadline=time.monotonic() - 1.0,
            )

        session.drop_proxy_session(p1_key)
        assert p1_key not in session._httpx_clients

    class FailingCurlSession:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request(self, method, _url, **_kwargs):
            raise CurlRequestsError(
                f"{method} proxy auth failed for 'http://myuser:topsecret@127.0.0.1:8080'"
            )

        def close(self):
            return None

    monkeypatch.setattr(
        "apps.lots.integrations.http_client.curl_requests.Session", FailingCurlSession
    )
    curl_session = ResilientHttpSession(
        proxy_rotator=ProxyRotator(["http://myuser:topsecret@127.0.0.1:8080"], use_redis=False)
    )
    for call in (
        lambda: curl_session.get("https://www.farpost.ru/"),
        lambda: curl_session.post("https://www.farpost.ru/verify", data={"s": "1"}),
    ):
        with pytest.raises(HttpTransportError) as exc_info:
            call()
        assert "topsecret" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
