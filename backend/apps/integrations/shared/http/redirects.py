"""Manual redirect validation and HTTP method mutation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

from apps.integrations.shared.http.throttle import (
    HttpFetchResponse,
    HttpTransportError,
    RawHttpResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 5
_BODY_HEADERS = frozenset({"content-type", "content-length"})
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "x-api-key", "proxy-authorization"})


def _url_origin(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").rstrip(".").lower()
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None:
        port = 443 if scheme == "https" else (80 if scheme == "http" else None)
    netloc = f"{host}:{port}" if port is not None else parsed.netloc.lower()
    return scheme, netloc


def _filter_headers(headers: dict[str, str] | None, drop: frozenset[str]) -> dict[str, str] | None:
    if not headers or not drop:
        return headers
    return {k: v for k, v in headers.items() if k.lower() not in drop}


def strip_body_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    return _filter_headers(headers, _BODY_HEADERS)


@dataclass
class HopRequestState:
    """Mutable request state across manual redirect hops."""

    method: str
    url: str
    params: dict[str, Any] | None
    data: dict[str, Any] | bytes | None
    headers: dict[str, str] | None


def advance_redirect_hop(
    *,
    hop: int,
    original_url: str,
    status_code: int,
    response_url: str,
    location: str,
    state: HopRequestState,
    proxy_key: str,
    validate_url: Callable[[str], str],
) -> HopRequestState:
    """Validate redirect target and update method/payload/headers per RFC 9110."""
    if hop >= MAX_REDIRECTS:
        raise HttpTransportError(f"Too many redirects for {original_url}", proxy_key=proxy_key)
    current_url = response_url or state.url
    next_url = validate_url(urljoin(current_url, location))
    cross_origin = _url_origin(current_url) != _url_origin(next_url)

    if status_code in {307, 308}:
        if cross_origin and (state.data is not None or state.method.upper() not in {"GET", "HEAD"}):
            raise HttpTransportError(
                f"Blocked cross-origin {status_code} redirect with request body for {original_url}",
                proxy_key=proxy_key,
            )
        drop = _SENSITIVE_HEADERS if cross_origin else frozenset()
        headers = _filter_headers(state.headers, drop)
        return HopRequestState(
            method=state.method,
            url=next_url,
            params=None,
            data=state.data,
            headers=headers,
        )

    drop_headers = _BODY_HEADERS | (_SENSITIVE_HEADERS if cross_origin else frozenset())
    return HopRequestState(
        method="GET",
        url=next_url,
        params=None,
        data=None,
        headers=_filter_headers(state.headers, drop_headers),
    )


def execute_hop_loop(
    *,
    original_url: str,
    state: HopRequestState,
    effective_timeout: float,
    deadline: float | None,
    proxy_key: str,
    used_proxy: str,
    send_hop: Callable[[HopRequestState, float], RawHttpResponse],
    compute_timeout: Callable[[float, float | None], float],
    validate_url: Callable[[str], str],
) -> HttpFetchResponse:
    """Execute HTTP hops across manual redirects with per-hop SSRF validation."""
    for hop in range(MAX_REDIRECTS + 1):
        hop_timeout = compute_timeout(effective_timeout, deadline)
        response = send_hop(state, hop_timeout)
        location = response.headers.get("location")
        if response.status_code in REDIRECT_STATUSES and location:
            state = advance_redirect_hop(
                hop=hop,
                original_url=original_url,
                status_code=response.status_code,
                response_url=response.url,
                location=location,
                state=state,
                proxy_key=proxy_key,
                validate_url=validate_url,
            )
            continue
        return HttpFetchResponse(
            status_code=response.status_code,
            url=response.url,
            headers=response.headers,
            content=response.content,
            used_proxy=used_proxy,
            proxy_key=proxy_key,
        )
    raise HttpTransportError(f"Too many redirects for {original_url}", proxy_key=proxy_key)
