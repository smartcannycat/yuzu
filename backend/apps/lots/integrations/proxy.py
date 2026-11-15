"""Shared domain-aware proxy pool, credential redaction, and temporary quarantine helpers."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import math
import re
import threading
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from redis.exceptions import RedisError

from apps.core.redis_utils import get_redis_client

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_URL_CREDS_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+):([^@\s]+)@")
_DEFAULT_PROXY_BAN_SEC = 120.0
_PROXY_BAN_KEY_PREFIX = "yuzu:proxy:ban"


def normalize_proxy_urls(*groups: Sequence[str] | str | None) -> tuple[str, ...]:
    """Flatten, strip, and deduplicate proxy URLs across override and shared groups."""
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        if not group:
            continue
        items: Sequence[str] = [group] if isinstance(group, str) else group
        for raw in items:
            if not raw:
                continue
            cleaned = str(raw).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                ordered.append(cleaned)
    return tuple(ordered)


def proxy_fingerprint(proxy_url: str | None) -> str:
    """Return a non-sensitive deterministic digest for a proxy URL."""
    if not proxy_url:
        return ""
    return hashlib.sha256(proxy_url.encode("utf-8")).hexdigest()[:16]


def redact_proxy_url(proxy_url: str | None) -> str | None:
    """Return scheme://host:port representation without leaking credentials into logs."""
    if not proxy_url:
        return None
    try:
        parsed = urlparse(proxy_url)
        hostname = parsed.hostname
        port_num = parsed.port
    except ValueError:
        return "<proxy>"
    if hostname:
        port = f":{port_num}" if port_num else ""
        scheme = parsed.scheme or "http"
        return f"{scheme}://{hostname}{port}"
    return "<proxy>"


def scrub_proxy_credentials(text: str, proxy_url: str | None = None) -> tuple[str, bool]:
    """Strip credentials or full proxy URLs from transport error messages."""
    redacted = text
    scrubbed = False
    if proxy_url and proxy_url in redacted:
        redacted = redacted.replace(proxy_url, redact_proxy_url(proxy_url) or "<proxy>")
        scrubbed = True
    cleaned = _URL_CREDS_RE.sub(r"\1***:***@", redacted)
    if cleaned != redacted:
        scrubbed = True
    if proxy_url:
        try:
            parsed = urlparse(proxy_url)
            if parsed.password and parsed.password in cleaned:
                cleaned = cleaned.replace(parsed.password, "***")
                scrubbed = True
        except ValueError:
            pass
    return cleaned, scrubbed


def _normalize_domain(domain: str | None) -> str:
    if not domain:
        return "default"
    cleaned = domain.strip().lower()
    if "://" in cleaned:
        with contextlib.suppress(ValueError):
            cleaned = (urlparse(cleaned).hostname or cleaned).lower()
    return cleaned or "default"


