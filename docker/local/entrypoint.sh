#!/bin/bash
set -e

echo "Waiting for postgres..."
while ! uv run python -c "
import psycopg, os, sys
try:
    psycopg.connect(os.environ['DATABASE_URL'])
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Applying migrations..."
uv run python manage.py migrate --noinput

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput

exec "$@"
