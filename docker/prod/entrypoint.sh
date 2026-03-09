#!/bin/bash
set -e

echo "Applying migrations..."
uv run python manage.py migrate --noinput

exec "$@"
