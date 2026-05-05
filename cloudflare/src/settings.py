from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudflareSettings:
    session_cap_ms: int = 60_000
    stt_provider: str = "soniox"
    soniox_api_key: str | None = None
    stop_timeout_seconds: float = 10.0


def _get_runtime_value(env, name: str) -> str | None:
    if env is not None and hasattr(env, name):
        value = getattr(env, name)
        if value is not None:
            return str(value)
    return os.getenv(name)


def get_settings(env=None) -> CloudflareSettings:
    return CloudflareSettings(
        session_cap_ms=int(_get_runtime_value(env, "SESSION_CAP_MS") or "60000"),
        stt_provider=_get_runtime_value(env, "STT_PROVIDER") or "soniox",
        soniox_api_key=_get_runtime_value(env, "SONIOX_API_KEY"),
        stop_timeout_seconds=float(
            _get_runtime_value(env, "STOP_TIMEOUT_SECONDS") or "10.0"
        ),
    )
