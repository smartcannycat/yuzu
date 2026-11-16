"""Low-level curl_cffi and httpx transport senders with size enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from curl_cffi.requests.errors import RequestsError as CurlRequestsError

from apps.integrations.shared.http.throttle import (
    HttpTransportError,
    RawHttpResponse,
    check_content_length,
)
from apps.integrations.shared.proxy import scrub_proxy_credentials

if TYPE_CHECKING:
    from collections.abc import Iterable

    from curl_cffi import requests as curl_requests


def _collect_bounded_chunks(chunks_iter: Iterable[bytes], max_bytes: int | None) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in chunks_iter:
        total += len(chunk)
        if max_bytes is not None and total > max_bytes:
            raise HttpTransportError(f"Response size {total} exceeds limit {max_bytes}")
        chunks.append(chunk)
    return b"".join(chunks)


def _raise_scrubbed_error(
    url: str,
    exc: Exception,
    proxy: str | None,
    proxy_key: str,
) -> None:
    msg, scrubbed = scrub_proxy_credentials(str(exc), proxy)
    err = HttpTransportError(f"Request failed for {url}: {msg}", proxy_key=proxy_key)
    if scrubbed:
        raise err from None
    raise err from exc


def send_httpx_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None,
    data: dict[str, Any] | bytes | None,
    headers: dict[str, str] | None,
    timeout: float,
    proxy: str | None,
    proxy_key: str,
    max_bytes: int | None,
) -> RawHttpResponse:
    """Execute one HTTP hop via injected httpx client transport (used in tests)."""
    kwargs: dict[str, Any] = {"headers": headers, "timeout": timeout}
    if params is not None:
        kwargs["params"] = params
    if data is not None:
        kwargs["data"] = data
    try:
        with client.stream(method, url, **kwargs) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            check_content_length(resp_headers, max_bytes)
            content = _collect_bounded_chunks(resp.iter_bytes(), max_bytes)
            return RawHttpResponse(
                status_code=resp.status_code,
                url=str(resp.url),
                headers=resp_headers,
                content=content,
            )
    except httpx.HTTPError as exc:
        _raise_scrubbed_error(url, exc, proxy, proxy_key)


def send_curl_request(
    session: curl_requests.Session,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None,
    data: dict[str, Any] | bytes | None,
    headers: dict[str, str] | None,
    timeout: float,
    proxy: str | None,
    proxy_key: str,
    max_bytes: int | None,
) -> RawHttpResponse:
    """Execute one HTTP hop via curl_cffi browser-impersonated session."""
    kwargs: dict[str, Any] = {
        "headers": headers,
        "timeout": timeout,
        "allow_redirects": False,
        "stream": True,
    }
    if params is not None:
        kwargs["params"] = params
    if data is not None:
        kwargs["data"] = data
    if proxy:
        kwargs["proxy"] = proxy
    try:
        resp = session.request(method, url, **kwargs)
        try:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            check_content_length(resp_headers, max_bytes)
            if hasattr(resp, "iter_content"):
                content = _collect_bounded_chunks(resp.iter_content(), max_bytes)
            else:
                content = resp.content
                if max_bytes is not None and len(content) > max_bytes:
                    raise HttpTransportError(
                        f"Response size {len(content)} exceeds limit {max_bytes}"
                    )
            return RawHttpResponse(
                status_code=resp.status_code,
                url=str(resp.url),
                headers=resp_headers,
                content=content,
            )
        finally:
            if hasattr(resp, "close"):
                resp.close()
    except CurlRequestsError as exc:
        _raise_scrubbed_error(url, exc, proxy, proxy_key)
