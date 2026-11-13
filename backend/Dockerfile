# ==========================================
# Stage 1: Base image with Python, uv & user
# ==========================================
FROM python:3.12-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r -g 1000 appgroup && \
    useradd -r -u 1000 -g appgroup -d /app -s /bin/bash appuser

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ==========================================
# Stage 2: Development target (with dev deps & reload)
# ==========================================
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["granian", "--interface", "asginl", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==========================================
# Stage 3: Production builder (without dev deps)
# ==========================================
FROM base AS prod-builder

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ==========================================
# Stage 4: Production target (minimal runtime)
# ==========================================
FROM base AS prod

COPY --from=prod-builder --chown=appuser:appgroup /app/.venv /app/.venv

COPY --chown=appuser:appgroup config ./config
COPY --chown=appuser:appgroup apps ./apps
COPY --chown=appuser:appgroup manage.py ./manage.py

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["granian", "--interface", "asginl", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
