# API Contracts & Domain Invariants

> Machine-readable HTTP contract SSOT: [`docs/architecture/openapi.json`](./openapi.json) -> generated TypeScript types at [`frontend/src/types/api.generated.ts`](../../frontend/src/types/api.generated.ts).
> Detailed change specifications live in [`docs/architecture/specs/`](./specs/README.md): [`001`](./specs/001-httponly-refresh-auth-and-logout.md), [`002`](./specs/002-private-media-storage-and-serving.md), and [`003`](./specs/003-cross-service-contracts-and-enums.md).
> Sync commands from repo root: `make openapi` (regenerate) and `make check-contracts` (verify in CI/dev).

## 1. Serialization & Error Handling

1. **Zero-Float Currency Rule:**
   - All `RUB` and `JPY` monetary amounts in API payloads and DB models are integers (`int`, rounded half-up where converted).
   - Exchange rates (`jpy_rub`, `eur_rub`, `usd_rub`) are `float`.
   - Customs duty in EUR (`duty_rate_eur_per_cc`, `customs_duty_eur`) uses `float` rounded to 2 decimal places.
2. **Strict Pydantic Schemas:**
   - API request/response schemas inherit from `apps.core.schemas.StrictBaseModel` (`extra="forbid"`, `str_strip_whitespace=True`, `use_enum_values=True`).
   - `AuthTokensResponse` omits `refresh_token`; `DamagedPartItem.source_kind` is typed as `PartSourceKind`; `CustomsCalculation.util_fee_type` is exposed as `UtilFeeType`.
3. **Identifiers & Timestamps:**
   - Primary IDs (`lot_id`, `batch_id`, `user_id`) are `UUID` (RFC 4122 v4).
   - Timestamps are UTC ISO 8601.
4. **RFC 7807 Problem Details:**
   - All `4xx`/`5xx` API responses—including pre-Ninja middleware errors (`400`, `403`, `413`, `500`) and unhandled `SuspiciousOperation`/`RequestDataTooBig`/`DisallowedHost` exceptions on `/api/v1/*`—return `application/problem+json` (`type`, `title`, `status`, `detail`, optional `instance`, `timestamp`, `invalid_params`).
   - `docs/architecture/openapi.json` declares `application/problem+json` for all `4xx`/`5xx` responses.
5. **Plain-Text Domain Strings:**
   - Backend scoring strings (`TrafficLightVerdict.headline`, `short_verdict_label`, `Lot.verdict_headline`) are plain localized text without emojis; UI icons are derived by the frontend from `TrafficLightColor`.

## 2. Canonical Enums (`backend/apps/core/enums.py`)

- **Traffic Light (`TrafficLightColor`):** `green` (`net_benefit_rub >= 150_000` and no critical/warning risks), `yellow` (benefit `50_000..149_999` or warning/cosmetic risks), `red` (critical stop factors, `meti_sanction_risk`, or benefit `< 50_000`).
- **Batch Lifecycle (`BatchStatus`):** `queued`, `processing`, `completed`, `partial_failed`, `failed`.
- **Item Lifecycle (`ItemProcessingStatus`):** `queued`, `processing`, `ready`, `failed`.
- **Pipeline Steps (`TaskStep`):** `gatekeeper` -> `gemini_ocr` -> (`cross_audit`, `drom_market`, `farpost_parts`) -> `customs_calc` -> `scoring` -> `completed` / `failed`.
- **Body Panels (`BodyPanel`):** 16 canonical schematic panels (`front_bumper`, `rear_bumper`, `hood`, `roof`, `tailgate`, `front_left_fender`, `front_right_fender`, `front_left_door`, `front_right_door`, `rear_left_door`, `rear_right_door`, `rear_left_quarter`, `rear_right_quarter`, `left_sill`, `right_sill`, `windshield`) plus `other` (`BodyPanel.OTHER = "other"`), aligned across `ml_service` and `backend`; frontend renders `other` defects in the unpinned defect list without diagram pins.
- **Defect Codes (`DefectCode`):** `A`, `U`, `W`, `S`, `C`, `XX`, `X`, `P`, `G`, `R`.
- **Power & Utilization (`PowerHpSource`, `UtilFeeType`):** `drom_catalog`, `katashiki_cache`, `manual`; `personal` vs `commercial` (160 HP cutoff enforced; when `is_under_160_hp is not True`, commercial util applies; exposed via `CustomsCalculation.util_fee_type`).
- **Parts Source (`PartSourceKind`):** `DamagedPartItem.source_kind` uses `PartSourceKind` (`farpost_color_match`, `farpost_plain`, `farpost_cache`, `missing_identity`, `rate_limited`, `fetch_error`, `not_found`, `matrix`); frontend must branch on enum values, never by parsing localized Russian labels.

## 3. Authentication, Refresh Cookie & Rate Limits

