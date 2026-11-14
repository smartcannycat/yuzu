"""Thin FastAPI controllers for single-sheet parsing, batch jobs, and RFC 7807 errors."""

import logging
from http import HTTPStatus
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.genai.errors import APIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ml_service.api.dependencies import (
    get_batch_service_dep,
    get_chassis_ocr_client_dep,
    get_key_pool_dep,
    get_parser_service_dep,
    get_settings_dep,
    rate_limit_dep,
    require_api_key_dep,
)
from ml_service.api.schemas import (
    BatchCreateResponse,
    BatchProgressResponse,
    ChassisOcrResponse,
    HealthResponse,
    InvalidParamDetail,
    ParserResponse,
    ParseUrlRequest,
    ProblemDetailsResponse,
    to_batch_create_response,
    to_batch_progress_response,
    to_parser_response,
)
from ml_service.config import Settings
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.services.batch_parser_service import BatchCapacityError, BatchConflictError, BatchParserService
from ml_service.services.sheet_parser_service import SheetParserService

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key_dep), Depends(rate_limit_dep)])
_UPLOAD_CHUNK_SIZE = 1024 * 1024

_ALLOWED_UPLOAD_MIMES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "application/octet-stream",
        "",
    }
)


def _validate_upload_content_type(upload: UploadFile) -> None:
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_UPLOAD_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported Content-Type '{mime}' for '{upload.filename or 'upload'}'. "
                "Allowed MIME types: image/jpeg, image/png, image/webp, image/heic, image/heif."
            ),
        )


async def _read_upload_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file in bounded chunks so oversized payloads fail before buffering."""
    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image size ({declared_size} bytes) exceeds maximum allowed ({max_bytes} bytes).",
        )

    chunks = bytearray()
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        if len(chunks) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image size exceeds maximum allowed ({max_bytes} bytes).",
            )
        chunks.extend(chunk)
    return bytes(chunks)


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
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_response(
            status_code=exc.status_code,
            detail=str(exc.detail),
            instance=str(request.url.path),
            headers=getattr(exc, "headers", None),
        )

    @app_instance.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        invalid_params = [
            InvalidParamDetail(
                name=".".join(str(part) for part in err.get("loc", ())) or "request",
                reason=str(err.get("msg", "Validation error")),
            )
            for err in exc.errors()
        ]
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc.errors()),
            instance=str(request.url.path),
            invalid_params=invalid_params,
        )


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(
    settings: Settings = Depends(get_settings_dep),
    key_pool: GeminiKeyPool = Depends(get_key_pool_dep),
) -> HealthResponse:
    """Return service health status and safe non-secret configuration counters."""
    return HealthResponse(
        status="ok",
        keys_configured=key_pool.key_count,
        reference_year=settings.reference_year,
    )


@router.post("/api/v1/chassis/read", response_model=ChassisOcrResponse, tags=["chassis"])
async def read_chassis_number(
    file: UploadFile = File(...),
    chassis_client=Depends(get_chassis_ocr_client_dep),
    settings: Settings = Depends(get_settings_dep),
) -> ChassisOcrResponse:
    """Read the chassis/frame number printed in an uploaded chassis image."""
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported Content-Type '{mime}' for chassis image. Allowed: image/jpeg, image/png.",
        )
    payload = await _read_upload_bounded(file, settings.max_image_bytes)
    entity = await chassis_client.read_chassis_number(payload, mime_type="image/jpeg" if mime != "image/png" else "image/png")
    return ChassisOcrResponse(
        frame_id=entity.frame_id,
        raw=entity.raw,
        confidence=entity.confidence,
        cached=entity.cached,
    )


@router.post("/api/v1/sheets/parse", response_model=ParserResponse, tags=["sheets"])
async def parse_sheet_file(
    file: UploadFile = File(...),
    force_refresh: bool = Query(default=False),
    parser_service: SheetParserService = Depends(get_parser_service_dep),
    settings: Settings = Depends(get_settings_dep),
) -> ParserResponse:
    """Parse an uploaded Japanese car auction sheet image."""
    _validate_upload_content_type(file)
    payload = await _read_upload_bounded(file, settings.max_image_bytes)
    filename = file.filename or "upload.png"
    try:
        result = await parser_service.parse_bytes(
            payload,
            filename=filename,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, APIError, TimeoutError) as exc:
        logger.warning("Single-sheet parse backend error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML extraction service is temporarily unavailable. Please retry.",
            headers={"Retry-After": "5"},
        ) from exc
    return to_parser_response(result)


@router.post("/api/v1/sheets/parse-url", response_model=ParserResponse, tags=["sheets"])
async def parse_sheet_url(
    body: ParseUrlRequest,
    parser_service: SheetParserService = Depends(get_parser_service_dep),
) -> ParserResponse:
    """Download an auction sheet image from a URL and parse it."""
    try:
        result = await parser_service.parse_url(
            str(body.url),
            force_refresh=body.force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, APIError, TimeoutError) as exc:
        logger.warning("URL sheet parse backend error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML extraction service is temporarily unavailable. Please retry.",
            headers={"Retry-After": "5"},
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to download remote image URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to download image from the provided URL.",
        ) from exc
    return to_parser_response(result)


@router.post(
    "/api/v1/lots/batches",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batches"],
)
async def create_batch(
    files: list[UploadFile] = File(...),
    force_refresh: bool = Query(default=False),
    batch_service: BatchParserService = Depends(get_batch_service_dep),
    settings: Settings = Depends(get_settings_dep),
) -> BatchCreateResponse:
    """Create an asynchronous batch parsing job for 1..10 auction sheet files."""
    if not files or len(files) > settings.batch_max_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch must contain between 1 and {settings.batch_max_items} files.",
        )
    for upload in files:
        _validate_upload_content_type(upload)
    items = [
        (
            await _read_upload_bounded(upload, settings.max_image_bytes),
            upload.filename or f"sheet_{index}.png",
        )
        for index, upload in enumerate(files)
    ]
    try:
        batch = await batch_service.create_batch(items, force_refresh=force_refresh)
    except BatchCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_batch_create_response(batch, poll_interval_ms=settings.batch_poll_interval_ms)


@router.get(
    "/api/v1/lots/batches/{batch_id}",
    response_model=BatchProgressResponse,
    tags=["batches"],
)
async def get_batch_progress(
    batch_id: UUID,
    batch_service: BatchParserService = Depends(get_batch_service_dep),
) -> BatchProgressResponse:
    """Poll batch parsing status and per-lot intermediate progress."""
    batch = await batch_service.get_batch(str(batch_id))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return to_batch_progress_response(batch)


@router.post(
    "/api/v1/lots/batches/{batch_id}/items",
    response_model=BatchProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batches"],
)
async def add_batch_items(
    batch_id: UUID,
    files: list[UploadFile] = File(...),
    force_refresh: bool = Query(default=False),
    batch_service: BatchParserService = Depends(get_batch_service_dep),
    settings: Settings = Depends(get_settings_dep),
) -> BatchProgressResponse:
    """Append additional auction sheet files to an existing active batch job."""
    if not files or len(files) > settings.batch_max_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least 1 and at most {settings.batch_max_items} files may be added per request.",
        )
    for upload in files:
        _validate_upload_content_type(upload)
    items = [
        (
            await _read_upload_bounded(upload, settings.max_image_bytes),
            upload.filename or f"sheet_{index}.png",
        )
        for index, upload in enumerate(files)
    ]
    try:
        batch = await batch_service.add_items(str(batch_id), items, force_refresh=force_refresh)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.") from exc
    except BatchConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_batch_progress_response(batch)
