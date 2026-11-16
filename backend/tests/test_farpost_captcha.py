"""ALTCHA and Farpost anti-bot verification tests."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import shutil
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from PIL import Image, ImageDraw

from apps.integrations.captcha.altcha import (
    AltchaChallenge,
    AltchaError,
    AltchaSolveTimeoutError,
    AltchaUnsupportedAlgorithmError,
    build_altcha_payload,
    solve_altcha,
    solve_altcha_payload,
)
from apps.integrations.captcha.farpost import (
    FarpostCaptchaError,
    FarpostCaptchaSolver,
    is_farpost_challenge_response,
    parse_farpost_challenge,
)
from apps.integrations.captcha.image import TesseractImageCaptchaSolver
from apps.integrations.farpost.client import (
    FarpostClient,
    FarpostRateLimitedError,
    PartCriteria,
)
from apps.integrations.shared.http import (
    HttpFetchResponse,
    proxy_fingerprint,
    reset_shared_proxy_pools,
)

VERIFY_URL = "https://www.farpost.ru/verify?u=%2Fvladivostok%2Fzapchasti%2F%3Fquery%3Dtest"
TARGET_URL = "https://www.farpost.ru/vladivostok/zapchasti/?query=Toyota+Corolla+NRE210"
CRITERIA = PartCriteria(
    "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", "070"
)


def _sha_challenge(*, counter: int = 3, prefix_hex_length: int = 4) -> dict:
    nonce = bytes.fromhex("00112233445566778899aabbccddeeff")
    salt = bytes.fromhex("ffeeddccbbaa99887766554433221100")
    digest = hashlib.sha256(salt + nonce + counter.to_bytes(4, "big")).digest()
    prefix = digest.hex()[:prefix_hex_length]
    while any(
        hashlib.sha256(salt + nonce + value.to_bytes(4, "big")).hexdigest().startswith(prefix)
        for value in range(counter)
    ):
        counter += 1
        digest = hashlib.sha256(salt + nonce + counter.to_bytes(4, "big")).digest()
        prefix = digest.hex()[:prefix_hex_length]
    return {
        "parameters": {
            "algorithm": "SHA-256",
            "cost": 1,
            "keyLength": 32,
            "keyPrefix": prefix,
            "nonce": nonce.hex(),
            "salt": salt.hex(),
        },
        "signature": "test-signature",
    }


def _legacy_challenge() -> tuple[dict, int]:
    salt = "legacy?expires=9999999999&"
    number = 137
    challenge = hashlib.sha512((salt + str(number)).encode()).hexdigest()
    return (
        {
            "algorithm": "SHA-512",
            "challenge": challenge,
            "maxnumber": 1000,
            "salt": salt,
            "signature": "legacy-signature",
        },
        number,
    )


def _listing_html() -> str:
    return """<html><title>Автозапчасти</title>
    <input name="goodPresentState" value="present" checked>
    <div class="bull-item" data-good-id="123">
    <a data-role="bulletin-link" href="/vladivostok/zapchasti/door-123.html">
    Дверь передняя левая Toyota Corolla NRE210 цвет 070</a>
    <div class="bull-item__annotation">Контрактная деталь</div>
    <div class="price-block__final-price"><div data-role="price">18 000₽</div></div>
    </div></html>"""


def _altcha_page(payload: dict, *, s: str = "signed-token") -> str:
    challenge = html.escape(json.dumps(payload), quote=True)
    return f"""<html><head><title>Вы не робот?</title></head><body>
    <form id="grecap-form" method="POST" action="/verify?u=test&f=3">
      <input type="hidden" name="s" value="{s}">
      <input type="hidden" name="t" value="1794793478613">
      <altcha-widget language="ru" challenge="{challenge}"></altcha-widget>
      <input type="hidden" name="g-recaptcha-response" value="{s}">
    </form></body></html>"""


def _altcha_page_with_url(*, s: str = "signed-token") -> str:
    return f"""<html><head><title>Вы не робот?</title></head><body>
    <form id="grecap-form" method="POST" action="/verify?u=test&amp;f=3">
      <input type="hidden" name="s" value="{s}">
      <input type="hidden" name="t" value="1794793478613">
      <altcha-widget language="ru" challengeurl="?u=test&amp;a=1794793478613">
      </altcha-widget>
      <input type="hidden" name="g-recaptcha-response" value="{s}">
    </form></body></html>"""


def _image_page() -> str:
    return """<html><head><title>Вы не робот?</title></head><body>
    <div class="cap4"><div>
      <p>Введите символы, чтобы продолжить.</p>
      <img alt="Изображение для проверки" src="?u=test&amp;f=1&amp;i=image-token">
      <form method="POST" action="/verify?u=test&amp;f=1">
        <input type="hidden" name="s" value="image-token">
        <input type="hidden" name="t" value="1794793478613">
        <input type="text" name="g-recaptcha-response">
      </form>
    </div></div></body></html>"""


def test_solves_legacy_full_digest_challenge():
    payload, number = _legacy_challenge()
    challenge = AltchaChallenge.from_payload(payload)
    solution = solve_altcha(challenge, max_workers=2)
    assert solution.counter == number

    encoded = build_altcha_payload(challenge, solution)
    decoded = json.loads(base64.b64decode(encoded))
    assert decoded["number"] == str(number)
    assert decoded["salt"] == payload["salt"]
    assert decoded["challenge"] == payload["challenge"]


def test_solves_modern_sha_prefix_challenge_and_builds_v2_payload():
    payload = _sha_challenge(counter=5)
    challenge = AltchaChallenge.from_payload(payload)
    solution = solve_altcha(challenge, max_workers=2)
    assert solution.derived_key.startswith(payload["parameters"]["keyPrefix"])

    encoded = solve_altcha_payload(challenge, max_workers=2)
    decoded = json.loads(base64.b64decode(encoded))
    assert decoded["challenge"]["parameters"] == payload["parameters"]
    assert decoded["solution"]["counter"] == solution.counter
    assert decoded["solution"]["derivedKey"] == solution.derived_key


def test_solves_pbkdf2_and_argon2id_challenges():
    nonce = bytes.fromhex("00112233445566778899aabbccddeeff")
    salt = bytes.fromhex("ffeeddccbbaa99887766554433221100")

    def pbkdf2_digest(counter: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", nonce + counter.to_bytes(4, "big"), salt, 10, dklen=32)

    pbkdf2_counter = 2
    pbkdf2_prefix = pbkdf2_digest(pbkdf2_counter).hex()[:8]
    while any(
        pbkdf2_digest(value).hex().startswith(pbkdf2_prefix) for value in range(pbkdf2_counter)
    ):
        pbkdf2_counter += 1
        pbkdf2_prefix = pbkdf2_digest(pbkdf2_counter).hex()[:8]
    pbkdf2 = _sha_challenge()
    pbkdf2["parameters"].update(
        {
            "algorithm": "PBKDF2/SHA-256",
            "cost": 10,
            "keyPrefix": pbkdf2_prefix,
            "nonce": nonce.hex(),
            "salt": salt.hex(),
        }
    )
    assert solve_altcha(AltchaChallenge.from_payload(pbkdf2), max_workers=2).counter == (
        pbkdf2_counter
    )

    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

    def argon_digest(counter: int) -> bytes:
        return Argon2id(salt=salt, length=32, iterations=1, lanes=1, memory_cost=64).derive(
            nonce + counter.to_bytes(4, "big")
        )

    argon_counter = 1
    argon_prefix = argon_digest(argon_counter).hex()[:4]
    while any(argon_digest(value).hex().startswith(argon_prefix) for value in range(argon_counter)):
        argon_counter += 1
        argon_prefix = argon_digest(argon_counter).hex()[:4]
    argon = {
        "parameters": {
            "algorithm": "argon2id",
            "cost": 1,
            "memoryCost": 64,
            "parallelism": 1,
            "keyLength": 32,
            "keyPrefix": argon_prefix,
            "nonce": nonce.hex(),
            "salt": salt.hex(),
        },
        "signature": "argon-signature",
    }
    assert solve_altcha(AltchaChallenge.from_payload(argon), max_workers=1).counter == (
        argon_counter
    )


def test_unsupported_algorithm_and_exhausted_range_are_errors():
    with pytest.raises(AltchaUnsupportedAlgorithmError):
        AltchaChallenge.from_payload({"algorithm": "scrypt", "challenge": "00", "salt": "x"})

    challenge = AltchaChallenge.from_payload(
        {
            "algorithm": "SHA-256",
            "challenge": "ff" * 32,
            "maxnumber": 1,
            "salt": "never-matches",
        }
    )
    with pytest.raises(AltchaSolveTimeoutError):
        solve_altcha(challenge, max_workers=1)


def test_altcha_page_parsing_and_challenge_url_resolution():
    payload = _sha_challenge()
    page = parse_farpost_challenge(_altcha_page_with_url(), page_url=VERIFY_URL)
    assert page.challenge_source == "?u=test&a=1794793478613"
    assert page.form_fields["s"] == "signed-token"
    assert page.form_fields["g-recaptcha-response"] == "signed-token"

    parsed = parse_farpost_challenge(_altcha_page(payload), page_url=VERIFY_URL)
    assert parsed.challenge_source is not None
    assert json.loads(parsed.challenge_source) == payload


def test_image_page_parsing_pairs_form_with_its_own_image():
    page = parse_farpost_challenge(_image_page(), page_url=VERIFY_URL)
    assert page.image_url and "i=image-token" in page.image_url
    assert page.form_fields["s"] == "image-token"


def test_farpost_client_solves_altcha_and_reuses_signed_grecaptcha_field():
    payload = _sha_challenge(counter=5)
    s_token = "signed-token"
    listing = _listing_html()
    seen_posts: list[dict[str, list[str]]] = []
    challenged = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal challenged
        if request.method == "GET" and request.url.path == "/vladivostok/zapchasti/":
            if not challenged:
                challenged = True
                return httpx.Response(302, headers={"Location": VERIFY_URL})
            return httpx.Response(200, text=listing)
        if request.method == "GET":
            if request.url.params.get("a"):
                return httpx.Response(200, json=payload)
            return httpx.Response(200, text=_altcha_page_with_url(s=s_token))
        if request.method == "POST":
            seen_posts.append(parse_qs(request.content.decode()))
            return httpx.Response(302, headers={"Location": TARGET_URL})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = FarpostClient(transport=httpx.MockTransport(handler))
    offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert offers[0].price_rub == 18000
    assert seen_posts
    posted = seen_posts[0]
    assert posted["s"] == [s_token]
    assert posted["g-recaptcha-response"] == [s_token]
    solution = json.loads(base64.b64decode(posted["altcha"][0]))
    assert solution["solution"]["derivedKey"].startswith(payload["parameters"]["keyPrefix"])


def test_farpost_client_falls_back_when_image_captcha_has_no_solver():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if request.url.path == "/vladivostok/zapchasti/":
                return httpx.Response(302, headers={"Location": VERIFY_URL})
            return httpx.Response(200, text=_image_page())
        raise AssertionError("POST must not happen without an image solver")

    client = FarpostClient(transport=httpx.MockTransport(handler))
    with pytest.raises(FarpostRateLimitedError):
        client.search(CRITERIA, deadline=time.monotonic() + 20)


def test_image_solver_can_complete_the_verification_flow():
    listing = _listing_html()
    seen_codes: list[str] = []
    challenged = False

    class FakeImageSolver:
        def solve(self, image: bytes, *, deadline: float) -> str:
            assert image == b"png-bytes"
            return "1234"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal challenged
        if request.method == "GET" and "i=image-token" in str(request.url):
            return httpx.Response(200, content=b"png-bytes")
        if request.method == "GET" and request.url.path == "/vladivostok/zapchasti/":
            if not challenged:
                challenged = True
                return httpx.Response(302, headers={"Location": VERIFY_URL})
            return httpx.Response(200, text=listing)
        if request.method == "GET":
            if request.url.path == "/verify":
                return httpx.Response(200, text=_image_page())
            return httpx.Response(200, text=listing)
        if request.method == "POST":
            seen_codes.append(parse_qs(request.content.decode())["g-recaptcha-response"][0])
            return httpx.Response(302, headers={"Location": TARGET_URL})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    solver = FarpostCaptchaSolver(image_solver=FakeImageSolver())
    client = FarpostClient(transport=httpx.MockTransport(handler), captcha_solver=solver)
    offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert seen_codes == ["1234"]


def test_challenge_detection_accepts_verify_path_and_bottopotamus_header():
    path_response = HttpFetchResponse(
        200, "https://www.farpost.ru/verify?u=x", {"content-type": "text/html"}, b""
    )
    assert is_farpost_challenge_response(path_response)
    header_response = HttpFetchResponse(
        200,
        "https://www.farpost.ru/page",
        {"x-bottopotamus-verify": "true", "content-type": "text/html"},
        b"",
    )
    assert is_farpost_challenge_response(header_response)
    listing_response = HttpFetchResponse(
        200, TARGET_URL, {"content-type": "text/html"}, b"<html>parts</html>"
    )
    assert not is_farpost_challenge_response(listing_response)


def test_solver_rejects_page_without_recognized_challenge():
    with pytest.raises(FarpostCaptchaError):
        parse_farpost_challenge("<html><title>Вы не робот?</title></html>", page_url=VERIFY_URL)
    with pytest.raises(FarpostCaptchaError):
        parse_farpost_challenge(
            '<html><form><input name="s" value="a"><input name="t" value="b"></form></html>',
            page_url=VERIFY_URL,
        )


def test_solves_v2_sha384_and_sha512_with_cost_and_odd_length_prefix():
    nonce = bytes.fromhex("00112233445566778899aabbccddeeff")
    salt = bytes.fromhex("ffeeddccbbaa99887766554433221100")

    def chained_digest(algo: str, counter: int, cost: int, key_len: int) -> bytes:
        digest = hashlib.new(algo, salt + nonce + counter.to_bytes(4, "big")).digest()[:key_len]
        for _ in range(cost - 1):
            digest = hashlib.new(algo, digest).digest()[:key_len]
        return digest

    for algo_name, hashlib_name, key_len in [("SHA-384", "sha384", 48), ("SHA-512", "sha512", 64)]:
        counter = 2
        odd_prefix = chained_digest(hashlib_name, counter, 3, key_len).hex()[:7]
        while any(
            chained_digest(hashlib_name, value, 3, key_len).hex().startswith(odd_prefix)
            for value in range(counter)
        ):
            counter += 1
            odd_prefix = chained_digest(hashlib_name, counter, 3, key_len).hex()[:7]

        payload = {
            "parameters": {
                "algorithm": algo_name,
                "cost": 3,
                "keyLength": key_len,
                "keyPrefix": odd_prefix,
                "nonce": nonce.hex(),
                "salt": salt.hex(),
            },
            "signature": "sig",
        }
        challenge = AltchaChallenge.from_payload(payload)
        solution = solve_altcha(challenge, max_workers=0)
        assert solution.counter == counter
        assert solution.derived_key.startswith(odd_prefix)
        assert solution.derived_key == chained_digest(hashlib_name, counter, 3, key_len).hex()


def test_altcha_validation_errors_and_deadline_timeout():
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload(["not-a-mapping"])  # type: ignore[arg-type]
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload({"algorithm": "SHA-256", "challenge": "not-hex", "salt": "x"})
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload({"algorithm": "SHA-256", "challenge": "", "salt": "x"})
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload(
            {"algorithm": "SHA-256", "challenge": "00" * 32, "maxnumber": "bad", "salt": "x"}
        )
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload(
            {
                "parameters": {
                    "algorithm": "SHA-256",
                    "keyPrefix": "zzzz",
                    "nonce": "0011",
                    "salt": "2233",
                }
            }
        )
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload(
            {
                "parameters": {
                    "algorithm": "SHA-256",
                    "keyPrefix": "00",
                    "nonce": "not-hex",
                    "salt": "2233",
                }
            }
        )
    with pytest.raises(AltchaError):
        AltchaChallenge.from_payload(
            {
                "parameters": {
                    "algorithm": "SHA-256",
                    "keyPrefix": "00",
                    "nonce": "",
                    "salt": "2233",
                }
            }
        )

    challenge = AltchaChallenge.from_payload(_sha_challenge(counter=5))
    with pytest.raises(AltchaSolveTimeoutError, match="deadline"):
        solve_altcha(challenge, deadline=time.monotonic() - 1.0, max_workers=1)


def test_farpost_client_solves_inline_altcha_challenge():
    payload = _sha_challenge(counter=4)
    listing = _listing_html()
    posted_altcha: list[str] = []
    challenged = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal challenged
        if request.method == "GET" and request.url.path == "/vladivostok/zapchasti/":
            if not challenged:
                challenged = True
                return httpx.Response(302, headers={"Location": VERIFY_URL})
            return httpx.Response(200, text=listing)
        if request.method == "GET" and request.url.path == "/verify":
            return httpx.Response(200, text=_altcha_page(payload, s="inline-token"))
        if request.method == "POST" and request.url.path == "/verify":
            posted_altcha.append(parse_qs(request.content.decode())["altcha"][0])
            return httpx.Response(302, headers={"Location": TARGET_URL})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = FarpostClient(transport=httpx.MockTransport(handler))
    offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert len(posted_altcha) == 1
    decoded = json.loads(base64.b64decode(posted_altcha[0]))
    assert decoded["solution"]["derivedKey"].startswith(payload["parameters"]["keyPrefix"])


def test_farpost_client_escalates_from_altcha_to_image_captcha():
    payload = _sha_challenge(counter=3)
    listing = _listing_html()
    steps: list[str] = []

    class FakeImageSolver:
        def solve(self, image: bytes, *, deadline: float) -> str:
            assert image == b"img-bytes"
            return "9876"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/vladivostok/zapchasti/":
            if not steps:
                steps.append("initial")
                return httpx.Response(302, headers={"Location": VERIFY_URL})
            steps.append("listing")
            return httpx.Response(200, text=listing)
        if request.method == "GET" and request.url.path == "/verify":
            if "a" in request.url.params:
                steps.append("altcha_json")
                return httpx.Response(200, json=payload)
            if "i" in request.url.params:
                steps.append("image_fetch")
                return httpx.Response(200, content=b"img-bytes")
            steps.append("altcha_page")
            return httpx.Response(200, text=_altcha_page_with_url())
        if request.method == "POST":
            form = parse_qs(request.content.decode())
            if "altcha" in form:
                steps.append("post_altcha_escalated")
                return httpx.Response(200, text=_image_page())
            steps.append("post_image")
            assert form["g-recaptcha-response"] == ["9876"]
            return httpx.Response(302, headers={"Location": TARGET_URL})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    solver = FarpostCaptchaSolver(max_attempts=2, image_solver=FakeImageSolver())
    client = FarpostClient(transport=httpx.MockTransport(handler), captcha_solver=solver)
    offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert steps == [
        "initial",
        "altcha_page",
        "altcha_json",
        "post_altcha_escalated",
        "image_fetch",
        "post_image",
        "listing",
    ]


def test_farpost_captcha_exhaustion_and_endpoint_errors_quarantine_proxy(monkeypatch):
    monkeypatch.setattr("apps.integrations.shared.proxy.get_redis_client", lambda: None)
    reset_shared_proxy_pools()
    payload = _sha_challenge(counter=2)
    listing = _listing_html()

    # 1. Still challenged after max_attempts -> quarantines p1, succeeds on p2.
    calls = 0

    def exhausted_then_ok(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200, text=_altcha_page(payload), headers={"x-bottopotamus-verify": "true"}
            )
        if request.method == "POST":
            return httpx.Response(200, text=_altcha_page(payload))
        return httpx.Response(200, text=listing)

    client = FarpostClient(
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        proxy_ban_sec=60.0,
        captcha_max_attempts=1,
        transport=httpx.MockTransport(exhausted_then_ok),
    )
    with client:
        assert len(client.search(CRITERIA, deadline=time.monotonic() + 20)) == 1
        assert client._proxy_rotator is not None
        assert client._proxy_rotator.is_quarantined("http://p1:8080", domain="www.farpost.ru")

    reset_shared_proxy_pools()

    # 2. challengeurl returning HTTP 500 or invalid JSON triggers FarpostRateLimitedError.
    def bad_challenge_endpoint(request: httpx.Request) -> httpx.Response:
        if "a=" in str(request.url):
            return httpx.Response(500, text="error")
        return httpx.Response(200, text=_altcha_page_with_url())

    failing_client = FarpostClient(transport=httpx.MockTransport(bad_challenge_endpoint))
    with pytest.raises(FarpostRateLimitedError):
        failing_client.search(CRITERIA, deadline=time.monotonic() + 20)

    def bad_json_endpoint(request: httpx.Request) -> httpx.Response:
        if "a=" in str(request.url):
            return httpx.Response(200, text="{broken-json")
        return httpx.Response(200, text=_altcha_page_with_url())

    json_failing_client = FarpostClient(transport=httpx.MockTransport(bad_json_endpoint))
    with pytest.raises(FarpostRateLimitedError):
        json_failing_client.search(CRITERIA, deadline=time.monotonic() + 20)


def test_farpost_client_pins_same_proxy_and_cookies_during_captcha_solve(monkeypatch):
    monkeypatch.setattr("apps.integrations.shared.proxy.get_redis_client", lambda: None)
    reset_shared_proxy_pools()
    payload = _sha_challenge(counter=2)
    listing = _listing_html()
    seen_cookies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_cookies.append(request.headers.get("cookie", ""))
        if request.method == "GET" and request.url.path == "/vladivostok/zapchasti/":
            if "solved=1" not in request.headers.get("cookie", ""):
                return httpx.Response(
                    302,
                    headers={
                        "Location": VERIFY_URL,
                        "Set-Cookie": "fp_verify=step1; Path=/",
                    },
                )
            return httpx.Response(200, text=listing)
        if request.method == "GET" and "a" in request.url.params:
            return httpx.Response(200, json=payload)
        if request.method == "GET" and request.url.path == "/verify":
            return httpx.Response(200, text=_altcha_page_with_url())
        if request.method == "POST" and request.url.path == "/verify":
            return httpx.Response(
                302,
                headers={
                    "Location": TARGET_URL,
                    "Set-Cookie": "solved=1; Path=/",
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = FarpostClient(
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        transport=httpx.MockTransport(handler),
    )
    with client:
        assert client._session is not None
        offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
        assert len(offers) == 1
        # Every step (initial GET, challenge GET, POST, redirected listing) stayed on p1.
        assert client._session.last_proxy_key == proxy_fingerprint("http://p1:8080")
        assert len(client._session._httpx_clients) == 1
    assert any("fp_verify=step1" in cookie for cookie in seen_cookies[1:])
    assert "solved=1" in seen_cookies[-1]
    reset_shared_proxy_pools()


def _synthetic_captcha_png(digits: str = "4829", *, with_grid: bool = True) -> bytes:
    img = Image.new("L", (180, 56), color=255)
    draw = ImageDraw.Draw(img)
    if with_grid:
        for y in (8, 48):
            draw.line([(0, y), (179, y)], fill=120, width=1)
        for x in (14, 166):
            draw.line([(x, 0), (x, 55)], fill=120, width=1)
    # Draw large crisp digits so preprocessing + Tesseract can read them.
    for idx, ch in enumerate(digits):
        draw.text((28 + idx * 32, 14), ch, fill=0, font_size=26)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_tesseract_solver_preprocess_and_error_handling(monkeypatch):
    solver = TesseractImageCaptchaSolver(command="tesseract", min_digits=3, max_digits=6)
    png_bytes = _synthetic_captcha_png("4829", with_grid=True)

    # Grid lines covering >70% of row/column width are stripped while dark digit pixels remain.
    processed = solver._preprocess(png_bytes)
    with Image.open(io.BytesIO(processed)) as cleaned:
        assert cleaned.size == (180 * 4, 56 * 4)
        # Top row y=8 grid line on left border (x=0..8) should be cleared to white (255).
        assert cleaned.getpixel((4, 8 * 4)) == 255

    # Missing binary or expired deadline or corrupt bytes -> None.
    monkeypatch.setattr("apps.integrations.captcha.image.shutil.which", lambda _cmd: None)
    assert solver.available is False
    assert solver.solve(png_bytes, deadline=time.monotonic() + 5) is None

    monkeypatch.setattr(
        "apps.integrations.captcha.image.shutil.which", lambda _cmd: "/usr/bin/tesseract"
    )
    assert solver.available is True
    assert solver.solve(png_bytes, deadline=time.monotonic() - 1) is None
    assert solver.solve(b"not-an-image", deadline=time.monotonic() + 5) is None

    # Mocked subprocess output strips non-digits and checks min/max length bounds.
    monkeypatch.setattr(
        "apps.integrations.captcha.image.subprocess.run",
        lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout=b" 48-29\n"),
    )
    assert solver.solve(png_bytes, deadline=time.monotonic() + 5) == "4829"

    monkeypatch.setattr(
        "apps.integrations.captcha.image.subprocess.run",
        lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout=b"12\n"),
    )
    assert solver.solve(png_bytes, deadline=time.monotonic() + 5) is None

    monkeypatch.setattr(
        "apps.integrations.captcha.image.subprocess.run",
        lambda *_a, **_kw: SimpleNamespace(returncode=1, stdout=b""),
    )
    assert solver.solve(png_bytes, deadline=time.monotonic() + 5) is None

    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="tesseract", timeout=5)

    monkeypatch.setattr("apps.integrations.captcha.image.subprocess.run", raise_timeout)
    assert solver.solve(png_bytes, deadline=time.monotonic() + 5) is None


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract binary not installed")
def test_tesseract_solver_real_binary_on_synthetic_image():
    png_bytes = _synthetic_captcha_png("4820", with_grid=True)
    solver = TesseractImageCaptchaSolver(command="tesseract", timeout_sec=5.0)
    recognized = solver.solve(png_bytes, deadline=time.monotonic() + 10)
    assert recognized == "4820"


def test_altcha_v2_without_deadline_caps_search_and_clamps_argon2_workers(monkeypatch):
    from apps.integrations.captcha.altcha import _resolve_workers

    monkeypatch.setattr("apps.integrations.captcha.altcha._DEFAULT_V2_MAXNUMBER", 5)
    unsolvable = AltchaChallenge.from_payload(
        {
            "parameters": {
                "algorithm": "SHA-256",
                "cost": 1,
                "keyLength": 32,
                "keyPrefix": "ffffffffffffffff",
                "nonce": "0011223344556677",
                "salt": "ffeeddccbbaa9988",
            }
        }
    )
    with pytest.raises(AltchaSolveTimeoutError, match="search range"):
        solve_altcha(unsolvable, max_workers=2)

    heavy_argon = AltchaChallenge.from_payload(
        {
            "parameters": {
                "algorithm": "argon2id",
                "cost": 1,
                "memoryCost": 16_384,
                "parallelism": 1,
                "keyLength": 32,
                "keyPrefix": "0000",
                "nonce": "0011223344556677",
                "salt": "ffeeddccbbaa9988",
            }
        }
    )
    assert _resolve_workers(None, challenge=heavy_argon) <= 4


def test_farpost_captcha_post_derives_origin_from_page_url():
    payload = _sha_challenge(counter=2)
    seen_origins: list[str] = []
    challenged = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal challenged
        if request.method == "POST":
            seen_origins.append(request.headers.get("origin", ""))
            return httpx.Response(302, headers={"Location": TARGET_URL})
        if request.url.path == "/verify":
            return httpx.Response(200, text=_altcha_page(payload))
        if not challenged:
            challenged = True
            return httpx.Response(
                302, headers={"Location": "https://mirror.farpost.ru/verify?u=test"}
            )
        return httpx.Response(200, text=_listing_html())

    client = FarpostClient(transport=httpx.MockTransport(handler))
    offers = client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert seen_origins == ["https://mirror.farpost.ru"]


def test_parse_farpost_challenge_blocks_unsafe_external_urls():
    with pytest.raises(FarpostCaptchaError, match="Unsafe Farpost"):
        parse_farpost_challenge(
            '<html><form id="grecap-form" action="https://evil.com/steal">'
            '<input name="s" value="1"><altcha-widget challenge="{}"></altcha-widget>'
            "</form></html>",
            page_url=VERIFY_URL,
        )
    with pytest.raises(FarpostCaptchaError, match="Unsafe Farpost"):
        parse_farpost_challenge(
            '<html><div class="cap4"><img src="http://127.0.0.1:8000/img">'
            '<form action="/verify"><input name="s" value="1"></form></div></html>',
            page_url=VERIFY_URL,
        )


def test_altcha_argon2_caps_explicit_workers_and_clamps_heavy_params(monkeypatch):
    from apps.integrations.captcha.altcha import _resolve_workers

    heavy = AltchaChallenge.from_payload(
        {
            "parameters": {
                "algorithm": "argon2id",
                "cost": 999999,
                "memoryCost": 1_048_576,
                "parallelism": 64,
                "keyLength": 32,
                "keyPrefix": "0000",
                "nonce": "0011223344556677",
                "salt": "ffeeddccbbaa9988",
            }
        }
    )
    assert heavy.memory_cost <= 131_072
    assert heavy.parallelism <= 4
    assert heavy.cost <= 100
    assert _resolve_workers(8, challenge=heavy) <= 4

    # solve_altcha exits promptly on deadline even when _derive_key blocks longer.
    def slow_derive(_challenge, _counter):
        time.sleep(0.5)
        return b"\x00" * 32

    monkeypatch.setattr("apps.integrations.captcha.altcha._derive_key", slow_derive)
    started = time.monotonic()
    with pytest.raises(AltchaSolveTimeoutError, match="deadline"):
        solve_altcha(
            AltchaChallenge.from_payload(_sha_challenge(counter=2)),
            deadline=started + 0.05,
            max_workers=2,
        )
    assert time.monotonic() - started < 0.35


def test_tesseract_solver_rejects_oversized_and_decompression_bomb_images(monkeypatch):
    monkeypatch.setattr(
        "apps.integrations.captcha.image.shutil.which", lambda _cmd: "/usr/bin/tesseract"
    )
    solver = TesseractImageCaptchaSolver(command="tesseract")
    huge = Image.new("L", (2500, 2500), color=255)
    buf = io.BytesIO()
    huge.save(buf, format="PNG")
    assert solver.solve(buf.getvalue(), deadline=time.monotonic() + 5) is None

    def raise_bomb(*_a, **_kw):
        raise Image.DecompressionBombError("too many pixels")

    monkeypatch.setattr("apps.integrations.captcha.image.Image.open", raise_bomb)
    assert solver.solve(b"fake", deadline=time.monotonic() + 5) is None
