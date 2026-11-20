"""HTTP middlewares for RFC 7807 API fallback errors and Django Admin hardening."""

from __future__ import annotations

import hashlib
import ipaddress
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import (
    DisallowedHost,
    RequestDataTooBig,
    SuspiciousOperation,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.http import HttpResponse

from apps.core.exceptions import ERROR_TYPE_BASE, TooManyRequestsProblemError
from apps.core.redis_utils import enforce_rate_limit, get_client_ip
from apps.core.schemas import ProblemDetail

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest

_FALLBACK_STATUS_MESSAGES: dict[int, tuple[str, str, str]] = {
    400: (
        f"{ERROR_TYPE_BASE}/bad-request",
        "Некорректный запрос",
        "Запрос отклонен как некорректный",
    ),
    403: (
        f"{ERROR_TYPE_BASE}/forbidden",
        "Доступ запрещен",
        "Доступ запрещен или не пройдена проверка безопасности",
    ),
    404: (
        f"{ERROR_TYPE_BASE}/not-found",
        "Ресурс не найден",
        "Запрашиваемый эндпоинт или ресурс не найден",
    ),
    405: (
        f"{ERROR_TYPE_BASE}/method-not-allowed",
        "Метод не поддерживается",
        "HTTP-метод не поддерживается для данного эндпоинта",
    ),
    413: (
        f"{ERROR_TYPE_BASE}/payload-too-large",
        "Превышен размер запроса",
        "Размер тела запроса превышает допустимый лимит",
    ),
    500: (
        f"{ERROR_TYPE_BASE}/internal-server-error",
        "Внутренняя ошибка сервера",
        "Произошла внутренняя ошибка сервера. Повторите попытку позже.",
    ),
}

_PAYLOAD_TOO_BIG_EXCEPTIONS = (RequestDataTooBig, TooManyFieldsSent, TooManyFilesSent)


def _build_problem_response(
    request: HttpRequest,
    *,
    status: int,
    error_type: str,
    title: str,
    detail: str,
    allow_header: str | None = None,
) -> HttpResponse:
    payload = ProblemDetail(
        type=error_type,
        title=title,
        status=status,
        detail=detail,
        instance=request.path,
    )
    problem_response = HttpResponse(
        payload.model_dump_json(),
        status=status,
        content_type="application/problem+json",
    )
    if allow_header is not None:
        problem_response["Allow"] = allow_header
    return problem_response


def _response_for_suspicious_operation(
    request: HttpRequest,
    exc: SuspiciousOperation,
) -> HttpResponse:
    if isinstance(exc, _PAYLOAD_TOO_BIG_EXCEPTIONS):
        return _build_problem_response(
            request,
            status=413,
            error_type=f"{ERROR_TYPE_BASE}/payload-too-large",
            title="Превышен размер запроса",
            detail="Размер тела запроса или количество параметров превышает допустимый лимит",
        )
    if isinstance(exc, DisallowedHost):
        return _build_problem_response(
            request,
            status=400,
            error_type=f"{ERROR_TYPE_BASE}/bad-request",
            title="Некорректный запрос",
            detail="Недопустимый заголовок Host",
        )
    return _build_problem_response(
        request,
        status=400,
        error_type=f"{ERROR_TYPE_BASE}/bad-request",
        title="Некорректный запрос",
        detail="Запрос отклонен системой безопасности",
    )


class ApiProblemDetailsMiddleware:
    """Convert pre-Ninja errors and security exceptions on /api/v1/* to RFC 7807."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            response = self.get_response(request)
        except SuspiciousOperation as exc:
            if request.path.startswith("/api/v1/"):
                return _response_for_suspicious_operation(request, exc)
            raise

        if not request.path.startswith("/api/v1/"):
            return response

        content_type = response.get("Content-Type", "")
        if content_type.startswith(("application/problem+json", "application/json")):
            return response

        fallback = _FALLBACK_STATUS_MESSAGES.get(response.status_code)
        if fallback is None:
            return response

        error_type, title, detail = fallback
        return _build_problem_response(
            request,
            status=response.status_code,
            error_type=error_type,
            title=title,
            detail=detail,
            allow_header=response.get("Allow"),
        )

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        if request.path.startswith("/api/v1/") and isinstance(exception, SuspiciousOperation):
            return _response_for_suspicious_operation(request, exception)
        return None


def _normalize_admin_prefix() -> str:
    raw = (getattr(settings, "DJANGO_ADMIN_URL", "admin/") or "admin/").strip().strip("/")
    return f"/{raw}/" if raw else "/admin/"


def _is_admin_request(path: str, prefix: str) -> bool:
    return path == prefix.rstrip("/") or path.startswith(prefix)


def _ip_in_allowlist(client_ip: str, allowed_entries: list[str] | tuple[str, ...]) -> bool:
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for raw_entry in allowed_entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def _apply_admin_security_headers(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "no-store"
    response["X-Frame-Options"] = "DENY"
    return response


def _check_admin_login_rate_limit(
    request: HttpRequest,
    client_ip: str,
    prefix: str,
) -> HttpResponse | None:
    if request.method != "POST" or not request.path.startswith(f"{prefix}login"):
        return None
    try:
        enforce_rate_limit(
            "admin:login:ip",
            client_ip,
            limit=15,
            window_sec=300,
            detail="Слишком много попыток входа в панель администратора. Попробуйте позже.",
        )
        raw_username = (request.POST.get("username") or "").strip().lower()
        if raw_username:
            username_hash = hashlib.sha256(raw_username.encode("utf-8")).hexdigest()
            enforce_rate_limit(
                "admin:login:user",
                username_hash,
                limit=10,
                window_sec=300,
                detail="Слишком много попыток входа для данного пользователя. Попробуйте позже.",
            )
    except TooManyRequestsProblemError as exc:
        response = HttpResponse(exc.detail, status=429, content_type="text/plain; charset=utf-8")
        response["Retry-After"] = "300"
        return _apply_admin_security_headers(response)
    return None


class AdminHardeningMiddleware:
    """Enforce optional IP allowlist, login rate limiting, and security headers on Django Admin."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        prefix = _normalize_admin_prefix()
        if not _is_admin_request(request.path, prefix):
            return self.get_response(request)

        client_ip = get_client_ip(request)
        allowed_ips = getattr(settings, "ADMIN_ALLOWED_IPS", []) or []
        if allowed_ips and not _ip_in_allowlist(client_ip, allowed_ips):
            return _apply_admin_security_headers(
                HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")
            )

        throttled = _check_admin_login_rate_limit(request, client_ip, prefix)
        if throttled is not None:
            return throttled

        response = self.get_response(request)
        return _apply_admin_security_headers(response)
