from __future__ import annotations

import os
from pathlib import Path

import logfire

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV_PATH = BACKEND_ROOT / ".env"


def _read_backend_env_var(name: str) -> str | None:
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


def _logfire_data_dir() -> Path:
    override = os.getenv("LOGFIRE_CREDENTIALS_DIR")
    if override:
        return Path(override)
    return BACKEND_ROOT / ".logfire"


def has_logfire_write_credentials() -> bool:
    if _read_backend_env_var("LOGFIRE_TOKEN"):
        return True
    return (_logfire_data_dir() / "logfire_credentials.json").exists()


def get_logfire_read_token() -> str | None:
    return _read_backend_env_var("LOGFIRE_READ_TOKEN")


def get_logfire_project_name() -> str | None:
    return _read_backend_env_var("LOGFIRE_PROJECT")


def configure_logfire(
    *,
    service_name: str = "voice-todos-backend",
    instrument_pydantic_ai: bool = False,
) -> None:
    logfire_token = _read_backend_env_var("LOGFIRE_TOKEN")
    logfire.configure(
        service_name=service_name,
        send_to_logfire="if-token-present",
        data_dir=_logfire_data_dir(),
        token=logfire_token,
    )
    if instrument_pydantic_ai:
        logfire.instrument_pydantic_ai()
