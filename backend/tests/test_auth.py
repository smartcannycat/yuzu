from uuid import UUID

import pytest
from django.conf import settings
from django.test import Client, override_settings
from ninja_jwt.tokens import AccessToken

from apps.users.models import User


class _FakeRateLimitRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def eval(self, _script: str, _numkeys: int, key: str, *_args) -> int:
        next_val = self.counters.get(key, 0) + 1
        self.counters[key] = next_val
        return next_val


@pytest.mark.django_db
def test_register_success(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "Alex@Example.com",
            "password": "Password123!",
            "name": " Алексей ",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in_sec"] == 3600
    assert isinstance(data["access_token"], str)
    assert "refresh_token" not in data

    cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
    assert cookie.value
    assert cookie["httponly"] is True
    assert cookie["path"] == settings.JWT_REFRESH_COOKIE_PATH
    assert cookie["samesite"] == "Lax"
    assert bool(cookie["secure"]) is (not settings.DEBUG)

    user_data = data["user"]
    UUID(user_data["user_id"])
    assert user_data["email"] == "alex@example.com"
    assert user_data["name"] == "Алексей"
    assert "created_at" in user_data

    assert User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_register_preserves_password_whitespace_and_normalizes_blank_name(
    api_client: Client,
) -> None:
    password_with_spaces = "  Secret123!  "
    register_response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "spaces@example.com",
            "password": password_with_spaces,
            "name": "   ",
        },
        content_type="application/json",
    )
    assert register_response.status_code == 201
    assert register_response.json()["user"]["name"] is None

    trimmed_login = api_client.post(
        "/api/v1/auth/login",
        {"email": "spaces@example.com", "password": password_with_spaces.strip()},
        content_type="application/json",
    )
    assert trimmed_login.status_code == 401

    exact_login = api_client.post(
        "/api/v1/auth/login",
        {"email": "spaces@example.com", "password": password_with_spaces},
        content_type="application/json",
    )
    assert exact_login.status_code == 200


@pytest.mark.django_db
def test_register_password_length_boundaries(api_client: Client) -> None:
    too_short = api_client.post(
        "/api/v1/auth/register",
        {"email": "short@example.com", "password": "1234567"},
        content_type="application/json",
    )
    assert too_short.status_code == 422

    too_long = api_client.post(
        "/api/v1/auth/register",
        {"email": "long@example.com", "password": "x" * 129},
        content_type="application/json",
    )
    assert too_long.status_code == 422

    exact_min = api_client.post(
        "/api/v1/auth/register",
        {"email": "min@example.com", "password": "12345678"},
        content_type="application/json",
    )
    assert exact_min.status_code == 201


@pytest.mark.django_db
def test_register_duplicate_email_returns_rfc7807_conflict(
    api_client: Client,
    user_factory,
) -> None:
    user_factory(email="alex@example.com")

    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "ALEX@example.com",
            "password": "Password123!",
            "name": "Алексей",
        },
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.headers["Content-Type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 409
    assert problem["instance"] == "/api/v1/auth/register"
    assert problem["title"]
    assert problem["detail"]


@pytest.mark.django_db
def test_register_validation_error_returns_rfc7807(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "not-an-email",
            "password": "123",
            "unexpected_field": "nope",
        },
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.headers["Content-Type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 422
    assert problem["instance"] == "/api/v1/auth/register"
    invalid_names = {item["name"] for item in problem["invalid_params"]}
    assert "email" in invalid_names
    assert "password" in invalid_names
    assert "unexpected_field" in invalid_names


def test_malformed_json_returns_rfc7807_400(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/login",
        "{bad json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.headers["Content-Type"].startswith("application/problem+json")
    assert response.json()["status"] == 400


@pytest.mark.django_db
def test_login_success_and_me_endpoint(api_client: Client, user_factory) -> None:
    user = user_factory(email="driver@example.com", password="Password123!", name="Иван")

    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "Driver@Example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["user"]["user_id"] == str(user.id)
    assert tokens["user"]["email"] == "driver@example.com"

    me_response = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
    )
    assert me_response.status_code == 200
    assert me_response.json() == tokens["user"]


@pytest.mark.django_db
def test_login_invalid_credentials_and_inactive_user(
    api_client: Client,
    user_factory,
) -> None:
    user_factory(email="active@example.com", password="Password123!")
    user_factory(email="inactive@example.com", password="Password123!", is_active=False)

    wrong_pass = api_client.post(
        "/api/v1/auth/login",
        {"email": "active@example.com", "password": "WrongPassword!"},
        content_type="application/json",
    )
    assert wrong_pass.status_code == 401
    assert wrong_pass.headers["Content-Type"].startswith("application/problem+json")
    assert wrong_pass.json()["status"] == 401

    inactive = api_client.post(
        "/api/v1/auth/login",
        {"email": "inactive@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert inactive.status_code == 401
    assert inactive.json()["status"] == 401


@pytest.mark.django_db
def test_refresh_token_flow_and_replay_blacklist(api_client: Client, user_factory) -> None:
    user = user_factory(email="refresh@example.com", password="Password123!")

    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "refresh@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert login_response.status_code == 200
    assert "refresh_token" not in login_response.json()
    initial_refresh = login_response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    refresh_response = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_ORIGIN="http://localhost:5173",
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["token_type"] == "bearer"
    assert refreshed["user"]["user_id"] == str(user.id)
    assert "refresh_token" not in refreshed
    rotated_refresh = refresh_response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    assert rotated_refresh != initial_refresh

    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = initial_refresh
    replay_response = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_X_REQUESTED_WITH="YuzuSPA",
    )
    assert replay_response.status_code == 401
    assert replay_response.headers["Content-Type"].startswith("application/problem+json")

    me_response = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {refreshed['access_token']}",
    )
    assert me_response.status_code == 200


@pytest.mark.django_db
def test_token_type_confusion_rejected(api_client: Client, user_factory) -> None:
    user_factory(email="confusion@example.com", password="Password123!")

    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "confusion@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    tokens = login_response.json()
    refresh_cookie = login_response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens["access_token"]
    refresh_with_access = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_X_REQUESTED_WITH="YuzuSPA",
    )
    assert refresh_with_access.status_code == 401

    me_with_refresh = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {refresh_cookie}",
    )
    assert me_with_refresh.status_code == 401