- **Access Token in Memory:** `AuthTokensResponse` returns `access_token` for in-memory JavaScript storage only (never persisted to `localStorage` or `sessionStorage`) and omits `refresh_token`.
- **HttpOnly Refresh Cookie:** `register` (`201`), `login` (`200`), and `refresh` (`200`) issue the refresh JWT exclusively in the `yuzu_refresh_token` cookie (`HttpOnly`, `Secure` when `not DEBUG`, `SameSite=Lax`, `Path=/api/v1/auth/`).
- **Cookie-Only Refresh & Logout:**
  - `POST /api/v1/auth/refresh` requires no JSON body (`TokenRefreshRequest` removed), reads `yuzu_refresh_token`, rotates and blacklists consumed tokens (`ROTATE_REFRESH_TOKENS = True`, `BLACKLIST_AFTER_ROTATION = True`), and returns `200 AuthTokensResponse` (`401 ProblemDetail` when missing, invalid, expired, or revoked).
  - `POST /api/v1/auth/logout` returns `204`, blacklists the cookie refresh token via `ninja_jwt.token_blacklist` when present and valid, and clears `yuzu_refresh_token`.
- **CSRF / Origin Protection:** Cookie-authenticated endpoints (`/api/v1/auth/refresh`, `/api/v1/auth/logout`) require any present `Origin` (or `Referer` when `Origin` is absent) to match `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, or `request.get_host()`; any untrusted or malformed `Origin`/`Referer` is always rejected with `403` `application/problem+json` even when `X-Requested-With: YuzuSPA` is sent, and `X-Requested-With: YuzuSPA` is accepted only when both `Origin` and `Referer` are absent.
- **Login Rate Limits:** `POST /api/v1/auth/login` enforces both IP-based throttling (`auth:login:ip`, `limit=40`, `window_sec=60`) and IP-independent per-account throttling (`auth:login:email`, `limit=10`, `window_sec=60`, keyed by SHA-256 of normalized lowercase email).

## 4. Private Media Storage, Validation & Serving

- **Split Django `STORAGES`:** `default` (`MEDIA_ROOT`) stores processed JPEG scans and thumbnails (`Lot.sheet_scan`, `Lot.sheet_thumbnail`); `private_intake` (`PRIVATE_INTAKE_ROOT` outside `MEDIA_ROOT`, `base_url=None`) stores raw `BatchItem.original_file` uploads under UUID filenames.
- **No Public `/media/*` Serving:** Unauthenticated `/media/*` serving is disabled in Caddy (`frontend/docker/Caddyfile`, `docker-compose.prod.yml`) and Django (`backend/config/urls.py`, including `DEBUG=True`).
- **Authenticated Lot Media Endpoint:** `GET /api/v1/lots/{lot_id}/media/{kind}` (`kind` in `{"scan", "thumbnail"}`, `AppJWTAuth()`) requires ownership (`user=request.auth`), `completed_at__isnull=False`, `deleted_at__isnull=True`, and an existing file in storage (returning `404 ProblemDetail` otherwise). Responses return `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox; default-src 'none'`, and `Content-Disposition: inline; filename="lot-{kind}.{ext}"`.
- **Media URLs in Payloads:** `LotSummary.thumbnail_url` and `LotMediaLinks` (`sheet_thumbnail_url`, `sheet_scan_url`) emit `/api/v1/lots/{lot_id}/media/{kind}` when present (`None` / `""` when absent); frontend loads protected images via authenticated Bearer requests into `Blob` object URLs.
- **Strict Upload Validation & Cleanup:** Batch uploads require BOTH allowed extension (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`, `.heif`) AND allowed MIME type (when provided), `0 < size <= 15 MB`, and Pillow/HEIF decode verification (`Image.MAX_IMAGE_PIXELS = 50_000_000`, max side `12_000` px). Sanitized display filenames, UUID storage filenames, `transaction.on_rollback` deletion on batch abort, and cleanup of aged media plus incomplete failed-batch orphan lots (`orphan_failed_lots`) via `media_purge.py` are enforced.

## 5. Bid, Simulator Floor & Cross-Service Defaults

- Minimum auction bid / slider floor is **`100_000 JPY`** (`Lot.bid_slider_min_jpy`, `RecalculateRequest.bid_jpy`, frontend RUB floor `Math.ceil(100_000 * jpy_rub)`).
- Manual `custom_power_hp` updates recalculate utilization fee, METI flags (where applicable), verdict, and return updated `bid_slider_min_jpy`, `power_hp`, `power_hp_source`, `is_under_160_hp`, and `ocr_warnings` directly in `RecalculateResponse`.
- Backend-to-ML HTTP client timeout `ML_SERVICE_TIMEOUT_SEC` defaults to `65.0` s (> `ml_service` `gemini_request_deadline_seconds = 45.0`).
- `ml_service` resolves default `reference_year` / `reference_month` dynamically in `Asia/Tokyo` (JST) when not explicitly overridden.
