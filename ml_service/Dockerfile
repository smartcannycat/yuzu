# ==========================================
# Stage 1: Base image with Python, uv & user
# ==========================================
FROM python:3.12-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

WORKDIR /app/ml_service

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/ml_service/.venv/bin:$PATH"

RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser \
    && mkdir -p /app/ml_service/.cache/sheets \
    && chown -R appuser:appuser /app/ml_service

# ==========================================
# Stage 2: Development target (with dev deps & reload)
# ==========================================
FROM base AS dev

ARG INSTALL_TESSERACT=true
RUN if [ "$INSTALL_TESSERACT" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*; \
fi

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY --chown=appuser:appuser . .
RUN uv sync --frozen \
    && mkdir -p /app/ml_service/.cache/sheets \
    && chown -R appuser:appuser /app/ml_service

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; from ml_service.config import get_settings; keys = get_settings().service_api_keys; req = urllib.request.Request('http://127.0.0.1:8001/health', headers={'X-API-Key': keys[0]} if keys else {}); urllib.request.urlopen(req, timeout=4)" || exit 1

CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]

# ==========================================
# Stage 3: Production builder (without dev deps)
# ==========================================
FROM base AS prod-builder

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md .env.example __init__.py config.py main.py ./
COPY api ./api
COPY domains ./domains
COPY factories ./factories
COPY infrastructure ./infrastructure
COPY services ./services
RUN uv sync --frozen --no-dev --no-editable

# ==========================================
# Stage 4: Production target (minimal runtime, no uv binary)
# ==========================================
FROM python:3.12-slim-bookworm AS prod

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/ml_service

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/ml_service/.venv/bin:$PATH"

RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser \
    && mkdir -p /app/ml_service/.cache/sheets \
    && chown -R appuser:appuser /app/ml_service

COPY --from=prod-builder --chown=appuser:appuser /app/ml_service/.venv /app/ml_service/.venv
COPY --chown=appuser:appuser config.toml .env.example ./

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; from ml_service.config import get_settings; keys = get_settings().service_api_keys; req = urllib.request.Request('http://127.0.0.1:8001/health', headers={'X-API-Key': keys[0]} if keys else {}); urllib.request.urlopen(req, timeout=4)" || exit 1

CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
