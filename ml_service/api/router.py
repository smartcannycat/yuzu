"""Thin FastAPI controllers for single-sheet parsing, batch jobs, and health checks."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from google.genai.errors import APIError
import httpx

from app.api.dependencies import (
    get_batch_service_dep,
    get_key_pool_dep,
    get_parser_service_dep,
    get_settings_dep,
)
from app.api.schemas import (
    BatchCreateResponse,
    BatchProgressResponse,
    HealthResponse,
    ParserResponse,
    ParseUrlRequest,
    to_batch_create_response,
    to_batch_progress_response,
    to_parser_response,
)
from app.config import Settings
from app.infrastructure.key_pool import GeminiKeyPool
from app.services.batch_parser_service import BatchParserService
from app.services.sheet_parser_service import SheetParserService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(
    settings: Settings = Depends(get_settings_dep),
    key_pool: GeminiKeyPool = Depends(get_key_pool_dep),
) -> HealthResponse:
    """Return service health status and safe non-secret configuration counters."""
    return HealthResponse(
        status="ok",
        keys_configured=key_pool.key_count,
        cache_dir=str(settings.cache_dir),
        reference_year=settings.reference_year,
    )


@router.post("/api/v1/sheets/parse", response_model=ParserResponse, tags=["sheets"])
async def parse_sheet_file(
    file: UploadFile = File(...),
    force_refresh: bool = Query(default=False),
    parser_service: SheetParserService = Depends(get_parser_service_dep),
) -> ParserResponse:
    """Parse an uploaded Japanese car auction sheet image."""
    payload = await file.read()
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download image from URL: {exc}",
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
) -> BatchCreateResponse:
    """Create an asynchronous batch parsing job for 1..10 auction sheet files."""
    items = [
        (await upload.read(), upload.filename or f"sheet_{index}.png")
        for index, upload in enumerate(files)
    ]
    try:
        batch = await batch_service.create_batch(items, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_batch_create_response(batch)


@router.get(
    "/api/v1/lots/batches/{batch_id}",
    response_model=BatchProgressResponse,
    tags=["batches"],
)
async def get_batch_progress(
    batch_id: str,
    batch_service: BatchParserService = Depends(get_batch_service_dep),
) -> BatchProgressResponse:
    """Poll batch parsing status and per-lot intermediate progress."""
    batch = await batch_service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return to_batch_progress_response(batch)


@router.post(
    "/api/v1/lots/batches/{batch_id}/items",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batches"],
)
async def add_batch_items(
    batch_id: str,
    files: list[UploadFile] = File(...),
    force_refresh: bool = Query(default=False),
    batch_service: BatchParserService = Depends(get_batch_service_dep),
) -> BatchCreateResponse:
    """Append additional auction sheet files to an existing batch job."""
    items = [
        (await upload.read(), upload.filename or f"sheet_{index}.png")
        for index, upload in enumerate(files)
    ]
    try:
        batch = await batch_service.add_items(batch_id, items, force_refresh=force_refresh)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_batch_create_response(batch)
