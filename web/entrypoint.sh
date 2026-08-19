#!/bin/sh
# Cloud Run entrypoint: migrate → ensure the initial superuser → gunicorn.
# DJANGO_SUPERUSER_PASSWORD comes from Secret Manager; createsuperuser is
# idempotent here (skipped if the user exists).
set -e
cd /app/web

python manage.py migrate --noinput

if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --noinput \
    --username "${DJANGO_SUPERUSER_USERNAME:-jaime}" \
    --email "${DJANGO_SUPERUSER_EMAIL:-js@qhhe.net}" 2>/dev/null \
    || echo "superusuario ya existe — sin cambios"
fi

exec gunicorn core.wsgi:application \
  --bind ":${PORT:-8080}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads 8 \
  --timeout 0
