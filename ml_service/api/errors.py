"""RFC 7807 Problem Details handlers and standardized HTTP error helpers."""

import logging
from http import HTTPStatus
from typing import NoReturn

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ml_service.api.schemas import InvalidParamDetail, ProblemDetailsResponse

logger = logging.getLogger(__name__)
_MAX_VALIDATION_ERRORS = 50


def raise_service_unavailable(detail: str) -> NoReturn:
    """Raise a standardized 503 Service Unavailable error with Retry-After header."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
        headers={"Retry-After": "5"},
    )


def _problem_response(
    *,
    status_code: int,
    detail: str,
    instance: str,
    headers: dict[str, str] | None = None,
    invalid_params: list[InvalidParamDetail] | None = None,
) -> JSONResponse:
    try:
        title = HTTPStatus(status_code).phrase
    except ValueError:
        title = "HTTP Error"
    payload = ProblemDetailsResponse(
        type=f"https://httpstatuses.com/{status_code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        invalid_params=invalid_params or [],
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        media_type="application/problem+json",
        headers=headers,
    )


def register_exception_handlers(app_instance: FastAPI) -> None:
    """Register RFC 7807 Problem Details handlers on a FastAPI application instance."""

    @app_instance.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _problem_response(
            status_code=exc.status_code,
            detail=str(exc.detail),
            instance=str(request.url.path),
            headers=getattr(exc, "headers", None),
        )

    @app_instance.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        invalid_params = [
            InvalidParamDetail(
                name=".".join(str(part) for part in err.get("loc", ())) or "request",
                reason=str(err.get("msg", "Validation error")),
            )
            for err in exc.errors()[:_MAX_VALIDATION_ERRORS]
        ]
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Request validation failed.",
            instance=str(request.url.path),
            invalid_params=invalid_params,
        )

    @app_instance.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request,
        exc: Exception,  # noqa: ARG001 — top-level RFC 7807 500 boundary
    ) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
            instance=str(request.url.path),
        )
