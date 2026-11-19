"""Proxy selection and per-proxy client/cookie-jar lifecycle for ResilientHttpSession."""

from __future__ import annotations

import threading
import time

import httpx
from curl_cffi import requests as curl_requests

from apps.integrations.shared.http.throttle import HttpBudgetExhaustedError, HttpTransportError
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
    if proxy_key:
        if rotator is None:
            raise HttpTransportError(
                f"Pinned proxy key {proxy_key!r} cannot be resolved without a proxy pool",
                proxy_key=proxy_key,
            )
        pinned = rotator.proxy_for_key(proxy_key)
        if pinned is None:
            raise HttpTransportError(
                f"Pinned proxy key {proxy_key!r} is missing from proxy pool",
                proxy_key=proxy_key,
            )
        return pinned, proxy_key
    if rotator is not None:
        selected = rotator.next_proxy(domain=domain)
        return selected, proxy_fingerprint(selected)
    return None, ""


class SessionClientRegistry:
    """Thread-safe store of persistent per-proxy clients across ``with session:`` blocks."""

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
        self._lock = threading.Lock()
        self.httpx_clients: dict[str, httpx.Client] = {}
        self.curl_sessions: dict[str, curl_requests.Session] = {}
        self._in_context = False

    @property
    def in_context(self) -> bool:
        with self._lock:
            return self._in_context

    @in_context.setter
    def in_context(self, value: bool) -> None:
        with self._lock:
            self._in_context = bool(value)

    def new_httpx_client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport, headers=self._headers, follow_redirects=False
        )

    def new_curl_session(self) -> curl_requests.Session:
        return curl_requests.Session(
            impersonate=self._impersonate, headers=self._headers, default_headers=True
        )

    def get_or_create_httpx(self, proxy_key: str) -> tuple[httpx.Client, bool]:
        with self._lock:
            if not self._in_context:
                return self.new_httpx_client(), False
            client = self.httpx_clients.get(proxy_key)
            if client is None:
                client = self.new_httpx_client()
                self.httpx_clients[proxy_key] = client
            return client, True

    def get_or_create_curl(self, proxy_key: str) -> tuple[curl_requests.Session, bool]:
        with self._lock:
            if not self._in_context:
                return self.new_curl_session(), False
            session = self.curl_sessions.get(proxy_key)
            if session is None:
                session = self.new_curl_session()
                self.curl_sessions[proxy_key] = session
            return session, True

    def drop(self, proxy_key: str) -> None:
        with self._lock:
            client = self.httpx_clients.pop(proxy_key, None)
            session = self.curl_sessions.pop(proxy_key, None)
        if client is not None:
            client.close()
        if session is not None:
            session.close()

    def close_all(self) -> None:
        with self._lock:
            self._in_context = False
            clients = list(self.httpx_clients.values())
            self.httpx_clients.clear()
            sessions = list(self.curl_sessions.values())
            self.curl_sessions.clear()
        for client in clients:
            client.close()
        for session in sessions:
            session.close()


class SessionClients:
    """Manages persistent (context-managed) or ephemeral httpx/curl clients for a request."""

    def __init__(self, registry: SessionClientRegistry, resolved_proxy_key: str) -> None:
        self._registry = registry
        self._proxy_key = resolved_proxy_key
        self._ephemeral_httpx: httpx.Client | None = None
        self._ephemeral_curl: curl_requests.Session | None = None

    def get_httpx(self) -> httpx.Client:
        if self._ephemeral_httpx is not None:
            return self._ephemeral_httpx
        client, persistent = self._registry.get_or_create_httpx(self._proxy_key)
        if not persistent:
            self._ephemeral_httpx = client
        return client

    def get_curl(self) -> curl_requests.Session:
        if self._ephemeral_curl is not None:
            return self._ephemeral_curl
        session, persistent = self._registry.get_or_create_curl(self._proxy_key)
        if not persistent:
            self._ephemeral_curl = session
        return session

    def close(self) -> None:
        if self._ephemeral_httpx is not None:
            self._ephemeral_httpx.close()
            self._ephemeral_httpx = None
        if self._ephemeral_curl is not None:
            self._ephemeral_curl.close()
            self._ephemeral_curl = None
