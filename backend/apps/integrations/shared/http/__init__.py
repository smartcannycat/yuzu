"""Shared HTTP transport helpers using curl_cffi browser impersonation and proxy pool."""

from apps.integrations.shared.http.client import ResilientHttpSession
from apps.integrations.shared.http.throttle import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    clear_local_throttle_state,
    decode_html_bytes,
    wait_for_request_slot,
)
from apps.integrations.shared.proxy import (
    ProxyPool,
    ProxyRotator,
    get_shared_proxy_pool,
    normalize_proxy_urls,
    proxy_fingerprint,
    redact_proxy_url,
    reset_shared_proxy_pools,
    scrub_proxy_credentials,
)

__all__ = [
    "HttpBudgetExhaustedError",
    "HttpFetchResponse",
    "HttpTransportError",
    "ProxyPool",
    "ProxyRotator",
    "ResilientHttpSession",
    "clear_local_throttle_state",
    "decode_html_bytes",
    "get_shared_proxy_pool",
    "normalize_proxy_urls",
    "proxy_fingerprint",
    "redact_proxy_url",
    "reset_shared_proxy_pools",
    "scrub_proxy_credentials",
    "wait_for_request_slot",
]
