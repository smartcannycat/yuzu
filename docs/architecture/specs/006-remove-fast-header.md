# 006: Remove Separate `fast_header` OCR Step & Retain `preview_title` from Primary Parse

- **Status:** Approved
- **Services affected:** ml_service, backend, frontend

## Problem & Goal
`fast_header` (`extract_fast_header` in `ml_service`, `TaskStep.FAST_HEADER_OCR` across services) previously ran an extra low-resolution Gemini Vision call per uploaded auction sheet just to extract `make`, `model`, and `lot_number` ahead of full extraction. Because the backend integrates via synchronous `POST /api/v1/sheets/parse`, that extra Gemini call never accelerated progress display in production while doubling Gemini RPM pressure and cost (especially when combined with `ThinkingLevel.MINIMAL` rejections).

## Changes
- **Remove `fast_header` Gemini OCR & Config (`ml_service`):**
  - Remove `extract_fast_header`, `FastHeaderPreviewSchema`, `FastHeaderPreviewEntity`, `enable_fast_header`, `fast_header_timeout_seconds`, and `on_preview` plumbing across `ml_service`.
- **Remove `TaskStep.FAST_HEADER_OCR` (`ml_service`, `backend`, `frontend`):**
  - Remove `FAST_HEADER_OCR = "fast_header_ocr"` from `TaskStep` in `ml_service/domains/enums.py` and `backend/apps/core/enums.py`.
  - Add migration `0011_remove_fast_header_task_step` updating any historical `BatchItem.current_step="fast_header_ocr"` rows to `"gemini_ocr"` and altering `BatchItem.current_step` choices.
  - Regenerate `docs/architecture/openapi.json` and `frontend/src/types/api.generated.ts`, and remove `fast_header_ocr` from frontend `formatters.ts` and mock simulation steps.
- **Retain `BatchItem.preview_title` from Primary Parse:**
  - Keep `BatchItem.preview_title` in the API contract so the batch progress card (`BatchItemCard.vue`) still renders `Make Model #Lot` after the primary sheet extraction completes while enrichment (`cross_audit`, `drom_market`, `farpost_parts`) continues, with zero extra Gemini calls.
