#!/bin/bash
set -e

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput

echo "Applying migrations..."
uv run python manage.py migrate --noinput

exec uv run gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --threads 4 \
    --timeout 60
