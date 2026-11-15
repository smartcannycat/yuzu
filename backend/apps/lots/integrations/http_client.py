"""Shared HTTP transport helpers using curl_cffi browser impersonation and proxy pool."""

from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from curl_cffi import requests as curl_requests
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

from apps.core.redis_utils import acquire_distributed_interval_slot
from apps.lots.integrations.proxy import (
    ProxyPool,
    ProxyRotator,
    normalize_proxy_urls,
    proxy_fingerprint,
    redact_proxy_url,
    scrub_proxy_credentials,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "HttpBudgetExhaustedError",
    "HttpFetchResponse",
    "HttpTransportError",
    "ProxyPool",
    "ProxyRotator",
    "ResilientHttpSession",
    "decode_html_bytes",
    "normalize_proxy_urls",
    "proxy_fingerprint",
    "redact_proxy_url",
    "scrub_proxy_credentials",
    "wait_for_request_slot",
]

_local_throttle_lock = threading.Lock()
_local_next_request_at: dict[str, float] = {}


class HttpTransportError(RuntimeError):
    """Unified network/transport error raised across httpx mock and curl_cffi sessions."""

    def __init__(self, message: str, *, proxy_key: str = "") -> None:
        super().__init__(message)
        self.proxy_key = proxy_key


class HttpBudgetExhaustedError(HttpTransportError):
    """Raised when waiting for the next rate-limit slot would exceed deadline."""


@dataclass(frozen=True)
class HttpFetchResponse:
    """Normalized HTTP response decoupled from underlying client implementation."""

    status_code: int
    url: str
    headers: Mapping[str, str]
    content: bytes
    used_proxy: str | None = None
    proxy_key: str = ""

    def json(self) -> Any:
        content_type = self.headers.get("content-type", "").lower()
        if "windows-1251" in content_type or "cp1251" in content_type:
            return json.loads(self.content.decode("cp1251"))
        return json.loads(self.content)


def wait_for_request_slot(
    throttle_key: str,
    interval_sec: float,
    jitter_sec: float = 0.0,
    *,
    deadline: float | None = None,
) -> None:
    """Reserve the next interval-spaced slot via Redis or per-key process lock."""
    if interval_sec <= 0 and jitter_sec <= 0:
        return
    jitter = random.uniform(0.0, jitter_sec) if jitter_sec > 0 else 0.0
    wait_sec = acquire_distributed_interval_slot(throttle_key, interval_sec)
    if wait_sec is None:
        with _local_throttle_lock:
            now = time.monotonic()
            scheduled = max(now, _local_next_request_at.get(throttle_key, 0.0))
            wait_sec = scheduled - now
            _local_next_request_at[throttle_key] = scheduled + interval_sec
    total_wait = wait_sec + jitter
    if total_wait > 0:
        if deadline is not None and time.monotonic() + total_wait >= deadline:
            raise HttpBudgetExhaustedError("Request budget exhausted")
        time.sleep(total_wait)


def decode_html_bytes(content: bytes, headers: Mapping[str, str] | None = None) -> str:
    """Decode HTML payloads while respecting windows-1251/cp1251 headers or meta tags."""
    content_type = (headers or {}).get("content-type", "").lower()
    if "windows-1251" in content_type or "cp1251" in content_type:
        return content.decode("cp1251", errors="replace")
    if "utf-8" in content_type:
        return content.decode("utf-8", errors="replace")
    head = content[:4000].decode("ascii", errors="ignore").lower()
    if "windows-1251" in head or "cp1251" in head:
        return content.decode("cp1251", errors="replace")
    return content.decode("utf-8", errors="replace")


