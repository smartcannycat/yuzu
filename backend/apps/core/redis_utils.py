"""Redis utilities for distributed throttling and API rate limiting."""

from __future__ import annotations

import logging
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
_cached_url: str | None = None
_cached_client: redis.Redis | None = None

_INTERVAL_SLOT_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local interval_ms = tonumber(ARGV[2])
local ttl_ms = tonumber(ARGV[3])
local current = redis.call('GET', key)
local next_allowed = current and tonumber(current) or now_ms
if next_allowed < now_ms then
    next_allowed = now_ms
end
local wait_ms = next_allowed - now_ms
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
    """Return a lazily initialized Redis client when a Redis URL is configured."""
    global _cached_url, _cached_client

    url = (getattr(settings, "REDIS_URL", "") or getattr(settings, "CELERY_BROKER_URL", "")).strip()
    if not url or not url.startswith(("redis://", "rediss://")):
        return None

    with _client_lock:
        if _cached_client is not None and _cached_url == url:
            return _cached_client
        _cached_url = url
        _cached_client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        return _cached_client


def acquire_distributed_interval_slot(key: str, interval_sec: float) -> float | None:
    """Reserve the next interval-spaced slot in Redis and return seconds to wait.

    Returns ``None`` when Redis is unconfigured or unreachable so callers can
    fall back to an in-process lock.
    """
    if interval_sec <= 0:
        return 0.0
    client = get_redis_client()
    if client is None:
        return None
    now_ms = int(time.time() * 1000)
    interval_ms = max(1, int(interval_sec * 1000))
    ttl_ms = interval_ms + 60_000
    try:
        wait_ms = client.eval(_INTERVAL_SLOT_LUA, 1, key, now_ms, interval_ms, ttl_ms)
        return max(0.0, float(wait_ms) / 1000.0)
    except RedisError as exc:
        logger.debug("Redis throttle slot unavailable, falling back to local lock: %s", exc)
        return None


def get_client_ip(request: HttpRequest) -> str:
    """Extract best-effort client IP behind reverse proxies (Caddy / Traefik)."""
    real_ip = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if real_ip:
        return real_ip
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return (request.META.get("REMOTE_ADDR") or "unknown").strip() or "unknown"


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
