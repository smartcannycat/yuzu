# Backend Agent Guidelines

## 1. General Rules

- Language: English only for code, comments, technical documentation, and commit messages. User-facing API error descriptions (`ProblemDetail.title`, `ProblemDetail.detail`, `invalid_params[].reason`) and localized product strings follow `../docs/API_DATA_CONTRACTS.md` (Russian).
- No Emojis: Never use emojis in code, comments, or commit messages.

## 2. Commands & Workflow (`Makefile`)

All project commands are defined in `Makefile` (`make help` lists every target):
- `make install` - Install dependencies via `uv sync` and install root Lefthook hooks
- `make up-db` / `make up` / `make down` - Manage dev PostgreSQL or full Docker Compose stack
- `make migrate` / `make makemigrations` - Run or generate Django migrations
- `make dev` - Run Granian ASGI server locally with reload (`127.0.0.1:8000`)
- `make lint` / `make format` / `make test` / `make check` - Run Ruff checks, formatting, and Pytest

## 3. Package Manager & Tooling

- Strictly use `uv` (`uv.lock`). Do not use pip, poetry, or pipenv.
- Linter & Formatter: `ruff`. Test Runner: `pytest`. Git Hooks: root `lefthook.yml`.

## 4. Architecture & Python Standards

- Layout: Project root (`backend/`) contains `manage.py`, project configuration in `config/`, domain apps in `apps/`.
- API Framework: Django Ninja Extra with class-based controllers (`@api_controller`).
- Schemas & Errors: Inherit API schemas from `apps.core.schemas.StrictBaseModel` (`extra="forbid"`, `use_enum_values=True`). Return all errors in RFC 7807 `ProblemDetail` format (`application/problem+json`).
- User Model & Auth: Custom `apps.users.models.User` with UUID primary key (`id` exposed as `user_id`) and lowercase `email` as `USERNAME_FIELD`. Authenticate routes with `AppJWTAuth` and rotate/blacklist refresh tokens.
- Configuration: Manage settings via Pydantic Settings in `config/settings/config.py`.
- Database: PostgreSQL 16 with `psycopg` (v3) is the standard for development, testing, and production (`USE_SQLITE=False`).
- Typing: Use modern Python 3.12+ type annotations (`list[str]`, `dict[str, Any]`, `X | None`).

## 5. Verification Checklist

Before completing any task, run `make check` (`ruff check`, `ruff format --check`, `pytest`) and ensure everything passes.
