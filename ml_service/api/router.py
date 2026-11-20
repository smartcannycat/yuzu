"""Thin FastAPI controllers for single-sheet parsing, chassis OCR, and batch jobs."""

import asyncio
import logging
from uuid import UUID

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from google.genai.errors import APIError

from ml_service.api.dependencies import (
    get_batch_service_dep,
    get_chassis_ocr_client_dep,
    get_key_pool_dep,
    get_parser_service_dep,
    get_settings_dep,
    pre_auth_rate_limit_dep,
    rate_limit_dep,
    require_api_key_dep,
)
from ml_service.api.errors import raise_service_unavailable
from ml_service.api.mappers import (
    to_batch_create_response,
    to_batch_progress_response,
    to_parser_response,
)
from ml_service.api.schemas import (
    BatchCreateResponse,
    BatchProgressResponse,
    ChassisOcrResponse,
    HealthResponse,
    ParserResponse,
    ParseUrlRequest,
)
from ml_service.api.uploads import (
    ALLOWED_CHASSIS_UPLOAD_MIMES,
    declared_sizes_sum,
    read_upload_bounded,
    stage_batch_uploads,
    validate_upload_content_type,
)
from ml_service.config import Settings, resolve_reference_date
from ml_service.infrastructure.image_formats import (
    CHASSIS_MAX_IMAGE_DIMENSION,
    CHASSIS_MAX_IMAGE_PIXELS,
)
from ml_service.infrastructure.image_loader import verify_image_mime
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.services.batch_parser_service import (
    BatchCapacityError,
    BatchConflictError,
    BatchParserService,
    StagedBatchItem,
)
from ml_service.services.sheet_parser_service import SheetParserService

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[
        Depends(pre_auth_rate_limit_dep),
        Depends(require_api_key_dep),
        Depends(rate_limit_dep),
    ]
)


async def _discard_if_supported(
    batch_service: BatchParserService, staged_refs: list[StagedBatchItem]
) -> None:
    if staged_refs and hasattr(batch_service, "discard_staged"):
        await batch_service.discard_staged(staged_refs)


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(
    settings: Settings = Depends(get_settings_dep),
    key_pool: GeminiKeyPool = Depends(get_key_pool_dep),
) -> HealthResponse:
    """Return service health status and safe non-secret configuration counters."""
    ref_year, _ = resolve_reference_date(settings.reference_year, settings.reference_month)
    return HealthResponse(
        status="ok",
        keys_configured=key_pool.key_count,
        reference_year=ref_year,
    )


@router.post("/api/v1/chassis/read", response_model=ChassisOcrResponse, tags=["chassis"])
async def read_chassis_number(
    file: UploadFile = File(...),
    chassis_client=Depends(get_chassis_ocr_client_dep),
    settings: Settings = Depends(get_settings_dep),
) -> ChassisOcrResponse:
    """Read the chassis/frame number printed in an uploaded chassis image."""
    validate_upload_content_type(
        file,
        allowed_mimes=ALLOWED_CHASSIS_UPLOAD_MIMES,
        allowed_description="image/jpeg, image/png",
    )
    payload = await read_upload_bounded(file, settings.max_image_bytes)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image payload is empty.",
        )
    try:
        detected_mime = await asyncio.to_thread(
            verify_image_mime,
            payload,
            max_pixels=CHASSIS_MAX_IMAGE_PIXELS,
            max_dimension=CHASSIS_MAX_IMAGE_DIMENSION,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if detected_mime not in {"image/jpeg", "image/png"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image format '{detected_mime}' for chassis image. "
                "Allowed: image/jpeg, image/png."
            ),
        )
    try:
        entity = await chassis_client.read_chassis_number(payload, mime_type=detected_mime)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, APIError, TimeoutError, httpx.HTTPError) as exc:
        logger.warning("Chassis OCR backend error: %s", exc)
        raise_service_unavailable(
            "ML chassis OCR service is temporarily unavailable. Please retry."
        )
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
    validate_upload_content_type(file)
    payload = await read_upload_bounded(file, settings.max_image_bytes)
    filename = file.filename or "upload.png"
    try:
        result = await parser_service.parse_bytes(
            payload,
            filename=filename,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, APIError, TimeoutError, httpx.HTTPError) as exc:
        logger.warning("Single-sheet parse backend error: %s", exc)
        raise_service_unavailable("ML extraction service is temporarily unavailable. Please retry.")
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
        raise_service_unavailable("ML extraction service is temporarily unavailable. Please retry.")
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
        validate_upload_content_type(upload)
    declared_bytes = declared_sizes_sum(files, settings.max_image_bytes)

    staged_refs: list[StagedBatchItem] = []
    try:
        if hasattr(batch_service, "preflight_create"):
            batch_service.preflight_create(item_count=len(files), declared_bytes=declared_bytes)
        items, staged_refs = await stage_batch_uploads(
            files, max_image_bytes=settings.max_image_bytes, batch_service=batch_service
        )
        batch = await batch_service.create_batch(items, force_refresh=force_refresh)
    except BatchCapacityError as exc:
        await _discard_if_supported(batch_service, staged_refs)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except ValueError as exc:
        await _discard_if_supported(batch_service, staged_refs)
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
            detail=(
                f"At least 1 and at most {settings.batch_max_items} files may be added per request."
            ),
        )
    for upload in files:
        validate_upload_content_type(upload)
    declared_bytes = declared_sizes_sum(files, settings.max_image_bytes)

    staged_refs: list[StagedBatchItem] = []
    try:
        if hasattr(batch_service, "preflight_add_items"):
            batch_service.preflight_add_items(
                str(batch_id), item_count=len(files), declared_bytes=declared_bytes
            )
        items, staged_refs = await stage_batch_uploads(
            files, max_image_bytes=settings.max_image_bytes, batch_service=batch_service
        )
        batch = await batch_service.add_items(str(batch_id), items, force_refresh=force_refresh)
    except KeyError as exc:
        await _discard_if_supported(batch_service, staged_refs)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found."
        ) from exc
    except BatchConflictError as exc:
        await _discard_if_supported(batch_service, staged_refs)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except BatchCapacityError as exc:
        await _discard_if_supported(batch_service, staged_refs)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except ValueError as exc:
        await _discard_if_supported(batch_service, staged_refs)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_batch_progress_response(batch)
