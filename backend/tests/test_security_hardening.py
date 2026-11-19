"""Security hardening tests for AdminHardeningMiddleware, RFC 7807 fallbacks, and scoring."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import pytest
from django.core.exceptions import DisallowedHost, RequestDataTooBig, SuspiciousOperation
from django.http import HttpResponse
from django.test import Client, RequestFactory

from apps.core.middleware import AdminHardeningMiddleware, ApiProblemDetailsMiddleware
from apps.lots.calculator.scoring import compute_verdict
from apps.lots.models import Lot, LotRiskFlags


class _FakeRateRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def eval(self, _script: str, _numkeys: int, key: str, *_args) -> int:
        next_val = self.counters.get(key, 0) + 1
        self.counters[key] = next_val
        return next_val


def test_admin_hardening_sets_headers_and_enforces_ip_allowlist(
    api_client: Client,
    settings,
) -> None:
    response = api_client.get("/admin/login/")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Frame-Options"] == "DENY"

    settings.ADMIN_ALLOWED_IPS = ["10.10.0.0/24", "203.0.113.5"]
    denied = api_client.get("/admin/login/", REMOTE_ADDR="198.51.100.77")
    assert denied.status_code == 403
    assert denied.headers["Cache-Control"] == "no-store"
    assert denied.headers["X-Frame-Options"] == "DENY"

    allowed_cidr = api_client.get("/admin/login/", REMOTE_ADDR="10.10.0.42")
    assert allowed_cidr.status_code == 200

    allowed_exact = api_client.get("/admin/login/", REMOTE_ADDR="203.0.113.5")
    assert allowed_exact.status_code == 200


def test_admin_login_rate_limits_by_ip_and_hashed_username(
    settings,
    monkeypatch,
) -> None:
    rf = RequestFactory()
    fake_redis = _FakeRateRedis()
    settings.RATE_LIMIT_ENABLED = True
    settings.DJANGO_ADMIN_URL = "/ops-admin"
    monkeypatch.setattr("apps.core.redis_utils.get_redis_client", lambda: fake_redis)

    middleware = AdminHardeningMiddleware(lambda _req: HttpResponse("ok", status=200))

    # 10 attempts for the same username across rotating IPs -> 11th is blocked by username hash.
    for idx in range(10):
        req = rf.post(
            "/ops-admin/login/",
            data={"username": "Boss@Example.com", "password": "wrong"},
            REMOTE_ADDR=f"198.51.100.{idx + 1}",
        )
        assert middleware(req).status_code == 200

    blocked_user_req = rf.post(
        "/ops-admin/login/",
        data={"username": "boss@example.com", "password": "wrong"},
        REMOTE_ADDR="198.51.100.50",
    )
    blocked_user_resp = middleware(blocked_user_req)
    assert blocked_user_resp.status_code == 429
    assert blocked_user_resp.headers["Cache-Control"] == "no-store"
    assert blocked_user_resp.headers["X-Frame-Options"] == "DENY"

    expected_hash = hashlib.sha256(b"boss@example.com").hexdigest()
    assert f"yuzu:rl:admin:login:user:{expected_hash}" in fake_redis.counters
    assert all("boss@example.com" not in k for k in fake_redis.counters)

    # 15 attempts from a single IP across distinct usernames -> 16th is blocked by IP.
    for idx in range(15):
        req = rf.post(
            "/ops-admin/login/",
            data={"username": f"user{idx}@example.com", "password": "wrong"},
            REMOTE_ADDR="203.0.113.77",
        )
        assert middleware(req).status_code == 200

    blocked_ip_req = rf.post(
        "/ops-admin/login/",
        data={"username": "fresh@example.com", "password": "wrong"},
        REMOTE_ADDR="203.0.113.77",
    )
    assert middleware(blocked_ip_req).status_code == 429


def test_disallowed_host_and_request_data_too_big_return_problem_json(
    settings,
) -> None:
    client = Client(raise_request_exception=False)
    settings.ALLOWED_HOSTS = ["api.yuzu.ru", "testserver"]

    bad_host = client.get("/api/v1/health", HTTP_HOST="evil.example.com")
    assert bad_host.status_code == 400
    assert bad_host.headers["Content-Type"].startswith("application/problem+json")
    assert bad_host.json()["status"] == 400

    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 16
    too_big = client.post(
        "/api/v1/auth/login",
        '{"email":"a@b.com","password":"Password123!"}',
        content_type="application/json",
    )
    assert too_big.status_code == 413
    assert too_big.headers["Content-Type"].startswith("application/problem+json")
    assert too_big.json()["status"] == 413


def test_pre_ninja_middleware_converts_errors_and_exceptions_on_api_routes() -> None:
    rf = RequestFactory()

    for status_code in (400, 403, 404, 405, 413, 500):
        mw = ApiProblemDetailsMiddleware(
            lambda _req, code=status_code: HttpResponse(
                "raw html", status=code, content_type="text/html"
            )
        )
        resp = mw(rf.get("/api/v1/lots"))
        assert resp.status_code == status_code
        assert resp.headers["Content-Type"] == "application/problem+json"
        body = json.loads(resp.content)
        assert body["status"] == status_code
        assert body["instance"] == "/api/v1/lots"

        non_api = mw(rf.get("/admin/login/"))
        assert non_api.status_code == status_code
        assert non_api.headers["Content-Type"] == "text/html"

    for exc, expected_status in (
        (RequestDataTooBig("too big"), 413),
        (DisallowedHost("bad host"), 400),
        (SuspiciousOperation("bad input"), 400),
    ):

        def _raise(_req, err=exc):
            raise err

        mw_exc = ApiProblemDetailsMiddleware(_raise)
        resp_exc = mw_exc(rf.post("/api/v1/lots/batches"))
        assert resp_exc.status_code == expected_status
        assert resp_exc.headers["Content-Type"] == "application/problem+json"
        assert json.loads(resp_exc.content)["status"] == expected_status

        with pytest.raises(type(exc)):
            mw_exc(rf.get("/non-api"))


@pytest.mark.django_db
def test_compute_verdict_headlines_have_no_emojis(user_factory) -> None:
    user = user_factory(email="scoring@example.com")

    green_lot = Lot.objects.create(
        user=user,
        make="Honda",
        model="Fit",
        net_benefit_rub=250_000,
        benefit_percentage=20.0,
        turnkey_cost_rub=1_200_000,
        market_price_rf_rub=1_450_000,
    )
    LotRiskFlags.objects.create(lot=green_lot)
    green_verdict = compute_verdict(green_lot)
    assert green_verdict.headline == "РЕКОМЕНДОВАНО К ПОКУПКЕ"

    yellow_lot = Lot.objects.create(
        user=user,
        make="Honda",
        model="Vezel",
        net_benefit_rub=80_000,
        benefit_percentage=8.0,
        turnkey_cost_rub=1_200_000,
        market_price_rf_rub=1_280_000,
    )
    LotRiskFlags.objects.create(lot=yellow_lot, windshield_damage=True)
    yellow_verdict = compute_verdict(yellow_lot)
    assert yellow_verdict.headline == "ВНИМАНИЕ: ЕСТЬ НЮАНСЫ"

    red_lot = Lot.objects.create(
        user=user,
        make="Honda",
        model="Freed",
        net_benefit_rub=200_000,
        benefit_percentage=15.0,
        turnkey_cost_rub=1_200_000,
        market_price_rf_rub=1_400_000,
        meti_sanction_risk=True,
    )
    LotRiskFlags.objects.create(lot=red_lot)
    red_verdict = compute_verdict(red_lot)
    assert red_verdict.headline == "ПОКУПКУ НЕ РЕКОМЕНДУЕМ"

    # Also verify pre-Ninja handler inside Admin/CSRF rejection on /api/v1/*.
    client = Client(enforce_csrf_checks=True)
    with patch("apps.core.api.HealthController.health_check", return_value={"status": "ok"}):
        csrf_res = client.post("/api/v1/health")
    assert csrf_res.status_code in (403, 405)
    assert csrf_res.headers["Content-Type"].startswith("application/problem+json")
