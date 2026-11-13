import logging
from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from ninja.errors import AuthenticationError, HttpError, ValidationError
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

from apps.core.exceptions import ERROR_TYPE_BASE, ApiProblemError
from apps.core.schemas import InvalidParamDetail, ProblemDetail

logger = logging.getLogger(__name__)

_STATUS_TITLES: dict[int, str] = {
    400: "Некорректный запрос",
    401: "Требуется авторизация",
    403: "Доступ запрещен",
    404: "Ресурс не найден",
    405: "Метод не поддерживается",
    409: "Конфликт данных",
    422: "Ошибка валидации параметров",
    500: "Внутренняя ошибка сервера",
    503: "Сервис временно недоступен",
}


def _problem_response(
    api: NinjaExtraAPI,
    request: HttpRequest,
    *,
    status: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    invalid_params: list[InvalidParamDetail] | None = None,
) -> HttpResponse:
    payload = ProblemDetail(
        type=error_type,
        title=title,
        status=status,
        detail=detail,
        instance=request.path,
        invalid_params=invalid_params or [],
    )
    response = api.create_response(request, payload, status=status)
    response["Content-Type"] = "application/problem+json"
    return response


def _format_error_loc(loc: Any) -> str:
    if not isinstance(loc, (list, tuple)):
        return str(loc) if loc else "body"
    parts = [str(part) for part in loc]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie", "form", "file"}:
        source = parts.pop(0)
        if source == "body" and len(parts) > 1 and parts[0] == "payload":
            parts.pop(0)
    return ".".join(parts) if parts else "body"


def _extract_detail_text(raw_detail: Any, fallback: str) -> str:
    if isinstance(raw_detail, dict):
        nested = raw_detail.get("detail")
        if nested is not None:
            return str(nested)
    if isinstance(raw_detail, list) and raw_detail:
        return "; ".join(str(item) for item in raw_detail)
    if raw_detail:
        return str(raw_detail)
    return fallback


def _validation_reason(error: dict[str, Any]) -> str:
    error_type = error.get("type")
    context = error.get("ctx") or {}
    if error_type == "exclusive_bid_currency":
        return str(error["msg"])
    if error_type == "string_too_short":
        return f"Минимальная длина: {context['min_length']} символов"
    if error_type == "string_too_long":
        return f"Максимальная длина: {context['max_length']} символов"
    if error_type == "greater_than_equal":
        return f"Значение должно быть не меньше {context['ge']}"
    if error_type == "less_than_equal":
        return f"Значение должно быть не больше {context['le']}"
    return {
        "missing": "Обязательное поле отсутствует",
        "extra_forbidden": "Недопустимое поле",
        "value_error": "Некорректное значение",
    }.get(error_type, "Некорректное значение")


def register_exception_handlers(api: NinjaExtraAPI) -> None:
    """Register global RFC 7807 exception handlers on NinjaExtraAPI."""

    @api.exception_handler(ApiProblemError)
    def handle_api_problem(request: HttpRequest, exc: ApiProblemError) -> HttpResponse:
        return _problem_response(
            api,
            request,
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            error_type=exc.error_type,
            invalid_params=exc.invalid_params,
        )

    @api.exception_handler(ValidationError)
    def handle_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
        invalid_params = [
            InvalidParamDetail(
                name=_format_error_loc(err.get("loc")),
                reason=_validation_reason(err),
            )
            for err in exc.errors
        ]
        first_reason = (
            invalid_params[0].reason
            if invalid_params
            else "Проверьте корректность переданных данных"
        )
        return _problem_response(
            api,
            request,
            status=422,
            title="Ошибка валидации параметров",
            detail=first_reason,
            error_type=f"{ERROR_TYPE_BASE}/validation-error",
            invalid_params=invalid_params,
        )

    @api.exception_handler(AuthenticationError)
    def handle_auth_error(request: HttpRequest, _exc: AuthenticationError) -> HttpResponse:
        return _problem_response(
            api,
            request,
            status=401,
            title="Требуется авторизация",
            detail="Отсутствует или недействителен токен авторизации",
            error_type=f"{ERROR_TYPE_BASE}/unauthorized",
        )

    @api.exception_handler(APIException)
    def handle_ninja_extra_exception(request: HttpRequest, exc: APIException) -> HttpResponse:
        status_code = getattr(exc, "status_code", 500)
        title = _STATUS_TITLES.get(status_code, "Ошибка запроса")
        if status_code == 401:
            detail = "Токен доступа недействителен или истек"
            error_type = f"{ERROR_TYPE_BASE}/unauthorized"
        else:
            detail = _extract_detail_text(getattr(exc, "detail", None), title)
            error_type = f"{ERROR_TYPE_BASE}/api-error"
        return _problem_response(
            api,
            request,
            status=status_code,
            title=title,
            detail=detail,
            error_type=error_type,
        )

    @api.exception_handler(HttpError)
    def handle_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
        status_code = exc.status_code
        title = _STATUS_TITLES.get(status_code, "Ошибка запроса")
        detail = exc.message or title
        if status_code == 400 and detail == "Cannot parse request body":
            detail = "Некорректный формат JSON в теле запроса"
        return _problem_response(
            api,
            request,
            status=status_code,
            title=title,
            detail=detail,
            error_type=f"{ERROR_TYPE_BASE}/http-{status_code}",
        )

    @api.exception_handler(Http404)
    def handle_not_found(request: HttpRequest, _exc: Http404) -> HttpResponse:
        return _problem_response(
            api,
            request,
            status=404,
            title="Ресурс не найден",
            detail="Запрашиваемый ресурс не найден",
            error_type=f"{ERROR_TYPE_BASE}/not-found",
        )

    @api.exception_handler(Exception)
    def handle_unexpected_error(request: HttpRequest, exc: Exception) -> HttpResponse:
        logger.exception("Unhandled API exception on %s", request.path)
        detail = (
            str(exc)
            if settings.DEBUG
            else "Произошла внутренняя ошибка сервера. Повторите попытку позже."
        )
        return _problem_response(
            api,
            request,
            status=500,
            title="Внутренняя ошибка сервера",
            detail=detail,
            error_type=f"{ERROR_TYPE_BASE}/internal-server-error",
        )
