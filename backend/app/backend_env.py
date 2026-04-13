from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV_PATH = BACKEND_ROOT / ".env"


def read_backend_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if not BACKEND_ENV_PATH.exists():
        return None

    for line in BACKEND_ENV_PATH.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return raw_value.strip().strip('"').strip("'")

    return None
