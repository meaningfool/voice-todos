from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudflareSettings:
    session_cap_ms: int = 60_000
    stt_provider: str = "soniox"


def get_settings() -> CloudflareSettings:
    return CloudflareSettings(
        session_cap_ms=int(os.getenv("SESSION_CAP_MS", "60000")),
        stt_provider=os.getenv("STT_PROVIDER", "soniox"),
    )
