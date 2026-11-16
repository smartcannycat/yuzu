"""HTTP client for Farpost used-parts search with proxy rotation and CAPTCHA handling."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from apps.lots.integrations.captcha.farpost import (
    FarpostCaptchaError,
    FarpostCaptchaSolver,
    is_farpost_challenge_response,
)
from apps.lots.integrations.farpost.parser import (
    FarpostFetchError,
    FarpostRateLimitedError,
    ParseResult,
    PartCriteria,
    PartOffer,
    _matches_paint_code,
    matches_paint_code,
    parse_listing_page,
    parse_offers,
)
from apps.lots.integrations.http_client import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ResilientHttpSession,
    decode_html_bytes,
    get_shared_proxy_pool,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import httpx

__all__ = [
    "FarpostClient",
    "FarpostFetchError",
    "FarpostRateLimitedError",
    "ParseResult",
    "PartCriteria",
    "PartOffer",
    "_matches_paint_code",
    "matches_paint_code",
    "parse_listing_page",
    "parse_offers",
]

_FARPOST_THROTTLE_KEY = "yuzu:farpost:throttle"
_FARPOST_URL = "https://www.farpost.ru/vladivostok/zapchasti/"
_MAX_RESPONSE_BYTES = 3_000_000
_PAGE_SIZE = 50

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3",
}


class _FarpostRetryableError(FarpostFetchError):
    """Transient Farpost HTTP error (5xx) eligible for proxy rotation."""


class FarpostClient:
    """Synchronous Farpost parts-search client with shared ProxyPool and ALTCHA solving."""

    def __init__(
        self,
        *,
        timeout_sec: float = 8.0,
        request_interval_sec: float = 0.0,
        request_jitter_sec: float = 0.0,
        proxy_ban_sec: float = 120.0,
        proxy_urls: Sequence[str] = (),
        transport: httpx.BaseTransport | None = None,
        captcha_solver: FarpostCaptchaSolver | None = None,
        captcha_max_attempts: int = 2,
        captcha_solve_budget_sec: float = 20.0,
        captcha_max_workers: int | None = None,
    ):
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self.request_jitter_sec = request_jitter_sec
        self.proxy_ban_sec = proxy_ban_sec
        self.transport = transport
        self._proxy_rotator = (
            get_shared_proxy_pool(proxy_urls, ban_cooldown_sec=proxy_ban_sec)
            if proxy_urls
            else None
        )
        self._captcha_solver = captcha_solver or FarpostCaptchaSolver(
            max_attempts=captcha_max_attempts,
            solve_budget_sec=captcha_solve_budget_sec,
            max_workers=captcha_max_workers,
            request_timeout_sec=timeout_sec,
        )
        self._session: ResilientHttpSession | None = None

    def _build_session(self) -> ResilientHttpSession:
        return ResilientHttpSession(
            headers=_DEFAULT_HEADERS,
            timeout_sec=self.timeout_sec,
            impersonate="chrome",
            domain="www.farpost.ru",
            allowed_hosts=frozenset({"farpost.ru"}),
            proxy_rotator=self._proxy_rotator,
            transport=self.transport,
        )

    def __enter__(self) -> FarpostClient:
        if self._session is None:
            self._session = self._build_session()
            self._session.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._session is not None:
            self._session.__exit__(*args)
            self._session = None

    def _fetch_html(
        self,
        session: ResilientHttpSession,
        criteria: PartCriteria,
        deadline: float,
        *,
        page: int = 1,
    ) -> tuple[str, str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FarpostFetchError("Farpost search budget exhausted")
        params: dict[str, str | int] = {
            "query": criteria.query,
            "goodPresentState": "present",
            "condition[]": "used",
            "sortBy": "pricea",
        }
        if page > 1:
            params["page"] = page
        response: HttpFetchResponse = session.get(
            _FARPOST_URL,
            params=params,
            timeout=min(self.timeout_sec, remaining),
            max_bytes=_MAX_RESPONSE_BYTES,
            throttle_key=_FARPOST_THROTTLE_KEY,
            interval_sec=self.request_interval_sec,
            jitter_sec=self.request_jitter_sec,
            deadline=deadline,
        )
        if is_farpost_challenge_response(response):
            try:
                response = self._captcha_solver.solve(session, response, deadline=deadline)
            except FarpostCaptchaError as exc:
                raise FarpostRateLimitedError(
                    "Farpost anti-bot verification could not be solved",
                    triggers_global_cooldown=False,
                ) from exc
        if response.status_code in {403, 429}:
            raise FarpostRateLimitedError("Farpost rate limited the request")
        if response.status_code >= 500:
            raise _FarpostRetryableError(f"Farpost returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise FarpostFetchError(f"Farpost returned HTTP {response.status_code}")
        if time.monotonic() > deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        return decode_html_bytes(response.content, response.headers), response.url

    def _fetch_and_parse_page(
        self,
        criteria: PartCriteria,
        *,
        deadline: float,
        page: int = 1,
    ) -> ParseResult:
        max_attempts = min(len(self._proxy_rotator), 3) if self._proxy_rotator else 1
        last_rate_err: FarpostRateLimitedError | None = None
        last_retry_err: _FarpostRetryableError | None = None
        last_transport_err: HttpTransportError | None = None
        for attempt in range(max_attempts):
            active_session = self._session
            try:
                if active_session is not None:
                    html, final_url = self._fetch_html(
                        active_session, criteria, deadline, page=page
                    )
                else:
                    with self._build_session() as session:
                        active_session = session
                        html, final_url = self._fetch_html(session, criteria, deadline, page=page)
                return parse_listing_page(html, criteria, source_url=final_url)
            except HttpBudgetExhaustedError as exc:
                raise FarpostFetchError("Farpost search budget exhausted") from exc
            except (FarpostRateLimitedError, _FarpostRetryableError) as exc:
                if active_session is not None and active_session.last_proxy_key:
                    active_session.mark_proxy_blocked(
                        active_session.last_proxy_key,
                        url=_FARPOST_URL,
                        cooldown_sec=self.proxy_ban_sec,
                    )
                if isinstance(exc, FarpostRateLimitedError):
                    last_rate_err = exc
                else:
                    last_retry_err = exc
                if (
                    self._proxy_rotator
                    and len(self._proxy_rotator) > 1
                    and attempt < max_attempts - 1
                    and deadline - time.monotonic() > 1.0
                ):
                    continue
                raise
            except HttpTransportError as exc:
                if active_session is not None and exc.proxy_key:
                    active_session.mark_proxy_blocked(
                        exc.proxy_key,
                        url=_FARPOST_URL,
                        cooldown_sec=self.proxy_ban_sec,
                    )
                last_transport_err = exc
                if attempt < max_attempts - 1 and deadline - time.monotonic() > 1.0:
                    continue
                raise FarpostFetchError(f"Farpost request failed: {exc}") from exc
        if last_rate_err is not None:
            raise last_rate_err
        if last_retry_err is not None:
            raise last_retry_err
        raise FarpostFetchError(f"Farpost request failed: {last_transport_err}")

    def search_with_metadata(self, criteria: PartCriteria, *, deadline: float) -> ParseResult:
        if time.monotonic() >= deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        result = self._fetch_and_parse_page(criteria, deadline=deadline, page=1)
        if (
            not result.offers
            and result.exact_feed_count is not None
            and result.exact_feed_count > _PAGE_SIZE
            and deadline - time.monotonic() > min(self.timeout_sec, 3.0)
        ):
            try:
                page2 = self._fetch_and_parse_page(criteria, deadline=deadline, page=2)
            except FarpostRateLimitedError:
                raise
            except FarpostFetchError:
                return result
            return ParseResult(
                offers=page2.offers,
                exact_feed_count=result.exact_feed_count,
            )
        return result

    def search(self, criteria: PartCriteria, *, deadline: float) -> list[PartOffer]:
        return self.search_with_metadata(criteria, deadline=deadline).offers
