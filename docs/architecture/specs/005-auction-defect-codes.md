# 005: Complete Japanese Auction Sheet Defect Code Catalog & Severity 1..4 Alignment

- **Status:** Approved
- **Services affected:** ml_service, backend, frontend

## Problem & Goal
Production auction sheets across Japanese auction groups (USS, TAA, CAA, Honda, JU, ARAI, MIRIVE, ORIX, KCAA, LAA, ZIP, AUCNET) routinely use defect marks outside the original 10-code subset (`A, U, W, S, C, XX, X, P, G, R`), most notably `B1..B4` (dent with scratch), `E1..E3` (dimple), `H1..H4` (faded/peeling paint), `BP` / `BP1..BP4` (body & paint repair), `Y1..Y4` (plastic/body crack/tear, previously absent from `DefectCode` in `ml_service` despite existing in `repair_matrix.json`), and severity-4 marks (`A4`, `U4`, `B4`, `Y4`) as well as Japanese size suffixes (`小`/`中`/`大`), ranges (`B2-3`, `A1~2`), and concatenated pairs (`A2U2`, `B2W1`). Previously, unknown marks triggered `unknown_defect_code:*` warnings in `ml_service` and `Unknown repair defect code` generic bodywork fallbacks in `backend`, and `severity=4` defects caused Pydantic validation `HTTP 500` on lot detail endpoints (`NormalizedDefect.severity <= 3` vs mapper `_MAX_DEFECT_SEVERITY = 4`).

## Contract & Domain Invariants

- **Canonical 20-Code `DefectCode` Enum (`ml_service` & `backend`):**
  - `DefectCode` defines 20 values across `ml_service/domains/enums.py` and `backend/apps/core/enums.py`:
    `A, U, B, E, W, S, C, Y, P, H, G, O, T, L, F, M, BP, XX, X, R`.
  - Database schema requires zero migrations (`LotDefect.defect_types` stores unrestricted `ArrayField(CharField(max_length=10))`).
- **Deterministic Token Parsing (`ml_service/factories/defect_normalizer.py`):**
  - Dedicated tokens (`XX`, `BP`, `X`, `R` with optional `1..4`) are matched before multi-letter expansion so `BP`/`BP2` never splits into `B` + `P`.
  - Japanese size suffixes (`小 -> 1`, `中 -> 2`, `大 -> 3`), severity ranges (`1-2`, `2~3` -> conservative `max`), concatenated code-severity pairs (`A2U2`, `B2W1`, `BP2A1`), and multi-letter same-severity composites (`AU3`, `BW2`) normalize cleanly while invalid tokens (`Z9`, `A5`, `???`) still emit `unknown_defect_code:*` warnings.
- **Severity `1..4` API Schema Alignment & OpenAPI Sync:**
  - `backend/apps/lots/api/schemas/common.py` updates `NormalizedDefect.severity` bounds from `ge=1, le=3` to `ge=1, le=4`, matching `backend/apps/integrations/ml/mapper.py` (`_MAX_DEFECT_SEVERITY = 4`).
  - `docs/architecture/openapi.json` and `frontend/src/types/api.generated.ts` are regenerated and verified with `config.openapi --check` and `check:api`.
- **Farpost Matrix Coverage & Replacement Routing (`backend/apps/integrations/farpost/`):**
  - `repair_matrix.json` covers every canonical code across bare marks and severities `1..4` (plus `"maximum_severity"` including `"B": 3`) with zero `Unknown repair defect code` warnings for valid auction marks.
  - `matrix.py` expands composites, ranges, and `小`/`中`/`大` suffixes accurately, and `service.py` routes `X`/`XX` with optional severity (`X1..X4`, `XX1..XX4`) to replacement-part lookup.
- **Frontend Severity & Tone Classification (`frontend/src/components/lots/detail/lotDefects.ts`):**
  - Recognizes severities `1..4`, handles `BP`/`W`/`B`/`Y`/`S`/`P`/`H`/`C` tones deterministically without false `X` substring matches, and renders severity-4 and `C` marks cleanly.

## Verification Plan
- **`ml_service` (`pytest`):** Verify parsing, warnings retention for invalid tokens, Russian descriptions, and `DefectCode` round-trips across all 20 codes, severities `1..4`, ranges, `小`/`中`/`大`, and concatenated composites.
- **`backend` (`pytest` + contract sync):** Verify all 20 codes and composite forms produce zero `Unknown repair defect code` warnings in `_panel_codes`/`_operations`, `X1` routes to part replacement, `NormalizedDefect` accepts `severity=4` and rejects `5`, and OpenAPI/migrations checks pass.
- **`frontend` (`vitest` + `check:api` + `typecheck` + `build`):** Verify `getDefectTone` / `getDefectPriorityScore` coverage on `B2`, `B3`, `B4`, `A4`, `C1`, `BP2`, `Y2`, `E1`, `H2` and verify API types stay synchronized.
