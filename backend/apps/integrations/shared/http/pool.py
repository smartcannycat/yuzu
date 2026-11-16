"""Proxy selection and per-proxy client/cookie-jar lifecycle for ResilientHttpSession."""

from __future__ import annotations

import time

import httpx
from curl_cffi import requests as curl_requests

from apps.integrations.shared.http.throttle import HttpBudgetExhaustedError
from apps.integrations.shared.proxy import ProxyPool, proxy_fingerprint


def compute_hop_timeout(effective_timeout: float, deadline: float | None) -> float:
    if deadline is None:
        return effective_timeout
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise HttpBudgetExhaustedError("Request budget exhausted")
    return min(effective_timeout, remaining)


def select_proxy(
    rotator: ProxyPool | None,
    *,
    proxy: str | None,
    proxy_key: str | None,
    domain: str | None,
) -> tuple[str | None, str]:
    if proxy is not None:
        return proxy, proxy_fingerprint(proxy)
    if proxy_key and rotator is not None:
        pinned = rotator.proxy_for_key(proxy_key)
        if pinned is not None:
            return pinned, proxy_key
    if rotator is not None:
        selected = rotator.next_proxy(domain=domain)
        return selected, proxy_fingerprint(selected)
    return None, ""


class SessionClientRegistry:
    """Stores persistent per-proxy clients across ``with session:`` blocks."""

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None,
        headers: dict[str, str],
        impersonate: str,
    ) -> None:
        self._transport = transport
        self._headers = headers
        self._impersonate = impersonate
        self.httpx_clients: dict[str, httpx.Client] = {}
        self.curl_sessions: dict[str, curl_requests.Session] = {}
        self.in_context = False

    def new_httpx_client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport, headers=self._headers, follow_redirects=False
        )

    def new_curl_session(self) -> curl_requests.Session:
        return curl_requests.Session(
            impersonate=self._impersonate, headers=self._headers, default_headers=True
        )

    def drop(self, proxy_key: str) -> None:
        if client := self.httpx_clients.pop(proxy_key, None):
            client.close()
        if session := self.curl_sessions.pop(proxy_key, None):
            session.close()

    def close_all(self) -> None:
        self.in_context = False
        for client in self.httpx_clients.values():
            client.close()
        self.httpx_clients.clear()
        for session in self.curl_sessions.values():
            session.close()
        self.curl_sessions.clear()


class SessionClients:
    """Manages persistent (context-managed) or ephemeral httpx/curl clients for a request."""

    def __init__(self, registry: SessionClientRegistry, resolved_proxy_key: str) -> None:
        self._registry = registry
        self._proxy_key = resolved_proxy_key
        self._ephemeral_httpx: httpx.Client | None = None
        self._ephemeral_curl: curl_requests.Session | None = None

    def get_httpx(self) -> httpx.Client:
        if self._registry.in_context:
            client = self._registry.httpx_clients.get(self._proxy_key)
            if client is None:
                client = self._registry.new_httpx_client()
                self._registry.httpx_clients[self._proxy_key] = client
            return client
        if self._ephemeral_httpx is None:
            self._ephemeral_httpx = self._registry.new_httpx_client()
        return self._ephemeral_httpx

    def get_curl(self) -> curl_requests.Session:
        if self._registry.in_context:
            session = self._registry.curl_sessions.get(self._proxy_key)
            if session is None:
                session = self._registry.new_curl_session()
                self._registry.curl_sessions[self._proxy_key] = session
            return session
        if self._ephemeral_curl is None:
            self._ephemeral_curl = self._registry.new_curl_session()
        return self._ephemeral_curl

    def close(self) -> None:
        if self._ephemeral_httpx is not None:
            self._ephemeral_httpx.close()
        if self._ephemeral_curl is not None:
            self._ephemeral_curl.close()
