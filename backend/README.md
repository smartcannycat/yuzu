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

## Currency Rates Gateway (BE-05)

Daily CBRF rates come from [cbr-xml-daily.ru](https://www.cbr-xml-daily.ru/) — Курсы валют, API.
Per its terms of use the backlink above must stay in the public documentation of services
consuming the data. The commercial JPY rate is an internal estimate
(`CBRF rate + 3% spread`, label "Расчётный ориентир: ЦБ РФ + 3%"), not a published bank quote.

Resolution order: fresh cache (1 hour TTL) -> live fetch (single updater under a PostgreSQL
advisory lock) -> last valid DB set (up to 7 days) -> configured fallback
(`CBRF_FALLBACK_RATES`, required in production).

Management command to warm the cache manually:

```bash
make refresh-currency-rates
```

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
