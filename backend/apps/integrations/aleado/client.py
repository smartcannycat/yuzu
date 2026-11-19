"""Synchronous HTTP client for auc.aleado.com with lazy login and throttling.

The site rate-limits aggressive scraping, so every HTTP call goes through
a minimum-interval gate (default 1 request per second). Authorization is
lazy: the first request checks for the "Sign out" marker and, when it is
missing, performs the form login and retries. A transport can be
injected (httpx.MockTransport) for tests.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from apps.core.redis_utils import acquire_distributed_interval_slot
from apps.integrations.aleado import session as aleado_session
from apps.integrations.aleado.parser import (
    AleadoLotDetail,
    AleadoLotRow,
    AleadoParseError,
    parse_lot_detail,
    parse_search_results,
)
from apps.integrations.shared.http.redirects import (
    MAX_REDIRECTS,
    REDIRECT_STATUSES,
    HopRequestState,
    advance_redirect_hop,
)
from apps.integrations.shared.http.throttle import HttpTransportError
from apps.integrations.shared.http.transport import read_bounded_httpx_response
from apps.integrations.shared.url_guard import UnsafeExternalUrlError, validate_external_url

logger = logging.getLogger(__name__)

DEFAULT_ALEADO_BASE_URL = "https://auc.aleado.com"
_SEARCH_PARAMS = aleado_session.FINDLOTS_SEARCH_PARAMS


class AleadoAuthError(RuntimeError):
    """Login to Aleado failed (bad credentials or changed auth flow)."""


class AleadoUnavailableError(RuntimeError):
    """Network failure, timeout or 5xx response from Aleado."""


class AleadoClient:
    """HTTP client for the Aleado auctions site (sync, throttled, process-global)."""

    # Process-wide throttle state: the site rate-limits per account/IP, and
    # the pipeline may run several client instances concurrently (parallel
    # batches, recovery threads), so the interval must be shared.
    _throttle_lock = threading.Lock()
    _global_last_request_at: float | None = None

    # Response size caps: Aleado pages are well under 1 MB; anything larger
    # means a misbehaving or compromised source and must not reach memory.
    _MAX_HTML_BYTES = 3 * 1024 * 1024
    _MAX_IMAGE_BYTES = 1 * 1024 * 1024

    # Only these hosts may be requested for content referenced by parsed HTML
    # (chassis images, photos) -- prevents SSRF via injected URLs or redirects.
    _ALLOWED_CONTENT_HOSTS = frozenset({"p3.aleado.com", "auc.aleado.com"})

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_ALEADO_BASE_URL,
        username: str = "",
        password: str = "",
        timeout_sec: float = 20.0,
        request_interval_sec: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Any = None,
        share_session: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self._sleep = sleep_fn or time.sleep
        self._uses_custom_transport = transport is not None
        self._share_session = (transport is None) if share_session is None else bool(share_session)
        self._session_key = (self.base_url, self.username)
        self._cookie_generation = 0
        self._logged_in = False
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_sec,
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AuctionCalc/1.0)"},
        )
        if self._use_shared_session():
            self._cookie_generation = aleado_session.init_client_cookies(
                self._session_key,
                self._client.cookies,
            )

    @classmethod
    def clear_shared_sessions(cls) -> None:
        """Reset cached process-local Aleado sessions (primarily for test isolation)."""
        aleado_session.clear_shared_sessions()

    def _use_shared_session(self) -> bool:
        return self._share_session and bool(self.username and self.password)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AleadoClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- low-level plumbing -------------------------------------------------

    def _throttle(self) -> None:
        if not self._uses_custom_transport and self.request_interval_sec > 0:
            wait_sec = acquire_distributed_interval_slot(
                "yuzu:aleado:next_request_at",
                self.request_interval_sec,
            )
            if wait_sec is not None:
                if wait_sec > 0:
                    self._sleep(wait_sec)
                return

        sleep_sec = 0.0
        with AleadoClient._throttle_lock:
            now = time.monotonic()
            last = AleadoClient._global_last_request_at
            if last is not None and self.request_interval_sec > 0:
                next_allowed = last + self.request_interval_sec
                if next_allowed > now:
                    sleep_sec = next_allowed - now
                    AleadoClient._global_last_request_at = next_allowed
                else:
                    AleadoClient._global_last_request_at = now
            else:
                AleadoClient._global_last_request_at = now
        if sleep_sec > 0:
            self._sleep(sleep_sec)

    def _validate_url(self, url: str) -> str:
        try:
            return validate_external_url(
                url,
                allowed_hosts=self._ALLOWED_CONTENT_HOSTS,
                check_dns=not self._uses_custom_transport,
            )
        except UnsafeExternalUrlError as exc:
            raise AleadoParseError(f"Blocked unsafe Aleado URL: {exc}") from exc

    def _validate_content_url(self, url: str) -> str:
        """Enforce https + host allowlist for URLs taken from parsed HTML."""
        resolved = urljoin(self.base_url + "/", url) if url.startswith("/") else url
        return self._validate_url(resolved)

    def _send_hop(
        self,
        state: HopRequestState,
        *,
        max_bytes: int,
    ) -> tuple[httpx.Response, bytes | None]:
        req_kwargs: dict[str, Any] = {}
        if state.params is not None:
            req_kwargs["params"] = state.params
        if state.data is not None:
            req_kwargs["data"] = state.data
        if state.headers is not None:
            req_kwargs["headers"] = state.headers

        self._throttle()
        try:
            with self._client.stream(state.method, state.url, **req_kwargs) as resp:
                if resp.status_code >= 500:
                    raise AleadoUnavailableError(f"Aleado returned HTTP {resp.status_code}")
                location = resp.headers.get("location")
                if resp.status_code in REDIRECT_STATUSES and location:
                    return resp, None
                content = read_bounded_httpx_response(
                    resp, max_bytes, error_factory=AleadoUnavailableError
                )
                return resp, content
        except httpx.HTTPError as exc:
            raise AleadoUnavailableError(f"Aleado request failed: {exc}") from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        max_bytes: int | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        full_url = self._validate_url(urljoin(self.base_url + "/", url))
        state = HopRequestState(
            method=method,
            url=full_url,
            params=kwargs.get("params"),
            data=kwargs.get("data"),
            headers=kwargs.get("headers"),
        )
        byte_cap = max_bytes if max_bytes is not None else self._MAX_HTML_BYTES
        for hop in range(MAX_REDIRECTS + 1):
            resp, content = self._send_hop(state, max_bytes=byte_cap)
            if content is not None:
                clean_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in {"content-encoding", "content-length"}
                }
                return httpx.Response(
                    status_code=resp.status_code,
                    headers=clean_headers,
                    content=content,
                    request=resp.request,
                )
            location = resp.headers["location"]
            try:
                state = advance_redirect_hop(
                    hop=hop,
                    original_url=full_url,
                    status_code=resp.status_code,
                    response_url=str(resp.url),
                    location=location,
                    state=state,
                    proxy_key="",
                    validate_url=self._validate_url,
                )
            except HttpTransportError as exc:
                raise AleadoUnavailableError(str(exc)) from exc
        raise AleadoUnavailableError(f"Too many redirects for {full_url}")

    def _bounded_read(self, response: httpx.Response, max_bytes: int) -> bytes:
        length = response.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_bytes:
            raise AleadoUnavailableError(f"Aleado response exceeds the size cap: {length} bytes")
        if hasattr(response, "is_stream_consumed") and not response.is_stream_consumed:
            return read_bounded_httpx_response(
                response, max_bytes, error_factory=AleadoUnavailableError
            )
        content = response.content
        if len(content) > max_bytes:
            raise AleadoUnavailableError(
                f"Aleado response exceeds the size cap: {len(content)} bytes"
            )
        return content

    def _is_authenticated(self, response: httpx.Response) -> bool:
        if "p=auth/login" in str(response.url):
            return False
        return "Sign out" in response.text

    def _login(self) -> None:
        if not self.username or not self.password:
            raise AleadoAuthError("Aleado credentials are not configured")
        response = self._request(
            "POST",
            "/auth/login.php",
            data={"username": self.username, "password": self.password, "Submit": "Login"},
            params={"cur_url": ""},
            max_bytes=self._MAX_HTML_BYTES,
        )
        # A successful login redirects to the cabinet catalog page, which
        # does NOT contain the "Sign out" marker (that shows up on the
        # auctions pages only). A rejected login re-renders the login
        # form itself ("Login to Auctions system" title).
        login_failed = response.status_code >= 400 or "Login to Auctions system" in response.text
        if login_failed:
            raise AleadoAuthError("Aleado login was rejected")
        self._logged_in = True
        logger.info("Aleado login succeeded")

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        if self._use_shared_session():
            self._cookie_generation = aleado_session.ensure_session(
                self._session_key,
                self._cookie_generation,
                self._client.cookies,
                self._login,
            )
        response = self._request("GET", url, **kwargs)
        if not self._is_authenticated(response):
            self._logged_in = False
            if self._use_shared_session():
                self._cookie_generation = aleado_session.reauthenticate(
                    self._session_key,
                    self._cookie_generation,
                    self._client.cookies,
                    self._login,
                )
            else:
                self._login()
            response = self._request("GET", url, **kwargs)
            if not self._is_authenticated(response):
                self._logged_in = False
        return response

    # --- public API ---------------------------------------------------------

    def search_lots(
        self, model_code: str, year: int | None = None, *, max_rows: int = 20
    ) -> list[AleadoLotRow]:
        """Search past and current lots by model type code (and optional year)."""
        params = dict(_SEARCH_PARAMS)
        params["type"] = model_code
        params["rows"] = str(max_rows)
        if year is not None:
            params["year1"] = str(year)
            params["year2"] = str(year)
        response = self._get("/auctions", params=params, max_bytes=self._MAX_HTML_BYTES)
        self._bounded_read(response, self._MAX_HTML_BYTES)
        try:
            _, rows = parse_search_results(response.text)
        except AleadoParseError:
            raise
        return rows[:max_rows]

    def get_lot_detail(self, internal_id: str) -> AleadoLotDetail:
        """Fetch and parse the lot detail page by internal Aleado id."""
        response = self._get(
            "/auctions",
            params={"p": "project/lot", "id": internal_id},
            max_bytes=self._MAX_HTML_BYTES,
        )
        self._bounded_read(response, self._MAX_HTML_BYTES)
        return parse_lot_detail(response.text)

    def fetch_chassis_image(self, detail: AleadoLotDetail) -> bytes:
        """Download the chassis-number image referenced by a lot detail."""
        if not detail.chassis_image_url:
            raise AleadoParseError("Lot detail has no chassis image URL")
        url = self._validate_content_url(detail.chassis_image_url)
        response = self._request("GET", url, max_bytes=self._MAX_IMAGE_BYTES)
        content = self._bounded_read(response, self._MAX_IMAGE_BYTES)
        if not content:
            raise AleadoUnavailableError("Chassis image response is empty")
        return content
