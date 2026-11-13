# Yuzu Backend API

REST API backend for Yuzu (AuctionCalc) built with Django 6, Django Ninja Extra, Django Ninja JWT, Granian, uv, and Ruff.

## Quick Start (Local with PostgreSQL in Docker)

```bash
cp .env.example .env
make install
make up-db
make migrate
make dev
```

API docs will be available at `http://127.0.0.1:8000/api/v1/docs`.

## Full Docker Compose

Development:

```bash
cp .env.example .env
make up
```

Production:

```bash
make prod-up
```

## Implemented Endpoints

- `GET /api/v1/health` - Service health check
- `POST /api/v1/auth/register` - Register user by email and password, return JWT tokens
- `POST /api/v1/auth/login` - Authenticate user by email and password, return JWT tokens
- `POST /api/v1/auth/refresh` - Rotate/refresh JWT tokens
- `GET /api/v1/auth/me` - Get current authenticated user profile

## Farpost Repair Estimates (BE-07)

The background `farpost_parts` step searches Farpost for replaceable panels marked
`X` or `XX`. Search requires a matching vehicle body code, panel, side and local
stock filter. It prefers the factory paint code, then searches other colors and
adds painting costs. Fixed panels use restoration estimates; glass does not incur
painting costs. The step saves the existing repair API contract without exposing
listing URLs or updating completed lots.

`FARPOST_TIMEOUT_SEC` defaults to 5 seconds per request. `FARPOST_BUDGET_SEC`
defaults to 20 seconds for source requests per lot. Successful searches are cached
in PostgreSQL for one hour; valid empty searches for ten minutes. Source failures
use successful results up to one day old, then the statistical matrix. Stale
results do not confirm current stock or a color match.

The versioned matrix in `apps/lots/integrations/farpost/data/repair_matrix.json`
contains planning estimates from the project research, not current STO quotes.
A part without a documented price uses the generic RUB 29,000 reserve. Work prices
include material costs where applicable. Duplicate defects do not duplicate work.

Farpost may return an anti-bot challenge with HTTP 200. The client treats it as an
error and does not bypass it. A live listing excerpt is stored under
`tests/fixtures/farpost`; its stock filter was not selected in the original page.
The parser tests select that filter explicitly to exercise the captured markup.
An end-to-end live quote still requires a response that confirms local stock.

## Commands

- `make dev` - Start Granian ASGI dev server with reload
- `make up-db` - Start PostgreSQL container for local dev and tests
- `make migrate` - Apply database migrations
- `make makemigrations` - Generate database migrations
- `make createsuperuser` - Create Django superuser
- `make test` - Run pytest against PostgreSQL
- `make lint` - Run ruff check
- `make format` - Format code and fix ruff issues
- `make check` - Run ruff check, format check, and pytest
- `make hooks` - Install Lefthook git hooks at repository root
- `make up` / `make down` - Manage dev Docker Compose
- `make prod-up` / `make prod-down` - Manage prod Docker Compose
- `make logs` - View dev API container logs
- `make clean` - Remove pycache and pytest cache