class ProxyPool:
    """Thread-safe round-robin proxy pool with per-domain temporary quarantine."""

    def __init__(
        self,
        proxy_urls: Sequence[str] = (),
        *,
        domain: str | None = None,
        ban_cooldown_sec: float = _DEFAULT_PROXY_BAN_SEC,
        use_redis: bool = True,
    ) -> None:
        self._proxies = normalize_proxy_urls(proxy_urls)
        self._fingerprints = tuple(proxy_fingerprint(p) for p in self._proxies)
        self._by_fingerprint = dict(zip(self._fingerprints, self._proxies, strict=True))
        self._domain = domain
        self._ban_cooldown_sec = max(0.0, float(ban_cooldown_sec))
        self._use_redis = use_redis
        self._index = 0
        self._lock = threading.Lock()
        self._blocked_until: dict[tuple[str, str], float] = {}

    def __len__(self) -> int:
        return len(self._proxies)

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def _redis_blocked_fingerprints(self, domain_key: str) -> set[str]:
        if not self._use_redis or not self._fingerprints or self._ban_cooldown_sec <= 0:
            return set()
        client = get_redis_client()
        if client is None:
            return set()
        keys = [f"{_PROXY_BAN_KEY_PREFIX}:{domain_key}:{fp}" for fp in self._fingerprints]
        try:
            values = client.mget(keys)
        except RedisError as exc:
            logger.debug("Redis proxy quarantine read unavailable: %s", exc)
            return set()
        return {fp for fp, val in zip(self._fingerprints, values, strict=True) if val is not None}

    def next_proxy(self, *, domain: str | None = None) -> str | None:
        """Select the next non-quarantined proxy for ``domain``, falling back gracefully."""
        if not self._proxies:
            return None
        domain_key = _normalize_domain(domain or self._domain)
        redis_blocked = self._redis_blocked_fingerprints(domain_key)
        now = time.monotonic()

        with self._lock:
            n = len(self._proxies)
            start = self._index % n
            best_quarantined_idx: int | None = None
            earliest_unblock = float("inf")

            for offset in range(n):
                idx = (start + offset) % n
                fp = self._fingerprints[idx]
                local_until = self._blocked_until.get((domain_key, fp), 0.0)
                if local_until <= now and fp not in redis_blocked:
                    self._index = idx + 1
                    return self._proxies[idx]
                effective_until = local_until if local_until > now else now + self._ban_cooldown_sec
                if effective_until < earliest_unblock:
                    earliest_unblock = effective_until
                    best_quarantined_idx = idx

            assert best_quarantined_idx is not None
            self._index = best_quarantined_idx + 1
            return self._proxies[best_quarantined_idx]

    def mark_blocked(
        self,
        proxy: str | None = None,
        *,
        proxy_key: str = "",
        domain: str | None = None,
        cooldown_sec: float | None = None,
    ) -> None:
        """Put a proxy into temporary quarantine for ``domain`` without affecting others."""
        fp = proxy_key or proxy_fingerprint(proxy)
        if not fp or fp not in self._by_fingerprint:
            return
        ttl = self._ban_cooldown_sec if cooldown_sec is None else max(0.0, float(cooldown_sec))
        if ttl <= 0:
            return
        domain_key = _normalize_domain(domain or self._domain)
        until = time.monotonic() + ttl
        with self._lock:
            current = self._blocked_until.get((domain_key, fp), 0.0)
            if until > current:
                self._blocked_until[(domain_key, fp)] = until

        if self._use_redis:
            client = get_redis_client()
            if client is not None:
                try:
                    client.set(
                        f"{_PROXY_BAN_KEY_PREFIX}:{domain_key}:{fp}",
                        "1",
                        ex=max(1, math.ceil(ttl)),
                    )
                except RedisError as exc:
                    logger.debug("Redis proxy quarantine write unavailable: %s", exc)

    def is_quarantined(self, proxy: str, *, domain: str | None = None) -> bool:
        fp = proxy_fingerprint(proxy)
        if not fp or fp not in self._by_fingerprint:
            return False
        domain_key = _normalize_domain(domain or self._domain)
        now = time.monotonic()
        with self._lock:
            if self._blocked_until.get((domain_key, fp), 0.0) > now:
                return True
        return fp in self._redis_blocked_fingerprints(domain_key)

    def clear_cooldown(
        self,
        proxy: str | None = None,
        *,
        proxy_key: str = "",
        domain: str | None = None,
    ) -> None:
        fp = proxy_key or proxy_fingerprint(proxy)
        if not fp:
            return
        domain_key = _normalize_domain(domain or self._domain)
        with self._lock:
            self._blocked_until.pop((domain_key, fp), None)
        if self._use_redis:
            client = get_redis_client()
            if client is not None:
                with contextlib.suppress(RedisError):
                    client.delete(f"{_PROXY_BAN_KEY_PREFIX}:{domain_key}:{fp}")


ProxyRotator = ProxyPool
