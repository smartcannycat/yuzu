from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.exceptions import ERROR_TYPE_BASE
from apps.core.schemas import ProblemDetail

_FALLBACK_STATUS_MESSAGES: dict[int, tuple[str, str, str]] = {
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
}


class ApiProblemDetailsMiddleware:
    """Ensure unmatched /api/v1/* 404 and 405 responses use RFC 7807 ProblemDetail."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if not request.path.startswith("/api/v1/"):
            return response

        content_type = response.get("Content-Type", "")
        if content_type.startswith(("application/problem+json", "application/json")):
            return response

        fallback = _FALLBACK_STATUS_MESSAGES.get(response.status_code)
        if fallback is None:
            return response

        error_type, title, detail = fallback
        payload = ProblemDetail(
            type=error_type,
            title=title,
            status=response.status_code,
            detail=detail,
            instance=request.path,
        )
        problem_response = HttpResponse(
            payload.model_dump_json(),
            status=response.status_code,
            content_type="application/problem+json",
        )
        if "Allow" in response:
            problem_response["Allow"] = response["Allow"]
        return problem_response
