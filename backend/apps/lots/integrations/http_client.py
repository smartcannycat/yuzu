"""Shared HTTP transport helpers using curl_cffi browser impersonation and proxy pool."""

from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import httpx
from curl_cffi import requests as curl_requests
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

from apps.core.redis_utils import acquire_distributed_interval_slot
from apps.lots.integrations.proxy import (
    ProxyPool,
    ProxyRotator,
    get_shared_proxy_pool,
    normalize_proxy_urls,
    proxy_fingerprint,
    redact_proxy_url,
    reset_shared_proxy_pools,
    scrub_proxy_credentials,
)
from apps.lots.integrations.url_guard import UnsafeExternalUrlError, validate_external_url

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "HttpBudgetExhaustedError",
    "HttpFetchResponse",
    "HttpTransportError",
    "ProxyPool",
    "ProxyRotator",
    "ResilientHttpSession",
    "clear_local_throttle_state",
    "decode_html_bytes",
    "get_shared_proxy_pool",
    "normalize_proxy_urls",
    "proxy_fingerprint",
    "redact_proxy_url",
    "reset_shared_proxy_pools",
    "scrub_proxy_credentials",
    "wait_for_request_slot",
]

_local_throttle_lock = threading.Lock()
_local_next_request_at: dict[str, float] = {}
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5


class HttpTransportError(RuntimeError):
    """Unified network/transport error raised across httpx mock and curl_cffi sessions."""

    def __init__(self, message: str, *, proxy_key: str = "") -> None:
        super().__init__(message)
        self.proxy_key = proxy_key


class HttpBudgetExhaustedError(HttpTransportError):
    """Raised when waiting for the next rate-limit slot would exceed deadline."""


@dataclass(frozen=True)
class _RawHttpResponse:
    status_code: int
    url: str
    headers: Mapping[str, str]
    content: bytes


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


def clear_local_throttle_state() -> None:
    """Reset in-process fallback request timestamps (for test isolation)."""
    with _local_throttle_lock:
        _local_next_request_at.clear()


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
    remaining: float | None = None
    if deadline is not None:
        remaining = deadline - time.monotonic() - jitter
        if remaining <= 0:
            raise HttpBudgetExhaustedError("Request budget exhausted")
    wait_sec = acquire_distributed_interval_slot(
        throttle_key,
        interval_sec,
        max_wait_sec=remaining,
    )
    if wait_sec is not None and wait_sec < 0:
        raise HttpBudgetExhaustedError("Request budget exhausted")
    if wait_sec is None:
        with _local_throttle_lock:
            now = time.monotonic()
            scheduled = max(now, _local_next_request_at.get(throttle_key, 0.0))
            wait_sec = scheduled - now
            if deadline is not None and now + wait_sec + jitter >= deadline:
                raise HttpBudgetExhaustedError("Request budget exhausted")
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


def _check_content_length(headers: Mapping[str, str], max_bytes: int | None) -> None:
    if max_bytes is None:
        return
    for key, value in headers.items():
        if key.lower() == "content-length" and str(value).isdigit() and int(value) > max_bytes:
            raise HttpTransportError(f"Response size {value} exceeds limit {max_bytes}")


def _strip_body_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    if not headers:
        return headers
    return {k: v for k, v in headers.items() if k.lower() not in {"content-type", "content-length"}}


