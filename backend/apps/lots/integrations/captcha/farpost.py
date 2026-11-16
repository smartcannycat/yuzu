"""Farpost anti-bot challenge parsing and submission.

Farpost serves a ``/verify`` page with two possible challenges:

* an ALTCHA proof-of-work widget (the common case), and
* an image code challenge after repeated verification attempts.

The ALTCHA path is fully automated. Image challenges can be handled by an
injected ``ImageCaptchaSolver`` (see ``image.py``) and otherwise fail with
``FarpostCaptchaError`` so the caller can fall back to cached/statistical data.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from apps.lots.integrations.captcha.altcha import (
    AltchaChallenge,
    AltchaError,
    solve_altcha_payload,
)
from apps.lots.integrations.http_client import (
    HttpFetchResponse,
    ResilientHttpSession,
    decode_html_bytes,
)


class FarpostCaptchaError(RuntimeError):
    """The anti-bot page could not be parsed or solved."""


class ImageCaptchaSolver(Protocol):
    """Optional OCR provider for Farpost image-code challenges."""

    def solve(self, image: bytes, *, deadline: float) -> str | None: ...


@dataclass(frozen=True)
class FarpostChallengePage:
    url: str
    form_action: str
    form_fields: dict[str, str]
    challenge_source: str | None = None
    image_url: str | None = None


def is_farpost_challenge_response(response: HttpFetchResponse) -> bool:
    """Return True for Farpost ``/verify`` pages and Bottopotamus headers."""
    if response.status_code in {403, 429}:
        return False
    if urlparse(response.url).path.startswith("/verify"):
        return True
    if str(response.headers.get("x-bottopotamus-verify", "")).lower() == "true":
        return True
    content_type = str(response.headers.get("content-type", "")).lower()
    if "text/html" not in content_type and "html" not in content_type:
        return False
    head = decode_html_bytes(response.content[:200_000], response.headers).casefold()
    return 'id="grecap-form"' in head or "altcha-widget" in head or "вы не робот" in head


def parse_farpost_challenge(html: str, *, page_url: str) -> FarpostChallengePage:
    """Parse a Farpost verification page into the fields needed for submission."""
    soup = BeautifulSoup(html, "html.parser")
    form, section = _find_challenge_form(soup)
    if form is None:
        raise FarpostCaptchaError("Farpost verification page has no challenge form")

    action = str(form.get("action") or page_url)
    form_action = urljoin(page_url, action)
    form_fields: dict[str, str] = {}
    for field in form.find_all("input"):
        name = str(field.get("name") or "")
        if name:
            form_fields[name] = str(field.get("value") or "")

    widget = form.find("altcha-widget") or (section and section.find("altcha-widget"))
    if widget is None:
        widget = soup.find("altcha-widget")
    challenge_source: str | None = None
    if widget is not None:
        challenge_source = (
            str(widget.get("challengeurl") or widget.get("challenge") or "").strip() or None
        )

    image_url: str | None = None
    image = None
    if section is not None:
        image = section.find("img", src=True)
    if image is None:
        image = form.find("img", src=True) or soup.find(
            "img", attrs={"alt": "Изображение для проверки"}
        )
    if image is not None:
        src = str(image.get("src") or "").strip()
        if "i=" in src or not challenge_source:
            image_url = src or None

    if challenge_source is None and image_url is None:
        raise FarpostCaptchaError("Farpost verification page has no recognized challenge")
    return FarpostChallengePage(
        url=page_url,
        form_action=form_action,
        form_fields=form_fields,
        challenge_source=challenge_source,
        image_url=image_url,
    )


def _find_challenge_form(soup: BeautifulSoup) -> tuple[Any | None, Any | None]:
    """Return the visible challenge form and the section that owns its image."""
    form = soup.find("form", id="grecap-form")
    if form is not None:
        return form, form.find_parent("div")
    for section in soup.find_all("div", class_=True):
        classes = section.get("class") or []
        if not any(str(name).startswith("cap") for name in classes):
            continue
        candidate = section.find("form")
        if candidate is None:
            continue
        if section.find("img", src=True) is None and candidate.find("img", src=True) is None:
            continue
        return candidate, section
    for candidate in soup.find_all("form"):
        fields = {str(field.get("name") or "") for field in candidate.find_all("input")}
        if {"s", "t"} <= fields:
            return candidate, candidate.find_parent("div")
    return None, None


class FarpostCaptchaSolver:
    """Solve Farpost verification pages on the session that received them."""

    def __init__(
        self,
        *,
        max_attempts: int = 2,
        solve_budget_sec: float = 20.0,
        max_workers: int | None = None,
        request_timeout_sec: float = 10.0,
        image_solver: ImageCaptchaSolver | None = None,
    ) -> None:
        self.max_attempts = max(1, max_attempts)
        self.solve_budget_sec = max(0.1, solve_budget_sec)
        self.max_workers = max_workers
        self.request_timeout_sec = request_timeout_sec
        self.image_solver = image_solver

    def solve(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        *,
        deadline: float,
    ) -> HttpFetchResponse:
        """Drive the verification form until Farpost returns the target page."""
        current = response
        solve_deadline = min(deadline, time.monotonic() + self.solve_budget_sec)
        for _ in range(self.max_attempts):
            if not is_farpost_challenge_response(current):
                return current
            if time.monotonic() >= solve_deadline:
                raise FarpostCaptchaError("Farpost verification deadline reached")
            html = decode_html_bytes(current.content, current.headers)
            try:
                page = parse_farpost_challenge(html, page_url=current.url)
                if page.challenge_source is not None:
                    current = self._solve_altcha(session, current, page, deadline=solve_deadline)
                elif page.image_url is not None:
                    current = self._solve_image(session, current, page, deadline=solve_deadline)
                else:  # pragma: no cover - parse guarantees one of the two
                    raise FarpostCaptchaError("Unrecognized Farpost challenge")
            except FarpostCaptchaError:
                raise
            except (AltchaError, ValueError, TypeError) as exc:
                raise FarpostCaptchaError(f"Farpost verification failed: {exc}") from exc

        if is_farpost_challenge_response(current):
            raise FarpostCaptchaError("Farpost still requests verification after solving")
        return current

    def _solve_altcha(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        page: FarpostChallengePage,
        *,
        deadline: float,
    ) -> HttpFetchResponse:
        challenge = self._load_challenge(session, response, page, deadline=deadline)
        payload = solve_altcha_payload(
            challenge,
            deadline=deadline,
            max_workers=self.max_workers,
        )
        fields = dict(page.form_fields)
        # The browser keeps the signed token in g-recaptcha-response and lets the
        # ALTCHA widget append a separate "altcha" field with the solution.
        fields["g-recaptcha-response"] = fields.get("g-recaptcha-response") or fields.get("s", "")
        fields["altcha"] = payload
        return self._post(session, response, page, fields, deadline=deadline)

    def _solve_image(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        page: FarpostChallengePage,
        *,
        deadline: float,
    ) -> HttpFetchResponse:
        if self.image_solver is None:
            raise FarpostCaptchaError(
                "Farpost requested an image CAPTCHA but no image solver is configured"
            )
        image_url = urljoin(page.url, page.image_url or "")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FarpostCaptchaError("Farpost verification deadline reached")
        image_response = session.get(
            image_url,
            headers={"Accept": "image/*", "Referer": page.url},
            timeout=min(self.request_timeout_sec, remaining),
            max_bytes=1_000_000,
            deadline=deadline,
            proxy_key=response.proxy_key or None,
        )
        if image_response.status_code != 200:
            raise FarpostCaptchaError(
                f"Farpost CAPTCHA image returned HTTP {image_response.status_code}"
            )
        code = self.image_solver.solve(image_response.content, deadline=deadline)
        if not code:
            raise FarpostCaptchaError("Farpost image CAPTCHA was not recognized")
        fields = dict(page.form_fields)
        fields["g-recaptcha-response"] = code
        fields.pop("altcha", None)
        return self._post(session, response, page, fields, deadline=deadline)

    def _load_challenge(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        page: FarpostChallengePage,
        *,
        deadline: float,
    ) -> AltchaChallenge:
        source = (page.challenge_source or "").strip()
        if not source:
            raise FarpostCaptchaError("Farpost verification page has no ALTCHA challenge")
        if source.startswith("{"):
            try:
                payload = json.loads(source)
            except json.JSONDecodeError as exc:
                raise FarpostCaptchaError("Farpost ALTCHA challenge is not valid JSON") from exc
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FarpostCaptchaError("Farpost verification deadline reached")
            challenge_url = urljoin(page.url, source)
            challenge_response = session.get(
                challenge_url,
                headers={"Accept": "application/json", "Referer": page.url},
                timeout=min(self.request_timeout_sec, remaining),
                max_bytes=256_000,
                deadline=deadline,
                proxy_key=response.proxy_key or None,
            )
            if challenge_response.status_code != 200:
                raise FarpostCaptchaError(
                    f"Farpost ALTCHA endpoint returned HTTP {challenge_response.status_code}"
                )
            try:
                payload = challenge_response.json()
            except ValueError as exc:
                raise FarpostCaptchaError("Farpost ALTCHA response is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise FarpostCaptchaError("Farpost ALTCHA response must be a JSON object")
        return AltchaChallenge.from_payload(payload)

    def _post(
        self,
        session: ResilientHttpSession,
        response: HttpFetchResponse,
        page: FarpostChallengePage,
        fields: dict[str, str],
        *,
        deadline: float,
    ) -> HttpFetchResponse:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FarpostCaptchaError("Farpost verification deadline reached")
        parsed = urlparse(page.url)
        origin = (
            f"{parsed.scheme}://{parsed.netloc}"
            if parsed.scheme and parsed.netloc
            else "https://www.farpost.ru"
        )
        return session.post(
            page.form_action,
            data=fields,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": origin,
                "Referer": page.url,
            },
            timeout=min(self.request_timeout_sec, remaining),
            max_bytes=3_000_000,
            deadline=deadline,
            proxy_key=response.proxy_key or None,
        )
