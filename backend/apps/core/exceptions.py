from apps.core.schemas import InvalidParamDetail

ERROR_TYPE_BASE = "https://api.yuzu-auto.ru/errors"


class ApiProblemError(Exception):
    """Domain error serialized to RFC 7807 Problem Details."""

    status_code: int = 400
    default_type: str = "about:blank"
    default_title: str = "Ошибка запроса"

    def __init__(
        self,
        detail: str,
        *,
        title: str | None = None,
        status_code: int | None = None,
        error_type: str | None = None,
        invalid_params: list[InvalidParamDetail] | None = None,
    ) -> None:
        self.detail = detail
        self.title = title or self.default_title
        if status_code is not None:
            self.status_code = status_code
        self.error_type = error_type or self.default_type
        self.invalid_params = invalid_params or []
        super().__init__(detail)


class BadRequestProblemError(ApiProblemError):
    status_code = 400
    default_type = f"{ERROR_TYPE_BASE}/bad-request"
    default_title = "Некорректный запрос"


class UnauthorizedProblemError(ApiProblemError):
    status_code = 401
    default_type = f"{ERROR_TYPE_BASE}/unauthorized"
    default_title = "Ошибка авторизации"


class NotFoundProblemError(ApiProblemError):
    status_code = 404
    default_type = f"{ERROR_TYPE_BASE}/not-found"
    default_title = "Ресурс не найден"


class ConflictProblemError(ApiProblemError):
    status_code = 409
    default_type = f"{ERROR_TYPE_BASE}/conflict"
    default_title = "Конфликт данных"
