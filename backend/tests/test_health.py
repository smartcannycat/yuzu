from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.test import Client, override_settings


@pytest.mark.django_db
def test_health_check(api_client: Client) -> None:
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_returns_503_when_db_unavailable(api_client: Client) -> None:
    with patch("apps.core.api.connection.cursor", side_effect=DatabaseError("db down")):
        response = api_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.headers["Content-Type"].startswith("application/problem+json")
    assert response.json()["status"] == 503


def test_openapi_schema_available(api_client: Client) -> None:
    response = api_client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Yuzu API"
    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/auth/me" in schema["paths"]


def test_cors_allows_vite_origin(api_client: Client) -> None:
    response = api_client.options(
        "/api/v1/health",
        HTTP_ORIGIN="http://localhost:5173",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_unmatched_api_route_returns_rfc7807_404(api_client: Client) -> None:
    response = api_client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    assert response.headers["Content-Type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 404
    assert problem["instance"] == "/api/v1/nonexistent-route"


def test_wrong_method_returns_rfc7807_405(api_client: Client) -> None:
    response = api_client.get("/api/v1/auth/login")
    assert response.status_code == 405
    assert response.headers["Content-Type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 405
    assert problem["instance"] == "/api/v1/auth/login"


@override_settings(DEBUG=False)
def test_unexpected_exception_masks_detail_in_non_debug(api_client: Client) -> None:
    with patch("apps.core.api.connection.cursor", side_effect=RuntimeError("sensitive secret")):
        response = api_client.get("/api/v1/health")

    assert response.status_code == 500
    assert response.headers["Content-Type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 500
    assert "sensitive secret" not in problem["detail"]


def test_admin_login_and_csrf_trusted_origins(api_client: Client) -> None:
    from django.conf import settings

    from config.settings.config import AppSettings

    response = api_client.get("/admin/login/")
    assert response.status_code == 200
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE

    derived = AppSettings(CORS_ALLOWED_ORIGINS="https://yuzu.nlzr.net,http://localhost:5173")
    assert derived.CSRF_TRUSTED_ORIGINS == []
    assert [o for o in derived.CORS_ALLOWED_ORIGINS if o.startswith(("http://", "https://"))] == [
        "https://yuzu.nlzr.net",
        "http://localhost:5173",
    ]
