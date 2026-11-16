# Yuzu

Japanese auction sheet inspection, cross-auction anomaly auditing, EAEU customs/recycling fee calculation, Vladivostok repair estimation, and investment verdict dashboard.

## Repository Layout

- `backend/` — Django 6 + Django Ninja Extra REST API, Celery worker/beat, PostgreSQL 16 + Redis 7 (`backend/README.md`)
- `ml_service/` — FastAPI OCR & normalization microservice for Japanese auction sheets (`ml_service/README.md`)
- `frontend/` — Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS v4 web app (`frontend/README.md`)
- `docs/` — Single documentation hub: architecture, live OpenAPI contract, product specs, and historical archive (`docs/README.md`)

## Quick Start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build -d
```

- Web UI: `http://127.0.0.1:5173`
- Backend API / OpenAPI docs: `http://127.0.0.1:8000/api/v1/docs`
- ML service docs: `http://127.0.0.1:8001/docs`

## Documentation & Agent Guidelines

- [Documentation Hub](docs/README.md)
- [Architecture Overview](docs/architecture/SYSTEM_OVERVIEW.md)
- [Backend Layering](docs/architecture/BACKEND_LAYERS.md)
- [API Contracts & Invariants](docs/architecture/CONTRACTS.md)
- Root and service agent instructions: `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`
