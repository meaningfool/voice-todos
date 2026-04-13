from __future__ import annotations

import json
import os
from pathlib import Path

from app.backend_env import BACKEND_ROOT, read_backend_env_var
from app.logfire_setup import (
    get_logfire_project_name,
    get_logfire_read_token,
    has_logfire_write_credentials,
)
from app.repo_env import repo_env_flag_enabled


def benchmark_report_skip_reason() -> str | None:
    if not get_logfire_read_token():
        return "requires LOGFIRE_READ_TOKEN via env or backend/.env"
    if not get_logfire_project_name():
        return (
            "requires LOGFIRE_PROJECT_NAME via env, backend/.env, or "
            "backend/.logfire/logfire_credentials.json"
        )
    return None


def benchmark_run_skip_reason() -> str | None:
    if not repo_env_flag_enabled("ITEM7_ENABLE_LIVE_SMOKE"):
        return "requires ITEM7_ENABLE_LIVE_SMOKE=1"

    report_reason = benchmark_report_skip_reason()
    if report_reason is not None:
        return report_reason

    if not has_logfire_write_credentials():
        return (
            "requires LOGFIRE_TOKEN via env/backend/.env or "
            "backend/.logfire/logfire_credentials.json"
        )

    if not any(
        read_backend_env_var(name)
        for name in ("GEMINI_API_KEY", "MISTRAL_API_KEY", "DEEPINFRA_API_KEY")
    ):
        return (
            "requires at least one benchmark provider credential "
            "in env or backend/.env"
        )

    return None


def hosted_dataset_crud_skip_reason() -> str | None:
    if not read_backend_env_var("LOGFIRE_DATASETS_TOKEN"):
        return "requires LOGFIRE_DATASETS_TOKEN via env or backend/.env"
    if not get_logfire_project_name():
        return (
            "requires LOGFIRE_PROJECT_NAME via env, backend/.env, or "
            "backend/.logfire/logfire_credentials.json"
        )
    return None


def hosted_dataset_locking_validation_warning() -> str | None:
    tracked_reason = benchmark_run_skip_reason()
    if tracked_reason == (
        "requires LOGFIRE_TOKEN via env/backend/.env or "
        "backend/.logfire/logfire_credentials.json"
    ):
        return tracked_reason
    if not _has_explicit_logfire_write_token():
        return (
            "requires LOGFIRE_TOKEN via env/backend/.env or "
            "backend/.logfire/logfire_credentials.json"
        )
    return tracked_reason or hosted_dataset_crud_skip_reason()


def stale_benchmark_detection_validation_warning() -> str | None:
    return hosted_dataset_crud_skip_reason()


def stale_benchmark_actions_validation_warning() -> str | None:
    return benchmark_run_skip_reason() or hosted_dataset_crud_skip_reason()


def _has_explicit_logfire_write_token() -> bool:
    if read_backend_env_var("LOGFIRE_TOKEN"):
        return True
    credentials_dir = os.getenv("LOGFIRE_CREDENTIALS_DIR")
    base_dir = Path(credentials_dir) if credentials_dir else BACKEND_ROOT / ".logfire"
    credentials_path = base_dir / "logfire_credentials.json"
    if not credentials_path.exists():
        return False
    try:
        payload = json.loads(credentials_path.read_text())
    except json.JSONDecodeError:
        return False
    token = payload.get("token")
    return isinstance(token, str) and bool(token)
