from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudflareSettings:
    session_cap_ms: int = 60_000
    stt_provider: str = "soniox"
    soniox_api_key: str | None = None
    gemini_api_key: str | None = None
    mistral_api_key: str | None = None
    deepinfra_api_key: str | None = None
    google_cloud_project_id: str | None = None
    stop_timeout_seconds: float = 30.0


def _get_runtime_value(env, name: str) -> str | None:
    if env is not None and hasattr(env, name):
        value = getattr(env, name)
        if value is not None:
            return str(value)
    return os.getenv(name)


def _mirror_runtime_env_to_process(env) -> None:
    for name in (
        "SONIOX_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPINFRA_API_KEY",
        "GOOGLE_CLOUD_PROJECT_ID",
    ):
        value = _get_runtime_value(env, name)
        if value is not None:
            os.environ[name] = value


def get_settings(env=None) -> CloudflareSettings:
    _mirror_runtime_env_to_process(env)
    return CloudflareSettings(
        session_cap_ms=int(_get_runtime_value(env, "SESSION_CAP_MS") or "60000"),
        stt_provider=_get_runtime_value(env, "STT_PROVIDER") or "soniox",
        soniox_api_key=_get_runtime_value(env, "SONIOX_API_KEY"),
        gemini_api_key=_get_runtime_value(env, "GEMINI_API_KEY"),
        mistral_api_key=_get_runtime_value(env, "MISTRAL_API_KEY"),
        deepinfra_api_key=_get_runtime_value(env, "DEEPINFRA_API_KEY"),
        google_cloud_project_id=_get_runtime_value(env, "GOOGLE_CLOUD_PROJECT_ID"),
        stop_timeout_seconds=float(
            _get_runtime_value(env, "STOP_TIMEOUT_SECONDS") or "30.0"
        ),
    )
