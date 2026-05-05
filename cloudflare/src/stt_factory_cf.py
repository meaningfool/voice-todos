from __future__ import annotations

from repo_bootstrap import bootstrap_backend_imports
from stt_soniox_cf import connect_soniox

bootstrap_backend_imports()

from app.stt import SttSession


async def create_stt_session(
    settings,
    *,
    recorder=None,
    connect_soniox_fn=connect_soniox,
) -> SttSession:
    provider = getattr(settings, "stt_provider", "soniox")
    if provider != "soniox":
        raise ValueError(f"Unsupported hosted STT provider: {provider}")

    api_key = getattr(settings, "soniox_api_key", None)
    if not api_key:
        raise ValueError("Soniox API key is required")

    raw_message_callback = None
    if recorder is not None:
        raw_message_callback = recorder.write_provider_message

    return await connect_soniox_fn(
        api_key,
        raw_message_callback=raw_message_callback,
    )