@pytest.mark.django_db
def test_refresh_invalid_or_missing_cookie_returns_401_problem(api_client: Client) -> None:
    missing_resp = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_X_REQUESTED_WITH="YuzuSPA",
    )
    assert missing_resp.status_code == 401
    assert missing_resp.headers["Content-Type"].startswith("application/problem+json")

    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = "not.a.valid.jwt"
    response = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_X_REQUESTED_WITH="YuzuSPA",
    )
    assert response.status_code == 401
    assert response.headers["Content-Type"].startswith("application/problem+json")
    assert response.json()["status"] == 401


@pytest.mark.django_db
def test_refresh_and_logout_enforce_csrf_origin_protection(
    api_client: Client,
    user_factory,
) -> None:
    user_factory(email="csrf@example.com", password="Password123!")
    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "csrf@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert login_response.status_code == 200

    for endpoint in ("/api/v1/auth/refresh", "/api/v1/auth/logout"):
        missing_headers = api_client.post(endpoint)
        assert missing_headers.status_code == 403
        assert missing_headers.headers["Content-Type"].startswith("application/problem+json")

        evil_origin = api_client.post(endpoint, HTTP_ORIGIN="https://evil.example.com")
        assert evil_origin.status_code == 403

        evil_origin_with_header = api_client.post(
            endpoint,
            HTTP_ORIGIN="https://evil.example.com",
            HTTP_X_REQUESTED_WITH="YuzuSPA",
        )
        assert evil_origin_with_header.status_code == 403

        null_origin = api_client.post(endpoint, HTTP_ORIGIN="null")
        assert null_origin.status_code == 403

        evil_referer = api_client.post(endpoint, HTTP_REFERER="https://evil.example.com/form")
        assert evil_referer.status_code == 403

    assert (
        api_client.post(
            "/api/v1/auth/refresh",
            HTTP_REFERER="http://localhost:5173/dashboard",
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            "/api/v1/auth/refresh",
            HTTP_ORIGIN="http://testserver",
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_logout_blacklists_refresh_cookie_clears_cookie_and_is_idempotent(
    api_client: Client,
    user_factory,
) -> None:
    user_factory(email="logout@example.com", password="Password123!")
    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "logout@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    refresh_val = login_response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    logout_response = api_client.post(
        "/api/v1/auth/logout",
        HTTP_ORIGIN="http://localhost:5173",
    )
    assert logout_response.status_code == 204
    cleared_cookie = logout_response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
    assert cleared_cookie.value == ""
    assert cleared_cookie["max-age"] == 0
    assert cleared_cookie["path"] == settings.JWT_REFRESH_COOKIE_PATH

    # Blacklisted refresh cookie cannot be replayed after logout.
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = refresh_val
    after_logout_refresh = api_client.post(
        "/api/v1/auth/refresh",
        HTTP_X_REQUESTED_WITH="YuzuSPA",
    )
    assert after_logout_refresh.status_code == 401

    # Logout remains idempotent when cookie is absent or invalid.
    api_client.cookies.pop(settings.JWT_REFRESH_COOKIE_NAME, None)
    assert (
        api_client.post("/api/v1/auth/logout", HTTP_X_REQUESTED_WITH="YuzuSPA").status_code == 204
    )
    api_client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = "garbage.jwt"
    assert (
        api_client.post("/api/v1/auth/logout", HTTP_X_REQUESTED_WITH="YuzuSPA").status_code == 204
    )


@pytest.mark.django_db
def test_refresh_cookie_sets_secure_flag_when_not_debug(
    api_client: Client,
    user_factory,
) -> None:
    user_factory(email="secure@example.com", password="Password123!")

    with override_settings(DEBUG=True):
        dev_resp = api_client.post(
            "/api/v1/auth/login",
            {"email": "secure@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        assert dev_resp.status_code == 200
        assert not dev_resp.cookies[settings.JWT_REFRESH_COOKIE_NAME]["secure"]

    with override_settings(DEBUG=False):
        login_resp = api_client.post(
            "/api/v1/auth/login",
            {"email": "secure@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        assert login_resp.status_code == 200
        assert bool(login_resp.cookies[settings.JWT_REFRESH_COOKIE_NAME]["secure"]) is True

        refresh_resp = api_client.post(
            "/api/v1/auth/refresh",
            HTTP_X_REQUESTED_WITH="YuzuSPA",
        )
        assert refresh_resp.status_code == 200
        assert bool(refresh_resp.cookies[settings.JWT_REFRESH_COOKIE_NAME]["secure"]) is True


@pytest.mark.django_db
def test_login_per_account_rate_limit_independent_of_ip(
    api_client: Client,
    user_factory,
    settings,
    monkeypatch,
) -> None:
    import hashlib

    user_factory(email="target@example.com", password="Password123!")
    fake_redis = _FakeRateLimitRedis()
    settings.RATE_LIMIT_ENABLED = True
    monkeypatch.setattr("apps.core.redis_utils.get_redis_client", lambda: fake_redis)

    for idx in range(10):
        resp = api_client.post(
            "/api/v1/auth/login",
            {"email": "Target@Example.com", "password": "WrongPassword!"},
            content_type="application/json",
            REMOTE_ADDR=f"198.51.100.{idx + 1}",
        )
        assert resp.status_code == 401

    blocked = api_client.post(
        "/api/v1/auth/login",
        {"email": "target@example.com", "password": "Password123!"},
        content_type="application/json",
        REMOTE_ADDR="198.51.100.99",
    )
    assert blocked.status_code == 429
    assert blocked.headers["Content-Type"].startswith("application/problem+json")

    expected_hash = hashlib.sha256(b"target@example.com").hexdigest()
    assert f"yuzu:rl:auth:login:email:{expected_hash}" in fake_redis.counters
    assert all("target@example.com" not in key for key in fake_redis.counters)

    # Another account is not affected by target's per-account throttle.
    other = api_client.post(
        "/api/v1/auth/login",
        {"email": "other@example.com", "password": "WrongPassword!"},
        content_type="application/json",
        REMOTE_ADDR="198.51.100.100",
    )
    assert other.status_code == 401


@pytest.mark.django_db
def test_me_requires_valid_bearer_token_and_handles_bad_claims(
    api_client: Client,
    user_factory,
) -> None:
    missing = api_client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.headers["Content-Type"].startswith("application/problem+json")
    assert missing.json()["status"] == 401

    invalid = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION="Bearer invalid.token.value",
    )
    assert invalid.status_code == 401
    assert invalid.headers["Content-Type"].startswith("application/problem+json")
    assert invalid.json()["status"] == 401

    bad_claim_token = AccessToken()
    bad_claim_token["user_id"] = "not-a-uuid"
    bad_claim = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {bad_claim_token}",
    )
    assert bad_claim.status_code == 401
    assert bad_claim.headers["Content-Type"].startswith("application/problem+json")

    user = user_factory(email="deleted@example.com", password="Password123!")
    valid_token = AccessToken.for_user(user)
    user.delete()

    deleted_user_resp = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {valid_token}",
    )
    assert deleted_user_resp.status_code == 401
