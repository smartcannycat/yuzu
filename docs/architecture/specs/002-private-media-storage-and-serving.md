# 002: Private Media Storage, Strict Upload Validation, and Authenticated Serving

- **Status:** Approved
- **Services affected:** backend, frontend, infra

## Problem & Goal
Serving auction sheet files directly under a public `/media/*` route in Caddy and Django exposes user uploads and processed scans without authentication or ownership checks (`BE-SEC-02`, `BE-SEC-03`). In addition, upload validation previously accepted files matching either extension or MIME type (`BE-SEC-01`), stored raw files alongside public media under user-supplied names (`BE-SEC-11`), lacked pixel/dimension decompression-bomb limits (`BE-MAJ-03`), and left orphaned files on disk on transaction rollback. This specification splits Django storage backends, removes all public `/media/*` serving, enforces strict upload validation and image bounds, and delivers lot scans and thumbnails exclusively through an authenticated API endpoint.

## Contract & Domain Invariants

- **Split Django `STORAGES` (`BE-SEC-02`, `BE-SEC-03`, `BE-SEC-11`):**
  - `default`: `FileSystemStorage` rooted at `MEDIA_ROOT` for processed browser-ready JPEG scan and thumbnail files (`Lot.sheet_scan`, `Lot.sheet_thumbnail`).
  - `private_intake`: `FileSystemStorage(location=PRIVATE_INTAKE_ROOT, base_url=None)` for raw uploaded files (`BatchItem.original_file`), where `PRIVATE_INTAKE_ROOT` (default `"private_intake"`) resides outside `MEDIA_ROOT`.
  - `BatchItem.original_file` binds `private_intake` via a callable storage getter (`_get_private_intake_storage`); historical upload helpers (`_batch_item_upload_to`, `_lot_scan_upload_to`, `_lot_thumb_upload_to`) remain defined in `apps/lots/models/__init__.py` to preserve `0001_initial` migration compatibility.
- **Public `/media/*` Removal (`BE-SEC-02`):**
  - Remove `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` from `backend/config/urls.py` across all environments, including `DEBUG=True`.
  - Remove `handle_path /media/*` from `frontend/docker/Caddyfile` and drop the read-only `media_data_prod` mount from the `frontend` service in `docker-compose.prod.yml`.
- **Authenticated Lot Media Endpoint:**
  - Route: `GET /api/v1/lots/{lot_id}/media/{kind}`, authenticated via `AppJWTAuth()`, where `kind` is restricted to `{"scan", "thumbnail"}` (unauthenticated requests return `401 ProblemDetail`; invalid `kind` returns `422 ProblemDetail`).
  - Access & lifecycle predicate: lot must satisfy `id=lot_id`, `user=request.auth`, `completed_at__isnull=False`, `deleted_at__isnull=True`, and the target `sheet_scan` or `sheet_thumbnail` file must exist in storage; any failure returns `404` `application/problem+json` (`ProblemDetail`).
  - Response: streams `FileResponse` with guessed image `Content-Type` and mandatory hardening headers:
    - `Cache-Control: private, no-store`
    - `X-Content-Type-Options: nosniff`
    - `Content-Security-Policy: sandbox; default-src 'none'`
    - `Content-Disposition: inline; filename="lot-{kind}.{ext}"`
  - API link serialization (`apps/lots/api/queries/helpers.py`): `_build_thumbnail_url(lot)` emits `/api/v1/lots/{lot.id}/media/thumbnail` when present (`None` when absent); `_build_media_links(lot)` emits `/api/v1/lots/{lot.id}/media/thumbnail` and `/api/v1/lots/{lot.id}/media/scan` when present (`""` when absent).
  - Frontend clients fetch protected scan/thumbnail URLs using Bearer authorization via the HTTP client into `Blob` object URLs (`URL.createObjectURL`) and revoke them on cleanup.
- **Strict Upload Validation, Image Bounds & Cleanup (`BE-SEC-01`, `BE-MAJ-03`, `BE-SEC-11`):**
  - Upload validation (`apps/lots/pipeline/batches.py`) requires **both** a whitelisted extension (`{".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}`) **and** a whitelisted MIME type (`{"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}`) whenever `content_type` is sent.
  - Size bounds reject `size is None or size <= 0 or size > 15 * 1024 * 1024` (15 MB) with `400 ProblemDetail`.
  - Pillow/HEIF decode verification (`batches.py` and `apps/lots/media.py`) registers HEIF (`ensure_heif_registered()`), sets `Image.MAX_IMAGE_PIXELS = 50_000_000`, validates `img.format in {"JPEG", "PNG", "WEBP", "HEIF"}`, and enforces max side `12_000` px and total pixels `<= 50_000_000`; `UnidentifiedImageError`, `Image.DecompressionBombError`, `OSError`, and `SyntaxError` raise `400 BadRequestProblemError`.
  - Original display name is sanitized (`Path(upload.name or "sheet").name[:255]`), raw files are persisted under generated UUID names (`f"{uuid.uuid4().hex}{ext}"`), `transaction.on_rollback` deletes written intake files if batch creation aborts, and `apps/lots/media_purge.py` purges aged soft-deleted lot media, aged terminal batch `original_file` uploads, and `sheet_scan`/`sheet_thumbnail` files for incomplete failed-batch orphan lots (`orphan_failed_lots`: `completed_at__isnull=True`, `deleted_at__isnull=True`, `batch_item__status=FAILED`), without scanning disk directories for arbitrary unreferenced files.

## Verification Plan
- **Backend (`backend/tests/test_lots_api.py`, `backend/tests/test_worker_and_hardening.py`):** Verify `GET /api/v1/lots/{lot_id}/media/{kind}` enforces ownership, completion, soft-delete exclusion, security headers, and `401`/`404`/`422` responses; verify `/media/*` returns `404` in Django URLs; verify extension/MIME mismatch rejection, `0`-byte/`>15 MB` rejection, pixel/dimension bomb rejection, UUID storage names under `PRIVATE_INTAKE_ROOT`, rollback file deletion, and aged/failed-orphan cleanup (`orphan_failed_lots`) in `media_purge.py`.
- **Infra:** Verify `frontend/docker/Caddyfile` and `docker-compose.prod.yml` contain no unauthenticated `/media/*` file server routes.
- **Contract Sync:** Run `make openapi` and verify `make check-contracts` passes cleanly.
