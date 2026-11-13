# Backend Agent Guidelines

## 1. General Rules

- Language: English only for code, comments, technical documentation, and commit messages. User-facing API error descriptions (`ProblemDetail.title`, `ProblemDetail.detail`, `invalid_params[].reason`) and localized product strings follow `../docs/API_DATA_CONTRACTS.md` (Russian).
- No Emojis: Never use emojis in code, comments, or commit messages.

## 2. Package Manager

- Strictly use `uv`. Do not use pip, poetry, or pipenv.
- Never generate or commit foreign lockfiles (`poetry.lock`, `Pipfile.lock`, `requirements.txt`).

## 3. Tooling & Quality

- Linter & Formatter: `ruff` (`uv run ruff check`, `uv run ruff format`). Do not add flake8, black, or isort.
- Test Runner: `pytest` (`uv run pytest`).
- Git Hooks: Managed by `lefthook` via the repository root `lefthook.yml` (runs `ruff check` and `ruff format` inside `backend/`).
- Task Runner: `make` (use targets defined in `Makefile`).

## 4. Architecture & Python Standards

- Layout: Project root (`backend/`) contains `manage.py`, project configuration in `config/`, domain apps in `apps/`.
- API Framework: Use Django Ninja and Django Ninja Extra with class-based controllers (`@api_controller`).
- Schemas & Errors: Inherit API schemas from `apps.core.schemas.StrictBaseModel` (`extra="forbid"`). Return all errors in RFC 7807 `ProblemDetail` format via `apps.core.exceptions` and global exception handlers.
- User Model: Custom `apps.users.models.User` with UUID primary key (`id` exposed as `user_id`) and `email` as `USERNAME_FIELD`.
- Configuration: Manage settings via Pydantic Settings in `config/settings/config.py`.
- Imports: Use first-party imports from `config.*` and `apps.*`.
- Typing: Use modern Python 3.12+ type annotations (`list[str]`, `dict[str, Any]`, `X | None`).

## 5. Server & Infrastructure

- ASGI Server: Granian with `--interface asginl` pointing to `config.asgi:application`.
- Database: PostgreSQL 16 with `psycopg` (v3) is the standard for development, testing, and production (`USE_SQLITE=False`).
- Containers: Multi-stage Dockerfile with `dev` and `prod` targets. Compose configs separated into `docker-compose.dev.yml` and `docker-compose.prod.yml`.

## 6. Verification Checklist

Run and ensure passing status before completing any task:

1. `make lint`
2. `make format`
3. `make test`