class ResilientHttpSession:
    """HTTP session that uses curl_cffi browser impersonation in production or httpx in tests."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 10.0,
        impersonate: str = "chrome",
        domain: str | None = None,
        proxy_rotator: ProxyPool | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._headers = dict(headers or {})
        self._timeout_sec = timeout_sec
        self._impersonate = impersonate
        self._domain = domain
        self._proxy_rotator = proxy_rotator
        self._transport = transport
        self._httpx_clients: dict[str, httpx.Client] = {}
        self._curl_sessions: dict[str, curl_requests.Session] = {}
        self._in_context = False

    def __enter__(self) -> ResilientHttpSession:
        self._in_context = True
        return self

    def __exit__(self, *args: object) -> None:
        self._in_context = False
        for client in self._httpx_clients.values():
            client.close()
        self._httpx_clients.clear()
        for session in self._curl_sessions.values():
            session.close()
        self._curl_sessions.clear()

    def _effective_domain(self, url: str, domain: str | None = None) -> str | None:
        return domain or self._domain or urlparse(url).hostname

    def drop_proxy_session(self, proxy_key: str) -> None:
        """Close and discard cached client state for ``proxy_key`` (e.g. challenge cookies)."""
        if client := self._httpx_clients.pop(proxy_key, None):
            client.close()
        if session := self._curl_sessions.pop(proxy_key, None):
            session.close()

    def mark_proxy_blocked(
        self,
        proxy_key: str,
        *,
        url: str | None = None,
        domain: str | None = None,
        cooldown_sec: float | None = None,
    ) -> None:
        """Quarantine ``proxy_key`` for the target domain and reset its cookie jar."""
        if not proxy_key:
            return
        self.drop_proxy_session(proxy_key)
        if self._proxy_rotator is not None:
            effective_domain = domain or self._domain or (urlparse(url).hostname if url else None)
            self._proxy_rotator.mark_blocked(
                proxy_key=proxy_key,
                domain=effective_domain,
                cooldown_sec=cooldown_sec,
            )

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
        domain: str | None = None,
        max_bytes: int | None = None,
    ) -> HttpFetchResponse:
        effective_timeout = timeout if timeout is not None else self._timeout_sec
        effective_domain = self._effective_domain(url, domain)
        selected_proxy = proxy
        if selected_proxy is None and self._proxy_rotator:
            selected_proxy = self._proxy_rotator.next_proxy(domain=effective_domain)
        proxy_key = proxy_fingerprint(selected_proxy)

        if self._transport is not None:
            response = self._get_httpx(
                url,
                params=params,
                headers=headers,
                timeout=effective_timeout,
                proxy=selected_proxy,
                proxy_key=proxy_key,
            )
        else:
            response = self._get_curl(
                url,
                params=params,
                headers=headers,
                timeout=effective_timeout,
                proxy=selected_proxy,
                proxy_key=proxy_key,
            )

        if max_bytes is not None and len(response.content) > max_bytes:
            raise HttpTransportError(
                f"Response size {len(response.content)} exceeds limit {max_bytes}",
                proxy_key=proxy_key,
            )
        return HttpFetchResponse(
            status_code=response.status_code,
            url=str(response.url),
            headers={k.lower(): v for k, v in response.headers.items()},
            content=response.content,
            used_proxy=redact_proxy_url(selected_proxy),
            proxy_key=proxy_key,
        )

    def _get_httpx(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: float,
        proxy: str | None,
        proxy_key: str,
    ) -> httpx.Response:
        try:
            if self._in_context:
                client = self._httpx_clients.get(proxy_key)
                if client is None:
                    client = httpx.Client(
                        transport=self._transport,
                        headers=self._headers,
                        follow_redirects=True,
                    )
                    self._httpx_clients[proxy_key] = client
                return client.get(url, params=params, headers=headers, timeout=timeout)
            with httpx.Client(
                transport=self._transport,
                headers=self._headers,
                follow_redirects=True,
            ) as client:
                return client.get(url, params=params, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            msg, scrubbed = scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}", proxy_key=proxy_key)
            if scrubbed:
                raise err from None
            raise err from exc

    def _get_curl(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: float,
        proxy: str | None,
        proxy_key: str,
    ) -> curl_requests.Response:
        kwargs: dict[str, Any] = {
            "params": params,
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": True,
        }
        if proxy:
            kwargs["proxy"] = proxy
        try:
            if self._in_context:
                session = self._curl_sessions.get(proxy_key)
                if session is None:
                    session = curl_requests.Session(
                        impersonate=self._impersonate,
                        headers=self._headers,
                        default_headers=True,
                    )
                    self._curl_sessions[proxy_key] = session
                return session.get(url, **kwargs)
            with curl_requests.Session(
                impersonate=self._impersonate,
                headers=self._headers,
                default_headers=True,
            ) as session:
                return session.get(url, **kwargs)
        except CurlRequestsError as exc:
            msg, scrubbed = scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}", proxy_key=proxy_key)
            if scrubbed:
                raise err from None
            raise err from exc
