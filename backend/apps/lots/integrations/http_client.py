"""Shared HTTP transport helpers using curl_cffi browser impersonation and proxy rotation."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from curl_cffi import requests as curl_requests
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_URL_CREDS_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+):([^@\s]+)@")


class HttpTransportError(RuntimeError):
    """Unified network/transport error raised across httpx mock and curl_cffi sessions."""


@dataclass(frozen=True)
class HttpFetchResponse:
    """Normalized HTTP response decoupled from underlying client implementation."""

    status_code: int
    url: str
    headers: Mapping[str, str]
    content: bytes
    used_proxy: str | None = None

    def json(self) -> Any:
        content_type = self.headers.get("content-type", "").lower()
        if "windows-1251" in content_type or "cp1251" in content_type:
            return json.loads(self.content.decode("cp1251"))
        return json.loads(self.content)


def redact_proxy_url(proxy_url: str | None) -> str | None:
    """Return host:port representation without leaking credentials into logs."""
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


def _scrub_proxy_credentials(text: str, proxy_url: str | None = None) -> tuple[str, bool]:
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


class ProxyRotator:
    """Thread-safe round-robin proxy selector for scraper sessions."""

    def __init__(self, proxy_urls: Sequence[str] = ()) -> None:
        self._proxies = tuple(p.strip() for p in proxy_urls if p and p.strip())
        self._index = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._proxies)

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def next_proxy(self) -> str | None:
        if not self._proxies:
            return None
        with self._lock:
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy


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
        proxy_rotator: ProxyRotator | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._headers = dict(headers or {})
        self._timeout_sec = timeout_sec
        self._impersonate = impersonate
        self._proxy_rotator = proxy_rotator
        self._transport = transport
        self._httpx_clients: dict[str | None, httpx.Client] = {}
        self._curl_sessions: dict[str | None, curl_requests.Session] = {}
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

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
        max_bytes: int | None = None,
    ) -> HttpFetchResponse:
        effective_timeout = timeout if timeout is not None else self._timeout_sec
        selected_proxy = proxy
        if selected_proxy is None and self._proxy_rotator:
            selected_proxy = self._proxy_rotator.next_proxy()

        if self._transport is not None:
            response = self._get_httpx(
                url,
                params=params,
                headers=headers,
                timeout=effective_timeout,
                proxy=selected_proxy,
            )
        else:
            response = self._get_curl(
                url,
                params=params,
                headers=headers,
                timeout=effective_timeout,
                proxy=selected_proxy,
            )

        if max_bytes is not None and len(response.content) > max_bytes:
            raise HttpTransportError(
                f"Response size {len(response.content)} exceeds limit {max_bytes}"
            )
        return HttpFetchResponse(
            status_code=response.status_code,
            url=str(response.url),
            headers={k.lower(): v for k, v in response.headers.items()},
            content=response.content,
            used_proxy=redact_proxy_url(selected_proxy),
        )

    def _get_httpx(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: float,
        proxy: str | None = None,
    ) -> httpx.Response:
        try:
            if self._in_context:
                client = self._httpx_clients.get(proxy)
                if client is None:
                    client = httpx.Client(
                        transport=self._transport,
                        headers=self._headers,
                        follow_redirects=True,
                    )
                    self._httpx_clients[proxy] = client
                return client.get(url, params=params, headers=headers, timeout=timeout)
            with httpx.Client(
                transport=self._transport,
                headers=self._headers,
                follow_redirects=True,
            ) as client:
                return client.get(url, params=params, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            msg, scrubbed = _scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}")
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
                session = self._curl_sessions.get(proxy)
                if session is None:
                    session = curl_requests.Session(
                        impersonate=self._impersonate,
                        headers=self._headers,
                        default_headers=True,
                    )
                    self._curl_sessions[proxy] = session
                return session.get(url, **kwargs)
            with curl_requests.Session(
                impersonate=self._impersonate,
                headers=self._headers,
                default_headers=True,
            ) as session:
                return session.get(url, **kwargs)
        except CurlRequestsError as exc:
            msg, scrubbed = _scrub_proxy_credentials(str(exc), proxy)
            err = HttpTransportError(f"Request failed for {url}: {msg}")
            if scrubbed:
                raise err from None
            raise err from exc
