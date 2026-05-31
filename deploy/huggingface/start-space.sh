#!/usr/bin/env sh
set -eu

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${PORT:-7860}"

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:${BACKEND_PORT}}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"
export PORT="${FRONTEND_PORT}"

python -m src.main -m http -p "${BACKEND_PORT}" &
backend_pid="$!"

cleanup() {
  kill "${backend_pid}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

cd /app/frontend
node server.js
