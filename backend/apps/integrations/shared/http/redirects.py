"""Manual redirect validation and HTTP method mutation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from apps.integrations.shared.http.throttle import (
    HttpFetchResponse,
    HttpTransportError,
    RawHttpResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 5


def strip_body_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    if not headers:
        return headers
    return {k: v for k, v in headers.items() if k.lower() not in {"content-type", "content-length"}}


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
    """Validate redirect target and update method/payload per RFC 9110."""
    if hop >= MAX_REDIRECTS:
        raise HttpTransportError(f"Too many redirects for {original_url}", proxy_key=proxy_key)
    next_url = validate_url(urljoin(response_url or state.url, location))
    if status_code in {301, 302, 303}:
        return HopRequestState(
            method="GET",
            url=next_url,
            params=None,
            data=None,
            headers=strip_body_headers(state.headers),
        )
    return HopRequestState(
        method=state.method,
        url=next_url,
        params=None,
        data=state.data,
        headers=state.headers,
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
