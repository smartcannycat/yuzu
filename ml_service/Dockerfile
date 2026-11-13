FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/ml_service

# Copy package metadata & README before pip install (pyproject.toml references readme = "README.md")
COPY pyproject.toml README.md .env.example ./
COPY __init__.py config.py main.py ./
COPY api ./api
COPY domains ./domains
COPY factories ./factories
COPY infrastructure ./infrastructure
COPY services ./services

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e . \
    && groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser \
    && mkdir -p /app/ml_service/.cache/sheets \
    && chown -R appuser:appuser /app/ml_service

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; from ml_service.config import get_settings; keys = get_settings().service_api_keys; req = urllib.request.Request('http://127.0.0.1:8001/health', headers={'X-API-Key': keys[0]} if keys else {}); urllib.request.urlopen(req, timeout=4)" || exit 1

CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
