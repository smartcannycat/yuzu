"""Shared scraper client session lifecycle for Farpost and Drom adapters."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Self

from apps.integrations.shared.http.client import ResilientHttpSession
from apps.integrations.shared.proxy import get_shared_proxy_pool

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    import httpx


class BaseScraperClient:
    """Manages shared proxy pool and ResilientHttpSession context lifecycle."""

    def __init__(
        self,
        *,
        domain: str,
        allowed_hosts: frozenset[str],
        default_headers: dict[str, str],
        timeout_sec: float = 10.0,
        request_interval_sec: float = 0.0,
        request_jitter_sec: float = 0.0,
        proxy_ban_sec: float = 120.0,
        proxy_urls: Sequence[str] = (),
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._scraper_domain = domain
        self._scraper_allowed_hosts = allowed_hosts
        self._default_headers = dict(default_headers)
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self.request_jitter_sec = request_jitter_sec
        self.proxy_ban_sec = proxy_ban_sec
        self.transport = transport
        self._proxy_rotator = (
            get_shared_proxy_pool(proxy_urls, ban_cooldown_sec=proxy_ban_sec)
            if proxy_urls
            else None
        )
        self._session: ResilientHttpSession | None = None

    def _build_session(self, headers: dict[str, str] | None = None) -> ResilientHttpSession:
        return ResilientHttpSession(
            headers=headers or self._default_headers,
            timeout_sec=self.timeout_sec,
            impersonate="chrome",
            domain=self._scraper_domain,
            allowed_hosts=self._scraper_allowed_hosts,
            proxy_rotator=self._proxy_rotator,
            transport=self.transport,
        )

    def __enter__(self) -> Self:
        if self._session is None:
            self._session = self._build_session()
            self._session.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._session is not None:
            self._session.__exit__(*args)
            self._session = None

    @contextlib.contextmanager
    def _borrow_session(
        self, headers: dict[str, str] | None = None
    ) -> Iterator[ResilientHttpSession]:
        if self._session is not None:
            yield self._session
            return
        with self._build_session(headers) as session:
            yield session
