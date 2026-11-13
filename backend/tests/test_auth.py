from uuid import UUID

import pytest
from django.test import Client

from apps.users.models import User


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
    assert isinstance(data["refresh_token"], str)

    user_data = data["user"]
    UUID(user_data["user_id"])
    assert user_data["email"] == "alex@example.com"
    assert user_data["name"] == "Алексей"
    assert "created_at" in user_data

    assert User.objects.filter(email="alex@example.com").exists()


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
def test_refresh_token_flow(api_client: Client, user_factory) -> None:
    user = user_factory(email="refresh@example.com", password="Password123!")

    login_response = api_client.post(
        "/api/v1/auth/login",
        {"email": "refresh@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    initial_tokens = login_response.json()

    refresh_response = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": initial_tokens["refresh_token"]},
        content_type="application/json",
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["token_type"] == "bearer"
    assert refreshed["user"]["user_id"] == str(user.id)
    assert refreshed["refresh_token"] != initial_tokens["refresh_token"]

    me_response = api_client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {refreshed['access_token']}",
    )
    assert me_response.status_code == 200


@pytest.mark.django_db
def test_refresh_invalid_token_returns_401_problem(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": "not.a.valid.jwt"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.headers["Content-Type"].startswith("application/problem+json")
    assert response.json()["status"] == 401


@pytest.mark.django_db
def test_me_requires_valid_bearer_token(api_client: Client) -> None:
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
