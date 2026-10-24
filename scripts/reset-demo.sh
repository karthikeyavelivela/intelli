#!/usr/bin/env bash
# One-command demo reset. DESTRUCTIVE: wipes ALL data in the database and dataset volume, then re-seeds the
# synthetic Indian demo data (Bharat Retail Pvt Ltd + Sagar Foods & Beverages Ltd).
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v docker >/dev/null 2>&1 && docker compose ps --status running backend 2>/dev/null | grep -q backend; then
  docker compose exec -T backend python -m app.seed --reset
else
  cd backend
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=python; fi
  "$PY" -m app.seed --reset
fi
