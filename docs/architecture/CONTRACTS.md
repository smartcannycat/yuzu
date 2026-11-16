# API Contracts & Domain Invariants

> Machine-readable HTTP contract SSOT: [`docs/architecture/openapi.json`](./openapi.json) → generated TypeScript types at [`frontend/src/types/api.generated.ts`](../../frontend/src/types/api.generated.ts).  
> Sync commands from repo root: `make openapi` (regenerate) and `make check-contracts` (verify in CI/dev).

## 1. Serialization & Error Handling

1. **Zero-Float Currency Rule:**
   - All `RUB` and `JPY` monetary amounts in API payloads and DB models are integers (`int`, rounded half-up where converted).
   - Exchange rates (`jpy_rub`, `eur_rub`, `usd_rub`) are `float`.
   - Customs duty in EUR (`duty_rate_eur_per_cc`, `customs_duty_eur`) uses `float` rounded to 2 decimal places.
2. **Strict Pydantic Schemas:**
   - API request/response schemas inherit from `apps.core.schemas.StrictBaseModel` (`extra="forbid"`, `str_strip_whitespace=True`, `use_enum_values=True`).
3. **Identifiers & Timestamps:**
   - Primary IDs (`lot_id`, `batch_id`, `user_id`) are `UUID` (RFC 4122 v4).
   - Timestamps are UTC ISO 8601.
4. **RFC 7807 Problem Details:**
   - All `4xx`/`5xx` API errors return `application/problem+json` (`type`, `title`, `status`, `detail`, optional `instance`, `timestamp`, `invalid_params`).

## 2. Canonical Enums (`backend/apps/core/enums.py`)

- **Traffic Light (`TrafficLightColor`):** `green` (`net_benefit_rub >= 150_000` and no critical/warning risks), `yellow` (benefit `50_000..149_999` or warning/cosmetic risks), `red` (critical stop factors, `meti_sanction_risk`, or benefit `< 50_000`).
- **Batch Lifecycle (`BatchStatus`):** `queued`, `processing`, `completed`, `partial_failed`, `failed`.
- **Item Lifecycle (`ItemProcessingStatus`):** `queued`, `processing`, `ready`, `failed`.
- **Pipeline Steps (`TaskStep`):** `gatekeeper` → `fast_header_ocr` → `gemini_ocr` → (`cross_audit`, `drom_market`, `farpost_parts`) → `customs_calc` → `scoring` → `completed` / `failed`.
- **Defect Codes (`DefectCode`):** `A`, `U`, `W`, `S`, `C`, `XX`, `X`, `P`, `G`, `R`.
- **Power & Utilization (`PowerHpSource`, `UtilFeeType`):** `drom_catalog`, `katashiki_cache`, `manual`; `personal` vs `commercial` (160 HP cutoff enforced; when `is_under_160_hp is not True`, commercial util applies).
- **Parts Source (`PartSourceKind`):** Frontend must branch on `PartSourceKind` enums (`farpost_color_match`, `farpost_plain`, `farpost_cache`, `missing_identity`, `rate_limited`, `fetch_error`, `not_found`, `matrix`), never by parsing localized Russian labels.

## 3. Bid & Simulator Floor

- Minimum auction bid / slider floor is **`100_000 JPY`** (`Lot.bid_slider_min_jpy`, `RecalculateRequest.target_bid_jpy`, frontend RUB floor `Math.ceil(100_000 * jpy_rub)`).
- Manual `custom_power_hp` updates recalculate utilization fee, METI flags (where applicable), verdict, and return updated `bid_slider_min_jpy`, `power_hp`, `power_hp_source`, `is_under_160_hp`, and `ocr_warnings` directly in `RecalculateResponse`.
