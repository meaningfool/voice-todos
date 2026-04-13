from __future__ import annotations

import os

from app.backend_env import BACKEND_ROOT

REPO_ROOT = BACKEND_ROOT.parent
REPO_ENV_DEV_PATH = REPO_ROOT / ".env.dev"
_FALSEY_VALUES = {"0", "false", "no", "off", ""}


def read_repo_env_dev_var(name: str) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value

    if not REPO_ENV_DEV_PATH.exists():
        return None

    for line in REPO_ENV_DEV_PATH.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        if "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return raw_value.strip().strip('"').strip("'")

    return None


def repo_env_flag_enabled(name: str) -> bool:
    value = read_repo_env_dev_var(name)
    if value is None:
        return False
    return value.strip().lower() not in _FALSEY_VALUES
