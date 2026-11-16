# Backend Agent Guidelines

## 1. General Rules

- Language: English only for code, comments, technical documentation, and commit messages. User-facing error strings (`ProblemDetail`, `invalid_params[].reason`) and localized product labels follow `../docs/architecture/CONTRACTS.md` (Russian).
- No Emojis: Never use emojis in code, comments, or commit messages.

## 2. Architecture & Strict Layering (`../docs/architecture/BACKEND_LAYERS.md`)

- `apps/core/` — Shared enums, `StrictBaseModel`, RFC 7807 `ProblemDetail` errors, Redis utils. Never imports `apps.lots`, `apps.users`, or `config`.
- `apps/users/` — Auth, custom `User` (`UUID` PK, lowercase `email`), JWT endpoints.
- `apps/lots/` — Keep `app_label = "lots"` migrations intact:
  - `models` — Django ORM models only; zero imports from `api`, `pipeline`, calculator, or `integrations`.
  - Calculator modules (`calculator/` / `customs`, `economics`, `recalc`, `scoring`, `safety`) — Pure business math and DB reads/writes; no HTTP/network calls, no Celery or Ninja controller imports.
  - Integrations (`integrations/` → `apps/integrations/`) — External HTTP/proxy/captcha/cache and parsers only; no customs math or REST controllers.
  - Pipeline (`pipeline/`) — Batch orchestration, Celery tasks, retries, and recovery.
  - API (`api`, queries, schemas) — Thin Ninja Extra `@api_controller` endpoints delegating work down cleanly.
- Automated boundary checks run via `uv run lint-imports` (`[tool.importlinter]` in `pyproject.toml`).

## 3. Code Size & Quality Rules

- **Soft module size limit: ~300–350 lines** (excluding migrations). When modifying a file already >350 lines, extract a focused submodule rather than adding more code to a monolith.
- **No blind `except Exception:`** (`BLE001` enabled in Ruff). Catch explicit exceptions or log explicitly at clear integration/worker boundaries.
- **Complexity limit:** Ruff enforces `C901` (`max-complexity = 12`). Extract cohesive helpers instead of deep nested conditionals.
- **Typing:** Python 3.12+ annotations (`list[str]`, `dict[str, Any]`, `X | None`) with `StrictBaseModel` (`extra="forbid"`, `use_enum_values=True`) for all API DTOs.

## 4. Commands & Workflow (`Makefile`)

- Package manager: strictly `uv` (`uv.lock`). Database: PostgreSQL 16 + `psycopg` (v3).
- `make dev` / `make migrate` / `make makemigrations`
- `make check` — Runs `ruff check .`, `ruff format --check .`, `lint-imports`, and `pytest`
- Export OpenAPI schema after API changes: `make openapi` (from repo root) or `uv run python -m config.openapi`
