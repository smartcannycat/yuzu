"""Redis utilities for distributed throttling and API rate limiting."""

from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
from typing import TYPE_CHECKING

import redis
from django.conf import settings
from redis.exceptions import RedisError

from apps.core.exceptions import TooManyRequestsProblemError

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_cached_clients: dict[tuple[int, str], redis.Redis] = {}


def _reset_redis_clients_after_fork() -> None:
    global _client_lock
    _client_lock = threading.Lock()
    _cached_clients.clear()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_redis_clients_after_fork)

_INTERVAL_SLOT_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local interval_ms = tonumber(ARGV[2])
local max_wait_ms = tonumber(ARGV[3])
local current = redis.call('GET', key)
local next_allowed = current and tonumber(current) or now_ms
if next_allowed < now_ms then
    next_allowed = now_ms
end
local wait_ms = next_allowed - now_ms
if max_wait_ms >= 0 and wait_ms >= max_wait_ms then
    return -1
end
local ttl_ms = wait_ms + interval_ms + 60000
redis.call('SET', key, tostring(next_allowed + interval_ms), 'PX', ttl_ms)
return wait_ms
"""

_RATE_LIMIT_LUA = """
local key = KEYS[1]
local window_sec = tonumber(ARGV[1])
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, window_sec)
end
return count
"""


def get_redis_client() -> redis.Redis | None:
    """Return a lazily initialized, fork-safe Redis client when a Redis URL is configured."""
    url = (getattr(settings, "REDIS_URL", "") or getattr(settings, "CELERY_BROKER_URL", "")).strip()
    if not url or not url.startswith(("redis://", "rediss://")):
        return None

    key = (os.getpid(), url)
    with _client_lock:
        client = _cached_clients.get(key)
        if client is not None:
            return client
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        _cached_clients[key] = client
        return client


def acquire_distributed_interval_slot(
    key: str,
    interval_sec: float,
    *,
    max_wait_sec: float | None = None,
) -> float | None:
    """Reserve the next interval-spaced slot in Redis and return seconds to wait.

    Returns ``None`` when Redis is unconfigured or unreachable so callers can
    fall back to an in-process lock, or ``-1.0`` when waiting would exceed ``max_wait_sec``.
    """
    if interval_sec <= 0:
        return 0.0
    client = get_redis_client()
    if client is None:
        return None
    now_ms = int(time.time() * 1000)
    interval_ms = max(1, int(interval_sec * 1000))
    max_wait_ms = max(0, int(max_wait_sec * 1000)) if max_wait_sec is not None else -1
    try:
        wait_ms = float(client.eval(_INTERVAL_SLOT_LUA, 1, key, now_ms, interval_ms, max_wait_ms))
        if wait_ms < 0:
            return -1.0
        return max(0.0, wait_ms / 1000.0)
    except RedisError as exc:
        logger.debug("Redis throttle slot unavailable, falling back to local lock: %s", exc)
        return None


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


_TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_trusted_proxy_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip_obj in net for net in _TRUSTED_PROXY_NETWORKS)


def get_client_ip(request: HttpRequest) -> str:
    """Extract validated client IP, trusting proxy headers only from trusted proxy hops."""
    remote_ip = _parse_ip(request.META.get("REMOTE_ADDR") or "")
    if remote_ip is not None and _is_trusted_proxy_ip(remote_ip):
        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
        if forwarded:
            valid_hops = [
                ip_obj for part in forwarded.split(",") if (ip_obj := _parse_ip(part)) is not None
            ]
            for ip_obj in reversed(valid_hops):
                if not _is_trusted_proxy_ip(ip_obj):
                    return str(ip_obj)
            if valid_hops:
                return str(valid_hops[0])
        real_ip = _parse_ip(request.META.get("HTTP_X_REAL_IP") or "")
        if real_ip is not None:
            return str(real_ip)
    return str(remote_ip) if remote_ip is not None else "unknown"


def enforce_rate_limit(
    scope: str,
    identifier: str,
    *,
    limit: int,
    window_sec: int,
    detail: str,
) -> None:
    """Apply a Redis fixed-window rate limit, failing open when Redis is unreachable."""
    if not getattr(settings, "RATE_LIMIT_ENABLED", False):
        return
    client = get_redis_client()
    if client is None:
        return
    redis_key = f"yuzu:rl:{scope}:{identifier}"
    try:
        count = int(client.eval(_RATE_LIMIT_LUA, 1, redis_key, window_sec))
    except RedisError as exc:
        logger.warning("Rate-limiter Redis check skipped due to error: %s", exc)
        return
    if count > limit:
        raise TooManyRequestsProblemError(detail)
