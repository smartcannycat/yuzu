#!/usr/bin/env bash
set -e

if [ "${RUN_MIGRATIONS:-auto}" = "true" ] || {
    [ "${RUN_MIGRATIONS:-auto}" = "auto" ] &&
        { [ "$1" = "granian" ] || [ "$1" = "/app/.venv/bin/granian" ]; }
}; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
fi

exec "$@"
