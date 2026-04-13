#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

set -a && source .env.dev 2>/dev/null && set +a

BACKEND_PORT="${BACKEND_PORT:-${CONDUCTOR_PORT:-8000}}"
FRONTEND_PORT="${FRONTEND_PORT:-$((BACKEND_PORT + 1))}"

export BACKEND_PORT
export FRONTEND_PORT

if [ ! -f "backend/.env" ]; then
  echo "Warning: backend/.env is missing. The app will start, but live transcription will fail without API keys."
fi

echo "Starting backend on http://localhost:$BACKEND_PORT"
echo "Starting frontend on http://localhost:$FRONTEND_PORT"

cd frontend
pnpm exec concurrently \
  --kill-others \
  --names frontend,backend \
  --prefix-colors blue,green \
  "BACKEND_PORT=$BACKEND_PORT FRONTEND_PORT=$FRONTEND_PORT pnpm dev --port $FRONTEND_PORT" \
  "cd ../backend && BACKEND_PORT=$BACKEND_PORT FRONTEND_PORT=$FRONTEND_PORT uv run uvicorn app.main:app --reload --port $BACKEND_PORT --log-level info"
