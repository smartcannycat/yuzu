from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from apps.lots.integrations.drom.listings_parser import is_antibot_challenge_html
from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromFetchError,
    DromNotFoundError,
)
from apps.lots.integrations.http_client import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ResilientHttpSession,
    decode_html_bytes,
    get_shared_proxy_pool,
)

if TYPE_CHECKING:
    import httpx

_DROM_THROTTLE_KEY = "yuzu:drom:throttle"
_DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

_BLOCKED_STATUSES = frozenset({403, 429})
_RETRYABLE_STATUSES = frozenset({500, 502, 503, 504})


class DromHttpClient:
    """Thin HTTP client for Drom HTML pages and model JSON endpoints."""

    def __init__(
        self,
        *,
        timeout_sec: float = 10.0,
        max_retries: int = 1,
        retry_backoff_sec: float = 0.25,
        request_interval_sec: float = 0.0,
        request_jitter_sec: float = 0.0,
        proxy_ban_sec: float = 120.0,
        transport: httpx.BaseTransport | None = None,
        proxy_urls: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._timeout_sec = timeout_sec
        self._max_retries = max(0, max_retries)
        self._retry_backoff_sec = retry_backoff_sec
        self._request_interval_sec = request_interval_sec
        self._request_jitter_sec = request_jitter_sec
        self._proxy_ban_sec = proxy_ban_sec
        self._transport = transport
        self._proxy_rotator = (
            get_shared_proxy_pool(proxy_urls, ban_cooldown_sec=proxy_ban_sec)
            if proxy_urls
            else None
        )
        self._session: ResilientHttpSession | None = None

    def _build_session(self, headers: dict[str, str] | None = None) -> ResilientHttpSession:
        return ResilientHttpSession(
            headers=headers or _DEFAULT_HEADERS,
            timeout_sec=self._timeout_sec,
            impersonate="chrome",
            domain="drom.ru",
            proxy_rotator=self._proxy_rotator,
            transport=self._transport,
        )

    def __enter__(self) -> DromHttpClient:
        if self._session is None:
            self._session = self._build_session()
            self._session.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._session is not None:
            self._session.__exit__(*args)
            self._session = None

    def get_html(
        self,
        url: str,
        *,
        expected_path_parts: tuple[str, ...] | None = None,
    ) -> str:
        """Fetch an HTML page from Drom, decoding windows-1251/UTF-8 properly."""
        response = self._request(url, headers=_DEFAULT_HEADERS, check_antibot_html=True)
        if expected_path_parts:
            final_path = urlparse(response.url).path.lower()
            if not all(part in final_path for part in expected_path_parts):
                raise DromNotFoundError(
                    f"Drom redirected {url} to {response.url} (missing {expected_path_parts})"
                )
        return decode_html_bytes(response.content, response.headers)

    def get_json(self, url: str) -> dict[str, Any]:
        """Fetch and parse a JSON payload from Drom API endpoints."""
        headers = {**_DEFAULT_HEADERS, "Accept": "application/json"}
        response = self._request(url, headers=headers)
        try:
            payload = response.json()
        except ValueError as exc:
            raise DromFetchError(f"Invalid JSON payload from {url}") from exc
        if not isinstance(payload, dict):
            raise DromFetchError(f"Expected JSON object from {url}")
        return payload

    def _execute_request(
        self,
        session: ResilientHttpSession,
        url: str,
        *,
        headers: dict[str, str],
        total_attempts: int,
        deadline: float,
        check_antibot_html: bool,
    ) -> HttpFetchResponse:
        has_multiple_proxies = bool(self._proxy_rotator and len(self._proxy_rotator) > 1)
        for attempt in range(total_attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DromFetchError(f"Request budget exhausted for {url}")
            try:
                response = session.get(
                    url,
                    headers=headers,
                    timeout=min(self._timeout_sec, remaining),
                    throttle_key=_DROM_THROTTLE_KEY,
                    interval_sec=self._request_interval_sec,
                    jitter_sec=self._request_jitter_sec,
                    deadline=deadline,
                )
            except HttpBudgetExhaustedError as exc:
                raise DromFetchError(f"Request budget exhausted for {url}") from exc
            except HttpTransportError as exc:
                if exc.proxy_key:
                    session.mark_proxy_blocked(
                        exc.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                    )
                if attempt < total_attempts - 1:
                    if not has_multiple_proxies:
                        time.sleep(self._retry_backoff_sec * (attempt + 1))
                    continue
                raise DromFetchError(f"Network error requesting {url}: {exc}") from exc

            if response.status_code in _BLOCKED_STATUSES:
                session.mark_proxy_blocked(
                    response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                )
                if has_multiple_proxies and attempt < total_attempts - 1:
                    continue
                raise DromBlockedError(f"Drom blocked request ({response.status_code}) for {url}")
            if response.status_code == 404:
                raise DromNotFoundError(f"Drom returned 404 for {url}")
            if response.status_code in _RETRYABLE_STATUSES and attempt < total_attempts - 1:
                if has_multiple_proxies:
                    session.mark_proxy_blocked(
                        response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                    )
                else:
                    time.sleep(self._retry_backoff_sec * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise DromFetchError(f"Drom HTTP {response.status_code} for {url}")

            if check_antibot_html:
                html = decode_html_bytes(response.content, response.headers)
                if is_antibot_challenge_html(html):
                    session.mark_proxy_blocked(
                        response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                    )
                    if has_multiple_proxies and attempt < total_attempts - 1:
                        continue
                    raise DromBlockedError(
                        f"Drom вернул anti-bot/CAPTCHA страницу для {response.url}"
                    )
            return response
        raise DromFetchError(f"Unexpected retry termination for {url}")

    def _request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        check_antibot_html: bool = False,
    ) -> HttpFetchResponse:
        max_proxy_attempts = min(len(self._proxy_rotator), 3) if self._proxy_rotator else 1
        total_attempts = max(self._max_retries + 1, max_proxy_attempts)
        deadline = time.monotonic() + max(self._timeout_sec * total_attempts + 5.0, 15.0)
        if self._session is not None:
            return self._execute_request(
                self._session,
                url,
                headers=headers,
                total_attempts=total_attempts,
                deadline=deadline,
                check_antibot_html=check_antibot_html,
            )
        with self._build_session(headers) as session:
            return self._execute_request(
                session,
                url,
                headers=headers,
                total_attempts=total_attempts,
                deadline=deadline,
                check_antibot_html=check_antibot_html,
            )
