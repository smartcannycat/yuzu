from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from apps.integrations.drom.parser import is_antibot_challenge_html
from apps.integrations.drom.schemas import (
    DromBlockedError,
    DromBudgetExhaustedError,
    DromFetchError,
    DromNotFoundError,
)
from apps.integrations.shared.http import (
    BaseScraperClient,
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ResilientHttpSession,
    decode_html_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    import httpx

_DROM_THROTTLE_KEY = "yuzu:drom:throttle"
_MAX_RESPONSE_BYTES = 5_000_000
_DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

_BLOCKED_STATUSES = frozenset({403, 429})
_RETRYABLE_STATUSES = frozenset({500, 502, 503, 504})


class DromHttpClient(BaseScraperClient):
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
        super().__init__(
            domain="drom.ru",
            allowed_hosts=frozenset({"drom.ru"}),
            default_headers=_DEFAULT_HEADERS,
            timeout_sec=timeout_sec,
            request_interval_sec=request_interval_sec,
            request_jitter_sec=request_jitter_sec,
            proxy_ban_sec=proxy_ban_sec,
            proxy_urls=proxy_urls,
            transport=transport,
        )
        self._timeout_sec = timeout_sec
        self._max_retries = max(0, max_retries)
        self._retry_backoff_sec = retry_backoff_sec
        self._request_interval_sec = request_interval_sec
        self._request_jitter_sec = request_jitter_sec
        self._proxy_ban_sec = proxy_ban_sec
        self._transport = transport
        self._budget_deadline: float | None = None

    @contextlib.contextmanager
    def budget(self, budget_sec: float) -> Iterator[None]:
        """Bound a sequence of Drom calls inside one evaluate() run by a shared deadline."""
        previous = self._budget_deadline
        new_deadline = time.monotonic() + max(0.1, budget_sec)
        self._budget_deadline = (
            min(previous, new_deadline) if previous is not None else new_deadline
        )
        try:
            yield
        finally:
            self._budget_deadline = previous

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

    def _sleep_within_deadline(self, delay: float, deadline: float, url: str) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DromBudgetExhaustedError(f"Request budget exhausted for {url}")
        sleep_sec = min(max(0.0, delay), remaining)
        if sleep_sec > 0:
            time.sleep(sleep_sec)
        if delay >= remaining:
            raise DromBudgetExhaustedError(f"Request budget exhausted for {url}")

    def _validate_drom_response(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        url: str,
        *,
        has_multiple_proxies: bool,
        can_retry: bool,
        attempt: int,
        deadline: float,
        check_antibot_html: bool,
    ) -> HttpFetchResponse | None:
        if response.status_code in _BLOCKED_STATUSES:
            session.mark_proxy_blocked(
                response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
            )
            if has_multiple_proxies and can_retry:
                return None
            raise DromBlockedError(f"Drom blocked request ({response.status_code}) for {url}")
        if response.status_code == 404:
            raise DromNotFoundError(f"Drom returned 404 for {url}")
        if response.status_code in _RETRYABLE_STATUSES and can_retry:
            if has_multiple_proxies:
                session.mark_proxy_blocked(
                    response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                )
            else:
                self._sleep_within_deadline(self._retry_backoff_sec * (attempt + 1), deadline, url)
            return None
        if response.status_code >= 400:
            raise DromFetchError(f"Drom HTTP {response.status_code} for {url}")
        if check_antibot_html:
            html = decode_html_bytes(response.content, response.headers)
            if is_antibot_challenge_html(html):
                session.mark_proxy_blocked(
                    response.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                )
                if has_multiple_proxies and can_retry:
                    return None
                raise DromBlockedError(f"Drom вернул anti-bot/CAPTCHA страницу для {response.url}")
        return response

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
                raise DromBudgetExhaustedError(f"Request budget exhausted for {url}")
            can_retry = attempt < total_attempts - 1
            try:
                response = session.get(
                    url,
                    headers=headers,
                    timeout=min(self._timeout_sec, remaining),
                    max_bytes=_MAX_RESPONSE_BYTES,
                    throttle_key=_DROM_THROTTLE_KEY,
                    interval_sec=self._request_interval_sec,
                    jitter_sec=self._request_jitter_sec,
                    deadline=deadline,
                )
            except HttpBudgetExhaustedError as exc:
                raise DromBudgetExhaustedError(f"Request budget exhausted for {url}") from exc
            except HttpTransportError as exc:
                if exc.proxy_key:
                    session.mark_proxy_blocked(
                        exc.proxy_key, domain="drom.ru", cooldown_sec=self._proxy_ban_sec
                    )
                if can_retry:
                    if not has_multiple_proxies:
                        self._sleep_within_deadline(
                            self._retry_backoff_sec * (attempt + 1), deadline, url
                        )
                    continue
                raise DromFetchError(f"Network error requesting {url}: {exc}") from exc

            validated = self._validate_drom_response(
                session,
                response,
                url,
                has_multiple_proxies=has_multiple_proxies,
                can_retry=can_retry,
                attempt=attempt,
                deadline=deadline,
                check_antibot_html=check_antibot_html,
            )
            if validated is not None:
                return validated
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
        per_call_deadline = time.monotonic() + max(self._timeout_sec * total_attempts + 5.0, 15.0)
        deadline = (
            min(per_call_deadline, self._budget_deadline)
            if self._budget_deadline is not None
            else per_call_deadline
        )
        with self._borrow_session(headers) as session:
            return self._execute_request(
                session,
                url,
                headers=headers,
                total_attempts=total_attempts,
                deadline=deadline,
                check_antibot_html=check_antibot_html,
            )
