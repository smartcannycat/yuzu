"""FastAPI dependency providers reading service instances from app.state."""

import asyncio
import hmac
import time
from collections import deque

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from ml_service.config import Settings
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.services.batch_parser_service import BatchParserService
from ml_service.services.sheet_parser_service import SheetParserService

API_KEY_HEADER_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
_RATE_WINDOW_SECONDS = 60.0
_MAX_RATE_BUCKETS = 4096


def get_settings_dep(request: Request) -> Settings:
    """Return active application settings stored during app startup."""
    return request.app.state.settings


def require_api_key_dep(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Verify X-API-Key against configured service API keys using constant-time comparison."""
    expected_keys = settings.service_api_keys
    if not expected_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML service API key authentication is not configured.",
        )

    provided_bytes = (api_key or "").strip().encode("utf-8")
    matches = [
        hmac.compare_digest(provided_bytes, expected.encode("utf-8")) for expected in expected_keys
    ]
    if not provided_bytes or not any(matches):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing or invalid {API_KEY_HEADER_NAME} header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def _get_or_init_lock(request: Request, attr_name: str) -> asyncio.Lock:
    lock: asyncio.Lock | None = getattr(request.app.state, attr_name, None)
    if lock is None:
        lock = asyncio.Lock()
        setattr(request.app.state, attr_name, lock)
    return lock


def _get_or_init_buckets(request: Request, attr_name: str) -> dict[str, deque[float]]:
    buckets: dict[str, deque[float]] | None = getattr(request.app.state, attr_name, None)
    if buckets is None:
        buckets = {}
        setattr(request.app.state, attr_name, buckets)
    return buckets


async def _enforce_sliding_window_rate_limit(
    request: Request,
    *,
    limit: int,
    buckets_attr: str,
    lock_attr: str,
) -> None:
    if limit <= 0:
        return

    buckets = _get_or_init_buckets(request, buckets_attr)
    lock = _get_or_init_lock(request, lock_attr)
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SECONDS
    client_host = request.client.host if request.client and request.client.host else "unknown"

    async with lock:
        if len(buckets) >= _MAX_RATE_BUCKETS and client_host not in buckets:
            stale_keys = [
                key for key, stamps in buckets.items() if not stamps or stamps[-1] < cutoff
            ]
            for key in stale_keys:
                buckets.pop(key, None)
            if len(buckets) >= _MAX_RATE_BUCKETS:
                oldest_key = min(buckets, key=lambda k: buckets[k][-1] if buckets[k] else 0.0)
                buckets.pop(oldest_key, None)

        timestamps = buckets.setdefault(client_host, deque())
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        limited = len(timestamps) >= limit
        if not limited:
            timestamps.append(now)

    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit} requests per minute).",
            headers={"Retry-After": "60"},
        )


async def pre_auth_rate_limit_dep(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Enforce lightweight pre-authentication sliding-window RPM limit per client IP."""
    await _enforce_sliding_window_rate_limit(
        request,
        limit=settings.pre_auth_rate_limit_requests_per_minute,
        buckets_attr="_pre_auth_rate_limit_buckets",
        lock_attr="_pre_auth_rate_limit_lock",
    )


async def rate_limit_dep(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Enforce bounded in-memory sliding-window RPM limit per client IP."""
    await _enforce_sliding_window_rate_limit(
        request,
        limit=settings.rate_limit_requests_per_minute,
        buckets_attr="_rate_limit_buckets",
        lock_attr="_rate_limit_lock",
    )


def get_key_pool_dep(request: Request) -> GeminiKeyPool:
    """Return initialized Gemini API key pool stored during app startup."""
    return request.app.state.key_pool


def get_parser_service_dep(request: Request) -> SheetParserService:
    """Return initialized single-sheet parser service stored during app startup."""
    return request.app.state.parser_service


def get_chassis_ocr_client_dep(request: Request):
    """Return initialized chassis OCR client stored during app startup."""
    return request.app.state.chassis_ocr_client


def get_batch_service_dep(request: Request) -> BatchParserService:
    """Return initialized batch parser service stored during app startup."""
    return request.app.state.batch_service
