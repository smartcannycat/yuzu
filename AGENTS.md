# Repository Agent Guidelines (`AGENTS.md`)

## 1. Repository Map

- `backend/` — Django 6 + Ninja Extra + Celery + PostgreSQL 16 (`backend/AGENTS.md`)
- `ml_service/` — FastAPI OCR & auction sheet normalization microservice
- `frontend/` — Vue 3 + TypeScript + Vite + Pinia (`frontend/AGENTS.md`)
- `docs/` — Single documentation hub:
  - `docs/architecture/` (`SYSTEM_OVERVIEW.md`, `BACKEND_LAYERS.md`, `CONTRACTS.md`, `openapi.json`, `specs/`)
  - `docs/product/` (specs, design system, benchmark case)
  - `docs/archive/` (historical planning, research, legacy contracts — read-only reference)

## 2. Config & Secrets Policy

- Committed non-secret defaults (timeouts, limits, TTLs, model chains) live in `backend/config.toml` and `ml_service/config.toml`.
- Secrets, database/proxy credentials, and deployment hostnames live in root `.env` (template `.env.example`) or `ml_service/.env.example` for standalone ML nodes.
- Do not add new `.env.example` files in subprojects or reintroduce `USE_SQLITE` / SQLite database paths.

## 3. Contract-First & AI Documentation Discipline

1. Write a short 1-page RFC in `docs/architecture/specs/NNN-feature.md` before changing cross-service behavior.
2. Backend Pydantic `StrictBaseModel` schemas are the single runtime source of truth for REST contracts.
3. After any controller/schema change, run `make openapi` from repo root to update `docs/architecture/openapi.json` and `frontend/src/types/api.generated.ts`, then verify with `make check-contracts`.
4. Never create duplicate documentation trees outside `docs/` (`planning/`, `research/` remain archived under `docs/archive/`). Clean up temporary scratch files before finishing.

## 4. Verification Before Finishing

- From repo root: `make check-contracts` and `make check-architecture`.
- Per modified service: `cd backend && make check`, `cd ml_service && make check`, `cd frontend && make check`.
- Keep all code, comments, technical docs, and commit messages in English (no emojis in code/commits/docs; Russian only for localized user-facing product strings).
