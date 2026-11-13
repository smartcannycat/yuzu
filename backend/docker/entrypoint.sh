#!/usr/bin/env bash
set -e

if [ "$1" = "granian" ] || [ "$1" = "python" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
fi

exec "$@"
