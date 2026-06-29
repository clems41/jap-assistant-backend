#!/bin/bash
set -e

echo "Collecting static files..."
uv run --no-sync python manage.py collectstatic --noinput

echo "Applying migrations..."
uv run --no-sync python manage.py migrate --noinput

exec uv run --no-sync gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --threads 4 \
    --timeout 60
