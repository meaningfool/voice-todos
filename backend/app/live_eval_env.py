from __future__ import annotations

from app.backend_env import read_backend_env_var
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
