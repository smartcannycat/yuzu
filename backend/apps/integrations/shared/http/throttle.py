"""Shared request errors, response wrapper, HTML charset decoding, and rate throttling."""

from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apps.core.redis_utils import acquire_distributed_interval_slot

if TYPE_CHECKING:
    from collections.abc import Mapping

_local_throttle_lock = threading.Lock()
_local_next_request_at: dict[str, float] = {}


class HttpTransportError(RuntimeError):
    """Unified network/transport error raised across httpx mock and curl_cffi sessions."""

    def __init__(self, message: str, *, proxy_key: str = "") -> None:
        super().__init__(message)
        self.proxy_key = proxy_key


class HttpBudgetExhaustedError(HttpTransportError):
    """Raised when waiting for the next rate-limit slot would exceed deadline."""


@dataclass(frozen=True)
class RawHttpResponse:
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


def _reserve_local_slot(
    throttle_key: str, interval_sec: float, jitter: float, deadline: float | None
) -> float:
    with _local_throttle_lock:
        now = time.monotonic()
        scheduled = max(now, _local_next_request_at.get(throttle_key, 0.0))
        wait_sec = scheduled - now
        if deadline is not None and now + wait_sec + jitter >= deadline:
            raise HttpBudgetExhaustedError("Request budget exhausted")
        _local_next_request_at[throttle_key] = scheduled + interval_sec
        return wait_sec


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
        wait_sec = _reserve_local_slot(throttle_key, interval_sec, jitter, deadline)
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


def check_content_length(headers: Mapping[str, str], max_bytes: int | None) -> None:
    if max_bytes is None:
        return
    for key, value in headers.items():
        if key.lower() == "content-length" and str(value).isdigit() and int(value) > max_bytes:
            raise HttpTransportError(f"Response size {value} exceeds limit {max_bytes}")
