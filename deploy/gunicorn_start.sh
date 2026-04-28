#!/usr/bin/env bash
set -e

# Simple wrapper to start gunicorn with uvicorn workers
# Determine project root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_MODULE=${APP_MODULE:-"app.main:app"}
BIND_ADDR=${BIND_ADDR:-"127.0.0.1:8000"}
WORKERS=${WORKERS:-${WORKERS_ENV:-1}}
TIMEOUT=${TIMEOUT:-120}

# venv default to project .venv
VENV=${VENV:-"${PROJECT_ROOT}/.venv"}

if [[ -x "${VENV}/bin/gunicorn" ]]; then
  GUNICORN_EXEC="${VENV}/bin/gunicorn"
else
  GUNICORN_EXEC="gunicorn"
fi

exec "${GUNICORN_EXEC}" -k uvicorn.workers.UvicornWorker ${APP_MODULE} \
  --bind ${BIND_ADDR} --workers ${WORKERS} --timeout ${TIMEOUT} \
  --access-logfile - --error-logfile -
