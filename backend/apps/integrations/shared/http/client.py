"""Resilient HTTP session with SSRF guard, redirect checks, throttling, and proxy pinning."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from apps.integrations.shared.http.pool import (
    SessionClientRegistry,
    SessionClients,
    compute_hop_timeout,
    select_proxy,
)
from apps.integrations.shared.http.redirects import HopRequestState, execute_hop_loop
from apps.integrations.shared.http.throttle import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    RawHttpResponse,
    wait_for_request_slot,
)
from apps.integrations.shared.http.transport import send_curl_request, send_httpx_request
from apps.integrations.shared.proxy import ProxyPool, redact_proxy_url
from apps.integrations.shared.url_guard import UnsafeExternalUrlError, validate_external_url

if TYPE_CHECKING:
    import httpx
    from curl_cffi import requests as curl_requests


class ResilientHttpSession:
    """HTTP session using curl_cffi impersonation in production or httpx in tests."""

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
        self._registry = SessionClientRegistry(
            transport=transport, headers=self._headers, impersonate=impersonate
        )
        self._httpx_clients = self._registry.httpx_clients
        self._proxy_domains: dict[str, str] = {}
        self._last_proxy_key = ""

    @property
    def last_proxy_key(self) -> str:
        return self._last_proxy_key

    def __enter__(self) -> ResilientHttpSession:
        self._registry.in_context = True
        return self

    def __exit__(self, *args: object) -> None:
        self._proxy_domains.clear()
        self._registry.close_all()

    def _effective_domain(self, url: str, domain: str | None = None) -> str | None:
        return domain or self._domain or urlparse(url).hostname

    def drop_proxy_session(self, proxy_key: str) -> None:
        """Close and discard cached client state for ``proxy_key``."""
        self._registry.drop(proxy_key)

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

    def _send_hop(
        self,
        clients: SessionClients,
        state: HopRequestState,
        *,
        hop_timeout: float,
        selected_proxy: str | None,
        resolved_proxy_key: str,
        max_bytes: int | None,
    ) -> RawHttpResponse:
        if self._transport is not None:
            return self._send_httpx(
                clients.get_httpx(),
                state.method,
                state.url,
                params=state.params,
                data=state.data,
                headers=state.headers,
                timeout=hop_timeout,
                proxy=selected_proxy,
                proxy_key=resolved_proxy_key,
                max_bytes=max_bytes,
            )
        return self._send_curl(
            clients.get_curl(),
            state.method,
            state.url,
            params=state.params,
            data=state.data,
            headers=state.headers,
            timeout=hop_timeout,
            proxy=selected_proxy,
            proxy_key=resolved_proxy_key,
            max_bytes=max_bytes,
        )

    def _maybe_throttle(
        self,
        method: str,
        throttle_key: str,
        resolved_proxy_key: str,
        interval_sec: float,
        jitter_sec: float,
        deadline: float | None,
    ) -> None:
        if (
            method == "GET"
            and self._enable_throttle
            and throttle_key
            and (interval_sec > 0 or jitter_sec > 0)
        ):
            scoped_key = f"{throttle_key}:{resolved_proxy_key or 'direct'}"
            wait_for_request_slot(scoped_key, interval_sec, jitter_sec, deadline=deadline)

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
        selected_proxy, resolved_proxy_key = select_proxy(
            self._proxy_rotator, proxy=proxy, proxy_key=proxy_key, domain=effective_domain
        )
        self._last_proxy_key = resolved_proxy_key
        if resolved_proxy_key and effective_domain:
            self._proxy_domains[resolved_proxy_key] = effective_domain

        current_url = self._validate_target_url(url, selected_proxy=selected_proxy, check_dns=False)
        self._maybe_throttle(
            method, throttle_key, resolved_proxy_key, interval_sec, jitter_sec, deadline
        )
        should_check_dns = self._transport is None and not selected_proxy
        if should_check_dns:
            current_url = self._validate_target_url(
                current_url, selected_proxy=selected_proxy, check_dns=True
            )

        state = HopRequestState(method, current_url, params, data, headers)
        clients = SessionClients(self._registry, resolved_proxy_key)
        try:
            return execute_hop_loop(
                original_url=url,
                state=state,
                effective_timeout=effective_timeout,
                deadline=deadline,
                proxy_key=resolved_proxy_key,
                used_proxy=redact_proxy_url(selected_proxy),
                send_hop=lambda hop_state, hop_timeout: self._send_hop(
                    clients,
                    hop_state,
                    hop_timeout=hop_timeout,
                    selected_proxy=selected_proxy,
                    resolved_proxy_key=resolved_proxy_key,
                    max_bytes=max_bytes,
                ),
                compute_timeout=compute_hop_timeout,
                validate_url=lambda target: self._validate_target_url(
                    target, selected_proxy=selected_proxy, check_dns=should_check_dns
                ),
            )
        finally:
            clients.close()

    def _send_httpx(
        self, client: httpx.Client, method: str, url: str, **kwargs: Any
    ) -> RawHttpResponse:
        return send_httpx_request(client, method, url, **kwargs)

    def _send_curl(
        self, session: curl_requests.Session, method: str, url: str, **kwargs: Any
    ) -> RawHttpResponse:
        return send_curl_request(session, method, url, **kwargs)


__all__ = [
    "HttpBudgetExhaustedError",
    "HttpFetchResponse",
    "HttpTransportError",
    "ResilientHttpSession",
]
