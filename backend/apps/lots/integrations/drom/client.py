import time
from typing import Any

import httpx

from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromFetchError,
    DromNotFoundError,
)

_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
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
    ) -> None:
        self._timeout_sec = timeout_sec
        self._max_retries = max(0, max_retries)
        self._retry_backoff_sec = retry_backoff_sec
        self._transport = transport

    def get_html(
        self,
        url: str,
        *,
        expected_path_parts: tuple[str, ...] | None = None,
    ) -> str:
        """Fetch an HTML page from Drom, decoding windows-1251/UTF-8 properly."""
        response = self._request(url, headers=_DEFAULT_HEADERS)
        if expected_path_parts:
            final_path = response.url.path.lower()
            if not all(part in final_path for part in expected_path_parts):
                raise DromNotFoundError(
                    f"Drom redirected {url} to {response.url} (missing {expected_path_parts})"
                )
        encoding = _detect_charset(response)
        return response.content.decode(encoding, errors="replace")

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

    def _request(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(
                    timeout=self._timeout_sec,
                    headers=headers,
                    follow_redirects=True,
                    transport=self._transport,
                ) as client:
                    response = client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff_sec * (attempt + 1))
                    continue
                raise DromFetchError(f"Network error requesting {url}: {exc}") from exc

            if response.status_code in _BLOCKED_STATUSES:
                raise DromBlockedError(f"Drom blocked request ({response.status_code}) for {url}")
            if response.status_code == 404:
                raise DromNotFoundError(f"Drom returned 404 for {url}")
            if response.status_code in _RETRYABLE_STATUSES and attempt < self._max_retries:
                time.sleep(self._retry_backoff_sec * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise DromFetchError(f"Drom HTTP {response.status_code} for {url}")
            return response

        raise DromFetchError(f"Request failed for {url}: {last_error}")


def _detect_charset(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    if "windows-1251" in content_type or "cp1251" in content_type:
        return "cp1251"
    if "utf-8" in content_type:
        return "utf-8"
    head = response.content[:1024].decode("ascii", errors="ignore").lower()
    if "windows-1251" in head or "cp1251" in head:
        return "cp1251"
    return "utf-8"
