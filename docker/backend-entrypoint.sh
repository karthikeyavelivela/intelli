#!/usr/bin/env bash
set -euo pipefail
role="${1:-api}"

if [ "$role" = "api" ]; then
  echo "[entrypoint] running database migrations"
  for i in $(seq 1 30); do
    if alembic upgrade head; then break; fi
    echo "[entrypoint] database not ready (attempt $i), retrying in 2s"; sleep 2
  done
  if [ "${AUTO_SEED:-false}" = "true" ]; then
    echo "[entrypoint] seeding demo data if database is empty"
    python -m app.seed
  fi
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" --proxy-headers --forwarded-allow-ips="*"
elif [ "$role" = "worker" ]; then
  exec celery -A app.worker.celery_app worker --loglevel=INFO --concurrency="${CELERY_CONCURRENCY:-2}"
else
  exec "$@"
fi
