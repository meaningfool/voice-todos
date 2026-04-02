#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

ROOT_PATH="${CONDUCTOR_ROOT_PATH:-}"

link_shared_path() {
  local source_path="$1"
  local target_path="$2"

  if [ ! -e "$source_path" ]; then
    return 0
  fi

  if [ -e "$target_path" ] && [ ! -L "$target_path" ]; then
    echo "Skipping $target_path because it already exists and is not a symlink."
    return 0
  fi

  ln -sfn "$source_path" "$target_path"
  echo "Linked $target_path -> $source_path"
}

if [ -n "$ROOT_PATH" ]; then
  link_shared_path "$ROOT_PATH/backend/.env" "backend/.env"
  link_shared_path "$ROOT_PATH/backend/.logfire" "backend/.logfire"

  if [ ! -e "$ROOT_PATH/backend/.env" ]; then
    echo "Warning: shared backend/.env not found at $ROOT_PATH/backend/.env"
    echo "Create it from backend/.env.example and add SONIOX_API_KEY / GEMINI_API_KEY."
  fi
else
  echo "CONDUCTOR_ROOT_PATH is not set; skipping shared file linking."
fi

echo "Syncing backend dependencies with uv..."
(cd backend && uv sync --locked)

echo "Installing frontend dependencies with pnpm..."
(cd frontend && pnpm install --frozen-lockfile)

echo "Conductor setup complete."
