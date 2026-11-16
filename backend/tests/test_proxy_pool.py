"""Tests for shared domain-aware ProxyPool, redaction, and Redis quarantine."""

from __future__ import annotations

import pytest
from redis.exceptions import RedisError

from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.farpost.client import FarpostClient
from apps.lots.integrations.proxy import (
    ProxyPool,
    ProxyRotator,
    get_shared_proxy_pool,
    normalize_proxy_urls,
    proxy_fingerprint,
    redact_proxy_url,
    reset_shared_proxy_pools,
)


@pytest.fixture(autouse=True)
def _reset_proxy_pools():
    reset_shared_proxy_pools()
    yield
    reset_shared_proxy_pools()


def test_proxy_rotator_cycles_and_redacts_credentials():
    rotator = ProxyRotator(["http://u1:s1@proxy1.local:8080", "http://proxy2.local:3128"])
    assert len(rotator) == 2
    assert rotator.next_proxy() == "http://u1:s1@proxy1.local:8080"
    assert rotator.next_proxy() == "http://proxy2.local:3128"
    assert rotator.next_proxy() == "http://u1:s1@proxy1.local:8080"
    assert redact_proxy_url("http://u1:s1@proxy1.local:8080") == "http://proxy1.local:8080"
    assert redact_proxy_url("http://user:s3cr3t@127.0.0.1:abc") == "<proxy>"
    assert redact_proxy_url("http://user:p[ss@proxy.local:8080") == "<proxy>"
    assert redact_proxy_url(None) is None


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
    pool_worker_a.mark_blocked(
        "http://user:topsecret@p1:8080", domain="www.farpost.ru", cooldown_sec=30.0
    )

    assert stored
    assert all("topsecret" not in key for key in stored)
    assert all(val.startswith("exp:") for val in stored.values())
    assert pool_worker_b.next_proxy(domain="www.farpost.ru") == "http://user:topsecret@p2:8080"

    # Both quarantined in Redis with different TTLs -> pick earliest-expiring one.
    pool_worker_a.mark_blocked(
        "http://user:topsecret@p2:8080", domain="www.farpost.ru", cooldown_sec=120.0
    )
    assert pool_worker_b.next_proxy(domain="www.farpost.ru") == "http://user:topsecret@p1:8080"

    # Subdomain normalization groups auto.drom.ru and drom.ru together.
    pool_worker_a.mark_blocked(
        "http://user:topsecret@p1:8080", domain="auto.drom.ru", cooldown_sec=30.0
    )
    assert pool_worker_b.is_quarantined(
        "http://user:topsecret@p1:8080", domain="vladivostok.drom.ru"
    )

    # Redis errors degrade cleanly to in-process state without crashing.
    class BrokenRedis:
        def mget(self, keys):
            raise RedisError("redis down")

        def set(self, key, value, ex=None):
            raise RedisError("redis down")

        def delete(self, key):
            raise RedisError("redis down")

    monkeypatch.setattr("apps.lots.integrations.proxy.get_redis_client", lambda: BrokenRedis())
    pool_worker_b.mark_blocked("http://user:topsecret@p2:8080", domain="drom.ru", cooldown_sec=30.0)
    assert pool_worker_b.is_quarantined("http://user:topsecret@p2:8080", domain="drom.ru")


def test_shared_proxy_pool_is_shared_between_farpost_and_drom_and_normalizes_domain():
    proxies = ["http://p1:8080", "http://p2:8080"]
    fp = FarpostClient(proxy_urls=proxies, proxy_ban_sec=60.0)
    drom = DromHttpClient(proxy_urls=proxies, proxy_ban_sec=60.0)
    assert fp._proxy_rotator is not None
    assert fp._proxy_rotator is drom._proxy_rotator

    pool_a = get_shared_proxy_pool(proxies, domain="www.farpost.ru", ban_cooldown_sec=60.0)
    pool_b = get_shared_proxy_pool(proxies, domain="farpost.ru", ban_cooldown_sec=60.0)
    assert pool_a is pool_b

    p1_key = proxy_fingerprint("http://p1:8080")
    assert pool_a.proxy_for_key(p1_key) == "http://p1:8080"
    assert pool_a.proxy_for_key("missing") is None
    assert pool_a.proxy_for_key("") is None
