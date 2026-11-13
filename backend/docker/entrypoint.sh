#!/usr/bin/env bash
set -e

if [ "$1" = "granian" ] || [ "$1" = "/app/.venv/bin/granian" ] || [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
fi

exec "$@"
