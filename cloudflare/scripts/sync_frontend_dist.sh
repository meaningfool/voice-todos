#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
src="$repo_root/frontend/dist"
dest="$repo_root/cloudflare/public"

if [ ! -f "$src/index.html" ]; then
  echo "frontend build output missing: $src/index.html" >&2
  exit 1
fi

mkdir -p "$dest"
rsync -a --delete "$src"/ "$dest"/
