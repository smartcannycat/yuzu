# 003: Cross-Service Enum Alignment, OpenAPI Error Media Types, and Timeout/Date Sync

- **Status:** Approved
- **Services affected:** backend, ml_service, frontend

## Problem & Goal
Cross-service contract drift currently breaks alignment across the backend, ML parser, and frontend: `ml_service` emits `BodyPanel.OTHER = "other"` while the backend enum and OpenAPI schema restrict `BodyPanel` to 16 schematic zones (`XSVC-02`), and OpenAPI leaves `DamagedPartItem.source_kind` as an untyped string, omits `CustomsCalculation.util_fee_type`, and advertises `application/json` instead of `application/problem+json` on `4xx`/`5xx` responses (`XSVC-06`). Additionally, the backend `ML_SERVICE_TIMEOUT_SEC` of `30.0` seconds is shorter than `ml_service`'s `45.0`-second Gemini deadline (`XSVC-01`), `ml_service` hardcodes `2026`/`11` as its default reference date (`ML-MIN-03`), and backend scoring embeds traffic-light emojis in `verdict_headline` (`BE-OOP-01`). This specification aligns enums, OpenAPI schema typing and error media types, timeouts, dynamic JST reference dates, and plain-text verdict headlines across all three services.

## Contract & Domain Invariants

- **`BodyPanel.OTHER = "other"` & Unpinned Defect Fallback (`XSVC-02`):**
  - `backend/apps/core/enums.py` adds `OTHER = "other"` to `BodyPanel` (17 values total), matching `ml_service/domains/enums.py` and updated DB `LotDefect.panel_id` / `DamagedPartItem.panel_id` choices.
  - Non-schematic panels (such as core support, crossmember, inner apron, pillar, or frame rails) normalize to `BodyPanel.OTHER` and persist as `LotDefect` rows rather than falling back to `extra_ru` warnings.
  - Frontend (`LotBodyDiagram.vue`, `lotDefects.ts`, `LotTabTech.vue`) guards SVG pin lookup against `panel_id === "other"` (or missing `BODY_PANEL_PIN_COORDS` entries) so unpinned defects render safely in the defect breakdown list without attempting to draw a pin on the 2D car diagram.
- **Typed Economics Fields in OpenAPI (`XSVC-06`):**
  - `DamagedPartItem.source_kind` in `backend/apps/lots/api/schemas/economics.py` is strictly typed as `PartSourceKind` (default `PartSourceKind.MATRIX`); `apps/lots/api/queries/helpers.py` coerces any legacy empty string in persisted rows to `PartSourceKind.MATRIX`.
  - `CustomsCalculation` adds `util_fee_type: UtilFeeType = Field(UtilFeeType.PERSONAL, ...)`, populated in `_build_customs_out` as `UtilFeeType.COMMERCIAL` when `customs.is_commercial_util` is `True` and `UtilFeeType.PERSONAL` otherwise.
- **`application/problem+json` in OpenAPI & Middleware (`XSVC-06`, `BE-MIN-02`):**
  - `backend/config/openapi.py` rewrites all `4xx`/`5xx` `ProblemDetail` response media types in `docs/architecture/openapi.json` from `application/json` to `application/problem+json`.
  - `ApiProblemDetailsMiddleware` converts pre-Ninja `400`/`403`/`413`/`500` responses and unhandled `SuspiciousOperation`, `RequestDataTooBig`, and `DisallowedHost` exceptions on `/api/v1/*` into `application/problem+json` `ProblemDetail` payloads.
- **Timeout & Dynamic JST Reference Date Alignment (`XSVC-01`, `ML-MIN-03`):**
  - `ML_SERVICE_TIMEOUT_SEC` default increases from `30.0` to `65.0` in `backend/config/settings/config.py` and `backend/config.toml` so backend HTTP calls allow `ml_service`'s `gemini_request_deadline_seconds = 45.0` plus preprocessing and serialization headroom.
  - `ml_service` replaces hardcoded `2026`/`11` reference-date defaults (`config.py`, `config.toml`, `SheetFactory`, `normalizers.py`) with dynamic current Japan Standard Time (`Asia/Tokyo`, UTC+9) year and month resolution when not explicitly configured, preserving explicit overrides for deterministic tests.
- **Emoji-Free Backend Verdict Headlines (`BE-OOP-01`):**
  - `backend/apps/lots/calculator/scoring.py` and seeded starter fixtures emit plain Russian text without leading emoji characters in `TrafficLightVerdict.headline`, `short_verdict_label`, and `Lot.verdict_headline`:
    - `green`: `"РЕКОМЕНДОВАНО К ПОКУПКЕ"`
    - `yellow`: `"ВНИМАНИЕ: ЕСТЬ НЮАНСЫ"`
    - `red`: `"ПОКУПКУ НЕ РЕКОМЕНДУЕМ"`
  - Status icons remain strictly a frontend presentation concern derived from `verdict: TrafficLightColor`.

## Verification Plan
- **Backend (`backend/tests/`):** Verify `BodyPanel.OTHER` persistence and serialization; verify `DamagedPartItem.source_kind` (`PartSourceKind`) and `CustomsCalculation.util_fee_type` (`UtilFeeType`) in lot detail and recalculate responses; verify `ML_SERVICE_TIMEOUT_SEC == 65.0`; verify `verdict_headline` contains no emojis; verify `docs/architecture/openapi.json` declares `application/problem+json` on `4xx`/`5xx` responses (`test_openapi_export.py`).
- **ML Service (`ml_service/tests/`):** Verify default reference date evaluates in `Asia/Tokyo` (JST) when unset and honors explicit `reference_year`/`reference_month` overrides.
- **Frontend & Contract Sync:** Verify `LotBodyDiagram.vue` and `LotTabTech.vue` render `panel_id: "other"` defects cleanly in the unpinned list; run `make openapi` and confirm `make check-contracts` passes cleanly.
