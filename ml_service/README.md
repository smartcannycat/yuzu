# Auction Sheet Parser Microservice (`ml-service`)

Async FastAPI microservice for OCR, translation, and normalization of Japanese car auction inspection sheets in a layered DDD architecture (`domains` <- `factories` <- `services` <- `infrastructure` & `api`).

## Architecture

- `domains/` - Pure `@dataclass` entities (`entities.py`, `batch_entities.py`) and `StrEnum` types (`AuctionHouse`, `BodyPanel`, `DefectCode`, `TaskStep`, `BatchStatus`, `BatchItemState`) with zero dependencies on FastAPI, Pydantic, or Pillow.
- `factories/` - Deterministic normalizers for Japanese era and Gregorian dates (`date_normalizer.py`, `R`/`H`/`S`, kanji, bare years with dynamic `Asia/Tokyo` default), `Frame ID` synthesis, defect code parsing (`DefectCode`, `S`/`C` small markers, `R`, `description_ru`, preserving unknown codes as `unknown_defect_code:<code>`), auction house token matching (`D1`), transmission/color normalization, structural risk-flag derivation (`defect_normalizer.py`), Russian Markdown rendering (`markdown_renderer.py`), and `SheetFactory`.
- `infrastructure/`:
  - `AsyncImageLoader` (`httpx` with `trust_env=False`, SHA-256 fingerprinting, Pillow + `pillow-heif` format/dimension verification with `Image.MAX_IMAGE_PIXELS = 50_000_000`, streaming size caps, SSRF validation rejecting credentials and `fec0::1`/internal IPs, resolved IP pinning with `Host` + TLS `sni_hostname`, and total download `asyncio.timeout`);
  - `PillowImageCropper` (margin trimming, 2x2 overlapping 60%x60% quadrants, compact `JPEG` output `1000-1400 px`, `quality=88`, explicit pixel/dimension guards);
  - `ResultCache` & `atomic_io.py` (two-tier LRU memory + atomic disk JSON cache keyed by image digest, reference date, auction strictness, and schema/prompt version, with TTL + disk byte quota eviction and graceful `OSError` handling);
  - `GeminiKeyPool` (round-robin API key pool with per-key sliding-window RPM tracking, cooldowns, and lock/semaphore release before sleep);
  - `GeminiRunner`, `AsyncGeminiVisionClient`, and `ChassisOcrClient` (shared async `client.aio` execution layer, `gemini-decision-1` Gatekeeper with `fail_open`, `FastHeaderPreview`, hedged failover across fallback models with `401`/`403` fail-fast, and clean SDK shutdown).
- `services/` - `SheetParserService` and `BatchParserService` (1..10 item batches with UUID v4, pre-read capacity & global queued-bytes enforcement, disk spill under `cache_dir`, completion-based TTL, sanitized error reporting, and Live Polling with `mascot` and `preview_title`).
- `api/` - Thin FastAPI controllers, pre-auth IP rate limiting + constant-time `X-API-Key` authentication (`hmac.compare_digest`, fail-closed `503`), async post-auth IP rate limiting, strict `extra="forbid"` schemas, and RFC 7807 Problem Details (`application/problem+json` for `400`, `401`, `404`, `409`, `422`, `429`, `500`, `502`, `503`).

---

## Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ML_SERVICE_API_KEY` | `""` | Service secret for required `X-API-Key` header on all endpoints (including `/health`) |
| `ML_SERVICE_API_KEYS` | `""` | Comma-separated `X-API-Key` rotation list (takes precedence over `ML_SERVICE_API_KEY`) |
| `GEMINI_API_KEYS` | `""` | Comma-separated Gemini API key pool |
| `GEMINI_API_KEY` | `""` | Fallback single Gemini API key when `GEMINI_API_KEYS` is empty |
| `GEMINI_DECISION_MODEL` | `gemini-decision-1` | Gatekeeper model for sheet classification and complexity routing |
| `GEMINI_FLASH_MODEL` | `gemini-3.6-flash` | Primary Vision extraction model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3-flash-preview,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite` | Fallback model chain on transient outages or rate limits |
| `ENABLE_GATEKEEPER` | `true` | Enable Gatekeeper pre-screening via `gemini-decision-1` |
| `GEMINI_GATEKEEPER_FAIL_OPEN` | `true` | Proceed to extraction when Gatekeeper is unavailable |
| `GEMINI_RPM_LIMIT` | `5` | Max requests per minute per Gemini API key |
| `GEMINI_REQUEST_TIMEOUT_MS` | `25000` | Single model call timeout in milliseconds |
| `GEMINI_SDK_MAX_ATTEMPTS` | `1` | SDK internal retry attempts before model failover |
| `GEMINI_MODEL_COOLDOWN_SECONDS` | `120.0` | Cooldown duration after transient model errors (`503`/`504`/timeout) |
| `GEMINI_CLIENT_ERROR_COOLDOWN_SECONDS` | `300.0` | Cooldown duration after model `400`/`404` responses |
| `GEMINI_KEY_COOLDOWN_SECONDS` | `30.0` | Key cooldown duration after HTTP `429` |
| `GEMINI_MAX_KEY_TRIES` | `3` | Max key attempts per model on `429` |
| `GEMINI_THINKING_LEVEL` | `LOW` | Gemini 3 thinking level (`MINIMAL`, `LOW`, `MEDIUM`, `HIGH`) |
| `GEMINI_REQUEST_DEADLINE_SECONDS` | `45.0` | Total extraction deadline across the model chain |
| `GEMINI_HEDGE_DELAY_SECONDS` | `8.0` | Delay before launching a hedged fallback model |
| `GEMINI_FAST_HEADER_TIMEOUT_SECONDS` | `1.2` | Strict timeout for fast header preview (`preview_title`) |
| `DEFAULT_AUCTION_STRICTNESS` | `0.65` | Default strictness index for `AuctionHouse.OTHER` |
| `BATCH_POLL_INTERVAL_MS` | `1500` | Suggested polling interval returned in `202 Accepted` |
| `BATCH_MAX_ITEMS` | `10` | Max files allowed per batch |
| `BATCH_MAX_CONCURRENCY` | `3` | Max concurrent items processed in batches |
| `BATCH_MAX_STORED_BATCHES` | `200` | Max batches retained in memory |
| `BATCH_TTL_SECONDS` | `1800` | Retention TTL after batch completion |
| `BATCH_MAX_QUEUED_BYTES` | `268435456` | Global cap on queued batch payload bytes across active batches |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `120` | Post-auth per-IP RPM limit (`0` disables) |
| `PRE_AUTH_RATE_LIMIT_REQUESTS_PER_MINUTE` | `300` | Pre-auth per-IP RPM limit before key verification (`0` disables) |
| `ENABLE_DOCS` | `false` | Expose `/docs`, `/redoc`, and `/openapi.json` when explicitly set to `true` |
| `CORS_ALLOWED_ORIGINS` | `[]` | Allowed CORS origins (empty disables CORS middleware) |
| `CROP_FORMAT` | `JPEG` | Quadrant output format (`JPEG`, `WEBP`, `PNG`) |
| `CROP_QUALITY` | `88` | Compression quality for `JPEG`/`WEBP` (`50..100`) |
| `CROP_MIN_PX` / `CROP_MAX_PX` | `1000` / `1400` | Normalized longest side bounds |
| `MAX_IMAGE_SIZE_MB` | `15` | Maximum input file size in MiB |
| `CACHE_DIR` | `.cache/sheets` | Disk cache directory (relative paths resolve under `ml_service/`) |
| `CACHE_TTL_SECONDS` | `604800.0` | Disk/memory cache TTL in seconds (`0` disables expiry) |
| `CACHE_MAX_DISK_MB` | `512` | Disk cache size quota in MiB |
| `REFERENCE_YEAR` / `REFERENCE_MONTH` | `None` / `None` | Optional overrides for age/corridor checks; defaults dynamically to `Asia/Tokyo` (JST) |

---

## Quick Start (Local with `uv`)

Run all commands from the `ml_service` directory:

```bash
uv sync
cp .env.example .env
```

Or via `Makefile` (also installs repository `lefthook` git hooks):

```bash
make install
```

Set `ML_SERVICE_API_KEY` and `GEMINI_API_KEYS` in `.env`, then start the server on port **8001** (expected by backend `ML_SERVICE_URL=http://127.0.0.1:8001`):

```bash
uv run uvicorn ml_service.main:app --host 127.0.0.1 --port 8001 --reload
# or: make dev
```

When `ENABLE_DOCS=true`, OpenAPI documentation is available at `http://localhost:8001/docs`.

---

## Running in Docker

From `ml_service` (production target by default):

```bash
docker compose up --build -d
```

Build dev image with dev dependencies and reload:

```bash
docker build --target dev -t yuzu-ml-service:dev .
```

Or build and run the production image manually:

```bash
docker build -t yuzu-ml-service .
docker run --rm -p 8001:8001 --env-file .env -v "${PWD}/.cache:/app/ml_service/.cache" yuzu-ml-service
```

The container listens on port `8001` (Compose service name `ml`, matching `ML_SERVICE_URL=http://ml:8001` in `backend`).

---

## Endpoints & Examples

All endpoints below (including `/health`) require the `X-API-Key` header (`401 Unauthorized` when missing/invalid, `503 Service Unavailable` when no service key is configured):

- `GET /health` - Service liveness, configured Gemini key count, and effective reference year.
- `POST /api/v1/chassis/read` - OCR chassis/frame number from a small image (`multipart/form-data`, `file`, `image/jpeg` or `image/png`, max 25 MP / 8000 px).
- `POST /api/v1/sheets/parse` - Upload and parse a single sheet (`multipart/form-data`, `file`, optional `?force_refresh=true`).
- `POST /api/v1/sheets/parse-url` - Fetch and parse an image from a remote URL (`{"url": "...", "force_refresh": false}`).
- `POST /api/v1/lots/batches` - Create an async batch job for `1..10` files (`202 Accepted`, `batch_id: UUID`).
- `GET /api/v1/lots/batches/{batch_id}` - Poll batch status (`total_count`, `mascot`, `items[].preview_title`) and parsed results.
- `POST /api/v1/lots/batches/{batch_id}/items` - Append files to an active batch (`202 Accepted`, or `409 Conflict` if already terminal).

```bash
curl -H "X-API-Key: <ML_SERVICE_API_KEY>" http://localhost:8001/health
curl -H "X-API-Key: <ML_SERVICE_API_KEY>" -X POST "http://localhost:8001/api/v1/sheets/parse" -F "file=@/path/to/sheet.png"
```

## Running Tests & Linter

```bash
make check
# or individually:
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest --cov=ml_service --cov-report=term-missing
```
