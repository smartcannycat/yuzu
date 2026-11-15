import time
from typing import Any
from urllib.parse import urlparse

import httpx

from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromFetchError,
    DromNotFoundError,
)
from apps.lots.integrations.http_client import (
    HttpFetchResponse,
    HttpTransportError,
    ProxyRotator,
    ResilientHttpSession,
    decode_html_bytes,
)

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
        transport: httpx.BaseTransport | None = None,
        proxy_urls: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._timeout_sec = timeout_sec
        self._max_retries = max(0, max_retries)
        self._retry_backoff_sec = retry_backoff_sec
        self._transport = transport
        self._proxy_rotator = ProxyRotator(proxy_urls) if proxy_urls else None

    def get_html(
        self,
        url: str,
        *,
        expected_path_parts: tuple[str, ...] | None = None,
    ) -> str:
        """Fetch an HTML page from Drom, decoding windows-1251/UTF-8 properly."""
        response = self._request(url, headers=_DEFAULT_HEADERS)
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

    def _request(self, url: str, *, headers: dict[str, str]) -> HttpFetchResponse:
        last_error: Exception | None = None
        total_attempts = max(self._max_retries + 1, len(self._proxy_rotator or ()))
        with ResilientHttpSession(
            headers=headers,
            timeout_sec=self._timeout_sec,
            impersonate="chrome",
            proxy_rotator=self._proxy_rotator,
            transport=self._transport,
        ) as session:
            for attempt in range(total_attempts):
                try:
                    response = session.get(url)
                except HttpTransportError as exc:
                    last_error = exc
                    if attempt < total_attempts - 1:
                        time.sleep(self._retry_backoff_sec * (attempt + 1))
                        continue
                    raise DromFetchError(f"Network error requesting {url}: {exc}") from exc

                if response.status_code in _BLOCKED_STATUSES:
                    if self._proxy_rotator and attempt < total_attempts - 1:
                        continue
                    raise DromBlockedError(
                        f"Drom blocked request ({response.status_code}) for {url}"
                    )
                if response.status_code == 404:
                    raise DromNotFoundError(f"Drom returned 404 for {url}")
                if response.status_code in _RETRYABLE_STATUSES and attempt < total_attempts - 1:
                    time.sleep(self._retry_backoff_sec * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise DromFetchError(f"Drom HTTP {response.status_code} for {url}")
                return response

        raise DromFetchError(f"Request failed for {url}: {last_error}")