class ResilientHttpSession:
    """HTTP session that uses curl_cffi browser impersonation in production or httpx in tests."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 10.0,
        impersonate: str = "chrome",
        domain: str | None = None,
        allowed_hosts: frozenset[str] | None = None,
        proxy_rotator: ProxyPool | None = None,
        transport: httpx.BaseTransport | None = None,
        enable_throttle: bool | None = None,
    ) -> None:
        self._headers = dict(headers or {})
        self._timeout_sec = timeout_sec
        self._impersonate = impersonate
        self._domain = domain
        self._allowed_hosts = allowed_hosts
        self._proxy_rotator = proxy_rotator
        self._transport = transport
        self._enable_throttle = (transport is None) if enable_throttle is None else enable_throttle
        self._httpx_clients: dict[str, httpx.Client] = {}
        self._curl_sessions: dict[str, curl_requests.Session] = {}
        self._proxy_domains: dict[str, str] = {}
        self._last_proxy_key = ""
        self._in_context = False

    @property
    def last_proxy_key(self) -> str:
        return self._last_proxy_key

    def __enter__(self) -> ResilientHttpSession:
        self._in_context = True
        return self

    def __exit__(self, *args: object) -> None:
        self._in_context = False
        self._proxy_domains.clear()
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
            effective_domain = (
                domain
                or self._proxy_domains.get(proxy_key)
                or self._domain
                or (urlparse(url).hostname if url else None)
            )
            self._proxy_rotator.mark_blocked(
                proxy_key=proxy_key,
                domain=effective_domain,
                cooldown_sec=cooldown_sec,
            )

    def _select_proxy(
        self,
        *,
        proxy: str | None,
        proxy_key: str | None,
        domain: str | None,
    ) -> tuple[str | None, str]:
        if proxy is not None:
            return proxy, proxy_fingerprint(proxy)
        if proxy_key and self._proxy_rotator is not None:
            pinned = self._proxy_rotator.proxy_for_key(proxy_key)
            if pinned is not None:
                return pinned, proxy_key
        if self._proxy_rotator is not None:
            selected = self._proxy_rotator.next_proxy(domain=domain)
            return selected, proxy_fingerprint(selected)
        return None, ""

    def _validate_target_url(
        self, url: str, *, selected_proxy: str | None, check_dns: bool = False
    ) -> str:
        try:
            return validate_external_url(
                url,
                allowed_hosts=self._allowed_hosts,
                check_dns=check_dns,
                allow_dns_failure=bool(selected_proxy),
            )
        except UnsafeExternalUrlError as exc:
            raise HttpTransportError(f"Blocked unsafe URL {url}: {exc}") from exc

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
        proxy_key: str | None = None,
        domain: str | None = None,
        max_bytes: int | None = None,
        throttle_key: str = "",
        interval_sec: float = 0.0,
        jitter_sec: float = 0.0,
        deadline: float | None = None,
    ) -> HttpFetchResponse:
        return self._request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            proxy=proxy,
            proxy_key=proxy_key,
            domain=domain,
            max_bytes=max_bytes,
            throttle_key=throttle_key,
            interval_sec=interval_sec,
            jitter_sec=jitter_sec,
            deadline=deadline,
        )

    def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
        proxy_key: str | None = None,
        domain: str | None = None,
        max_bytes: int | None = None,
        deadline: float | None = None,
    ) -> HttpFetchResponse:
        """POST form data while preserving the current proxy's cookie jar."""
        return self._request(
            "POST",
            url,
            data=data,
            headers=headers,
            timeout=timeout,
            proxy=proxy,
            proxy_key=proxy_key,
            domain=domain,
            max_bytes=max_bytes,
            deadline=deadline,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
        proxy_key: str | None = None,
        domain: str | None = None,
        max_bytes: int | None = None,
        throttle_key: str = "",
        interval_sec: float = 0.0,
        jitter_sec: float = 0.0,
        deadline: float | None = None,
    ) -> HttpFetchResponse:
        if deadline is not None and time.monotonic() >= deadline:
            raise HttpBudgetExhaustedError("Request budget exhausted")
        effective_timeout = timeout if timeout is not None else self._timeout_sec
        effective_domain = self._effective_domain(url, domain)
        selected_proxy, resolved_proxy_key = self._select_proxy(
            proxy=proxy, proxy_key=proxy_key, domain=effective_domain
        )
        self._last_proxy_key = resolved_proxy_key
        if resolved_proxy_key and effective_domain:
            self._proxy_domains[resolved_proxy_key] = effective_domain

        current_url = self._validate_target_url(url, selected_proxy=selected_proxy, check_dns=False)
        if (
            method == "GET"
            and self._enable_throttle
            and throttle_key
            and (interval_sec > 0 or jitter_sec > 0)
        ):
            scoped_key = f"{throttle_key}:{resolved_proxy_key or 'direct'}"
            wait_for_request_slot(scoped_key, interval_sec, jitter_sec, deadline=deadline)

        should_check_dns = self._transport is None and not selected_proxy
        if should_check_dns:
            current_url = self._validate_target_url(
                current_url, selected_proxy=selected_proxy, check_dns=True
            )

        current_method = method
        current_params = params
        current_data = data
        current_headers = headers

        # Ephemeral single-call client preserves cookies across manual redirect hops
        # even when ResilientHttpSession is used outside a ``with`` block.
        ephemeral_httpx: httpx.Client | None = None
        ephemeral_curl: curl_requests.Session | None = None
        try:
            for hop in range(_MAX_REDIRECTS + 1):
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise HttpBudgetExhaustedError("Request budget exhausted")
                    hop_timeout = min(effective_timeout, remaining)
                else:
                    hop_timeout = effective_timeout

                if self._transport is not None:
                    if self._in_context:
                        client = self._httpx_clients.get(resolved_proxy_key)
                        if client is None:
                            client = self._new_httpx_client()
                            self._httpx_clients[resolved_proxy_key] = client
                    else:
                        if ephemeral_httpx is None:
                            ephemeral_httpx = self._new_httpx_client()
                        client = ephemeral_httpx
                    response = self._send_httpx(
                        client,
                        current_method,
                        current_url,
                        params=current_params,
                        data=current_data,
                        headers=current_headers,
                        timeout=hop_timeout,
                        proxy=selected_proxy,
                        proxy_key=resolved_proxy_key,
                        max_bytes=max_bytes,
                    )
                else:
                    if self._in_context:
                        curl_sess = self._curl_sessions.get(resolved_proxy_key)
                        if curl_sess is None:
                            curl_sess = self._new_curl_session()
                            self._curl_sessions[resolved_proxy_key] = curl_sess
                    else:
                        if ephemeral_curl is None:
                            ephemeral_curl = self._new_curl_session()
                        curl_sess = ephemeral_curl
                    response = self._send_curl(
                        curl_sess,
                        current_method,
                        current_url,
                        params=current_params,
                        data=current_data,
                        headers=current_headers,
                        timeout=hop_timeout,
                        proxy=selected_proxy,
                        proxy_key=resolved_proxy_key,
                        max_bytes=max_bytes,
                    )

                location = response.headers.get("location")
                if response.status_code in _REDIRECT_STATUSES and location:
                    if hop >= _MAX_REDIRECTS:
                        raise HttpTransportError(
                            f"Too many redirects for {url}", proxy_key=resolved_proxy_key
                        )
                    next_url = urljoin(response.url or current_url, location)
                    current_url = self._validate_target_url(
                        next_url, selected_proxy=selected_proxy, check_dns=should_check_dns
                    )
                    if response.status_code in {301, 302, 303}:
                        current_method = "GET"
                        current_data = None
                        current_params = None
                        current_headers = _strip_body_headers(current_headers)
                    else:
                        current_params = None
                    continue

                return HttpFetchResponse(
                    status_code=response.status_code,
                    url=response.url,
                    headers=response.headers,
                    content=response.content,
                    used_proxy=redact_proxy_url(selected_proxy),
                    proxy_key=resolved_proxy_key,
                )
        finally:
            if ephemeral_httpx is not None:
                ephemeral_httpx.close()
            if ephemeral_curl is not None:
                ephemeral_curl.close()

        raise HttpTransportError(f"Too many redirects for {url}", proxy_key=resolved_proxy_key)

    def _new_httpx_client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            headers=self._headers,
            follow_redirects=False,
        )

    def _new_curl_session(self) -> curl_requests.Session:
        return curl_requests.Session(
            impersonate=self._impersonate,
            headers=self._headers,
            default_headers=True,
        )

    def _send_httpx(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        data: dict[str, Any] | bytes | None,
        headers: dict[str, str] | None,
        timeout: float,
        proxy: str | None,
        proxy_key: str,
        max_bytes: int | None,
    ) -> _RawHttpResponse:
        kwargs: dict[str, Any] = {"headers": headers, "timeout": timeout}
        if params is not None:
            kwargs["params"] = params
        if data is not None:
            kwargs["data"] = data
        try:
            with client.stream(method, url, **kwargs) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                _check_content_length(resp_headers, max_bytes)
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise HttpTransportError(f"Response size {total} exceeds limit {max_bytes}")
                    chunks.append(chunk)
                return _RawHttpResponse(
                    status_code=resp.status_code,
                    url=str(resp.url),
                    headers=resp_headers,
                    content=b"".join(chunks),
                )
        except httpx.HTTPError as exc:
            msg, scrubbed = scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}", proxy_key=proxy_key)
            if scrubbed:
                raise err from None
            raise err from exc

    def _send_curl(
        self,
        session: curl_requests.Session,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        data: dict[str, Any] | bytes | None,
        headers: dict[str, str] | None,
        timeout: float,
        proxy: str | None,
        proxy_key: str,
        max_bytes: int | None,
    ) -> _RawHttpResponse:
        kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": False,
            "stream": True,
        }
        if params is not None:
            kwargs["params"] = params
        if data is not None:
            kwargs["data"] = data
        if proxy:
            kwargs["proxy"] = proxy
        try:
            resp = session.request(method, url, **kwargs)
            try:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                _check_content_length(resp_headers, max_bytes)
                if hasattr(resp, "iter_content"):
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_content():
                        total += len(chunk)
                        if max_bytes is not None and total > max_bytes:
                            raise HttpTransportError(
                                f"Response size {total} exceeds limit {max_bytes}"
                            )
                        chunks.append(chunk)
                    content = b"".join(chunks)
                else:
                    content = resp.content
                    if max_bytes is not None and len(content) > max_bytes:
                        raise HttpTransportError(
                            f"Response size {len(content)} exceeds limit {max_bytes}"
                        )
                return _RawHttpResponse(
                    status_code=resp.status_code,
                    url=str(resp.url),
                    headers=resp_headers,
                    content=content,
                )
            finally:
                if hasattr(resp, "close"):
                    resp.close()
        except CurlRequestsError as exc:
            msg, scrubbed = scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}", proxy_key=proxy_key)
            if scrubbed:
                raise err from None
            raise err from exc
