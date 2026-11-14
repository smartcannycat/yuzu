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
from urllib.parse import urlparse

import httpx

from apps.core.redis_utils import acquire_distributed_interval_slot
from apps.lots.integrations.aleado.parser import (
    AleadoLotDetail,
    AleadoLotRow,
    AleadoParseError,
    parse_lot_detail,
    parse_search_results,
)

logger = logging.getLogger(__name__)

_SEARCH_PARAMS: dict[str, str] = {
    "p": "project/findlots",
    "ld": "",
    "s": "",
    "o": "d",
    "vs": "20",
    "pg": "1",
    "rows": "20",
    "date_check": "1",
    "auction_check": "1",
    "photo_check": "1",
    "company_check": "1",
    "model_check": "1",
    "grade_check": "1",
    "year_check": "1",
    "transmission_check": "1",
    "displacement_check": "1",
    "mileage_check": "1",
    "model_type_check": "1",
    "start_price_check": "1",
    "end_price_check": "1",
    "result_check": "1",
    "scores_check": "1",
    "mrk": "2",
    "exch": "jpy",
    "type_pos": "contains",
}


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
    # (chassis images, photos) -- prevents SSRF via injected URLs.
    _ALLOWED_CONTENT_HOSTS = frozenset({"p3.aleado.com", "auc.aleado.com"})

    def __init__(
        self,
        *,
        base_url: str = "https://auc.aleado.com",
        username: str = "",
        password: str = "",
        timeout_sec: float = 20.0,
        request_interval_sec: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self._sleep = sleep_fn or time.sleep
        self._uses_custom_transport = transport is not None
        self._logged_in = False
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_sec,
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AuctionCalc/1.0)"},
        )

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

        with AleadoClient._throttle_lock:
            last = AleadoClient._global_last_request_at
            if last is not None and self.request_interval_sec > 0:
                elapsed = time.monotonic() - last
                remaining = self.request_interval_sec - elapsed
                if remaining > 0:
                    self._sleep(remaining)
            AleadoClient._global_last_request_at = time.monotonic()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._throttle()
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise AleadoUnavailableError(f"Aleado request failed: {exc}") from exc
        if response.status_code >= 500:
            raise AleadoUnavailableError(f"Aleado returned HTTP {response.status_code}")
        return response

    def _validate_content_url(self, url: str) -> str:
        """Enforce https + host allowlist for URLs taken from parsed HTML.

        Page markup is untrusted third-party content; without this check a
        crafted ``chassis``/``photo`` URL would make the backend fetch
        arbitrary hosts (SSRF, including internal network addresses).
        """
        if url.startswith("/"):
            url = self.base_url + url
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self._ALLOWED_CONTENT_HOSTS:
            raise AleadoParseError(f"Blocked non-allowlisted content URL: {parsed.hostname!r}")
        return url

    def _bounded_read(self, response: httpx.Response, max_bytes: int) -> bytes:
        length = response.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_bytes:
            raise AleadoUnavailableError(f"Aleado response exceeds the size cap: {length} bytes")
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
        response = self._request("GET", url, **kwargs)
        if not self._logged_in and not self._is_authenticated(response):
            self._login()
            response = self._request("GET", url, **kwargs)
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
        response = self._get("/auctions", params=params)
        self._bounded_read(response, self._MAX_HTML_BYTES)
        try:
            _, rows = parse_search_results(response.text)
        except AleadoParseError:
            raise
        return rows[:max_rows]

    def get_lot_detail(self, internal_id: str) -> AleadoLotDetail:
        """Fetch and parse the lot detail page by internal Aleado id."""
        response = self._get("/auctions", params={"p": "project/lot", "id": internal_id})
        self._bounded_read(response, self._MAX_HTML_BYTES)
        return parse_lot_detail(response.text)

    def fetch_chassis_image(self, detail: AleadoLotDetail) -> bytes:
        """Download the chassis-number image referenced by a lot detail."""
        if not detail.chassis_image_url:
            raise AleadoParseError("Lot detail has no chassis image URL")
        url = self._validate_content_url(detail.chassis_image_url)
        response = self._request("GET", url)
        content = self._bounded_read(response, self._MAX_IMAGE_BYTES)
        if not content:
            raise AleadoUnavailableError("Chassis image response is empty")
        return content
