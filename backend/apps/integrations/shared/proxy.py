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
from urllib.parse import unquote, urlparse

from redis.exceptions import RedisError

from apps.core.redis_utils import get_redis_client

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_URL_CREDS_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+):([^/\s]+)@")
_URL_USERINFO_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s@]+)@")
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


def _parse_proxy_url_parts(
    proxy_url: str,
) -> tuple[str, str | None, str | None, str | None, int | None]:
    """Parse proxy URL components, falling back to rsplit('@', 1) when urlparse fails."""
    try:
        parsed = urlparse(proxy_url)
        return (
            parsed.scheme or "http",
            parsed.username,
            parsed.password,
            parsed.hostname,
            parsed.port,
        )
    except ValueError:
        pass
    scheme, sep, rest = proxy_url.partition("://")
    if not sep:
        scheme, rest = "http", proxy_url
    authority = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    username = password = None
    hostport = authority
    if "@" in authority:
        userinfo, hostport = authority.rsplit("@", 1)
        username, _, password_part = userinfo.partition(":")
        password = password_part if _ else None
    hostname: str | None = None
    port_num: int | None = None
    if hostport:
        with contextlib.suppress(ValueError):
            host_parsed = urlparse(f"{scheme or 'http'}://{hostport}")
            hostname, port_num = host_parsed.hostname, host_parsed.port
    return scheme or "http", username, password, hostname, port_num


def redact_proxy_url(proxy_url: str | None) -> str | None:
    """Return scheme://host:port representation without leaking credentials into logs."""
    if not proxy_url:
        return None
    scheme, _username, _password, hostname, port_num = _parse_proxy_url_parts(proxy_url)
    if hostname:
        formatted_host = f"[{hostname}]" if ":" in hostname else hostname
        port = f":{port_num}" if port_num else ""
        return f"{scheme}://{formatted_host}{port}"
    return "<proxy>"


def _mask_secret(
    text: str, secret: str | None, *, require_boundary_for_short: bool
) -> tuple[str, bool]:
    if not secret:
        return text, False
    if len(secret) < 3 and require_boundary_for_short:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(secret)}(?![A-Za-z0-9_])"
        updated = re.sub(pattern, "***", text)
        return updated, updated != text
    if secret in text:
        return text.replace(secret, "***"), True
    return text, False


def scrub_proxy_credentials(text: str, proxy_url: str | None = None) -> tuple[str, bool]:
    """Strip credentials or full proxy URLs from transport error messages."""
    redacted = text
    scrubbed = False
    if proxy_url and proxy_url in redacted:
        redacted = redacted.replace(proxy_url, redact_proxy_url(proxy_url) or "<proxy>")
        scrubbed = True
    cleaned = _URL_CREDS_RE.sub(r"\1***:***@", redacted)
    cleaned = _URL_USERINFO_RE.sub(r"\1***@", cleaned)
    if cleaned != redacted:
        scrubbed = True
    if proxy_url:
        _scheme, username, password, _host, _port = _parse_proxy_url_parts(proxy_url)
        for secret in (password, unquote(password) if password else None):
            cleaned, changed = _mask_secret(cleaned, secret, require_boundary_for_short=False)
            scrubbed = scrubbed or changed
        for secret in (username, unquote(username) if username else None):
            cleaned, changed = _mask_secret(cleaned, secret, require_boundary_for_short=True)
            scrubbed = scrubbed or changed
    return cleaned, scrubbed


def _normalize_domain(domain: str | None) -> str:
    if not domain:
        return "default"
    cleaned = domain.strip().lower()
    if "://" in cleaned:
        with contextlib.suppress(ValueError):
            cleaned = (urlparse(cleaned).hostname or cleaned).lower()
    else:
        cleaned = cleaned.split("/", 1)[0].split(":", 1)[0]
    if cleaned == "drom.ru" or cleaned.endswith(".drom.ru"):
        return "drom.ru"
    if cleaned == "farpost.ru" or cleaned.endswith(".farpost.ru"):
        return "farpost.ru"
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

    def _redis_blocked_fingerprints(self, domain_key: str) -> dict[str, float]:
        if not self._use_redis or not self._fingerprints:
            return {}
        client = get_redis_client()
        if client is None:
            return {}
        keys = [f"{_PROXY_BAN_KEY_PREFIX}:{domain_key}:{fp}" for fp in self._fingerprints]
        try:
            values = client.mget(keys)
        except RedisError as exc:
            logger.debug("Redis proxy quarantine read unavailable: %s", exc)
            return {}
        now_wall = time.time()
        blocked: dict[str, float] = {}
        for fp, val in zip(self._fingerprints, values, strict=True):
            if val is None:
                continue
            raw = val.decode("utf-8", errors="ignore") if isinstance(val, bytes) else str(val)
            if raw.startswith("exp:"):
                with contextlib.suppress(ValueError):
                    remaining = float(raw[4:]) - now_wall
                    if remaining > 0:
                        blocked[fp] = remaining
                    continue
            if self._ban_cooldown_sec > 0:
                blocked[fp] = self._ban_cooldown_sec
        return blocked

    def proxy_for_key(self, proxy_key: str) -> str | None:
        """Return a configured proxy by its non-sensitive fingerprint."""
        if not proxy_key:
            return None
        return self._by_fingerprint.get(proxy_key)

    def next_proxy(self, *, domain: str | None = None) -> str | None:
        """Select the next non-quarantined proxy for ``domain``, falling back gracefully."""
        if not self._proxies:
            return None
        domain_key = _normalize_domain(domain or self._domain)
        now = time.monotonic()

        with self._lock:
            redis_blocked = self._redis_blocked_fingerprints(domain_key)
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
                effective_until = local_until if local_until > now else now + redis_blocked[fp]
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
                            f"exp:{time.time() + ttl:.3f}",
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


_shared_pools_lock = threading.Lock()
_shared_pools: dict[tuple[tuple[str, ...], str | None, float, bool], ProxyPool] = {}


def get_shared_proxy_pool(
    proxy_urls: Sequence[str] = (),
    *,
    domain: str | None = None,
    ban_cooldown_sec: float = _DEFAULT_PROXY_BAN_SEC,
    use_redis: bool = True,
) -> ProxyPool:
    """Return a process-wide ProxyPool keyed by normalized configuration."""
    normalized = normalize_proxy_urls(proxy_urls)
    normalized_domain = _normalize_domain(domain) if domain else None
    cooldown = max(0.0, float(ban_cooldown_sec))
    key = (normalized, normalized_domain, cooldown, use_redis)
    with _shared_pools_lock:
        pool = _shared_pools.get(key)
        if pool is None:
            pool = ProxyPool(
                normalized,
                domain=normalized_domain,
                ban_cooldown_sec=cooldown,
                use_redis=use_redis,
            )
            _shared_pools[key] = pool
        return pool


def reset_shared_proxy_pools() -> None:
    """Clear process-wide shared proxy pools (for test isolation)."""
    with _shared_pools_lock:
        _shared_pools.clear()


ProxyRotator = ProxyPool
