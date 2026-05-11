from __future__ import annotations

from repo_bootstrap import bootstrap_backend_imports
from stt_mistral_cf import connect_mistral
from stt_soniox_cf import connect_soniox

bootstrap_backend_imports()

from app.stt import SttSession  # noqa: E402


async def create_stt_session(
    settings,
    *,
    recorder=None,
    connect_soniox_fn=connect_soniox,
    connect_mistral_fn=connect_mistral,
) -> SttSession:
    provider = getattr(settings, "stt_provider", "soniox")
    if provider == "mistral":
        api_key = getattr(settings, "mistral_api_key", None)
        if not api_key:
            raise ValueError("Mistral API key is required")
        raw_event_callback = None
        if recorder is not None:
            raw_event_callback = recorder.write_provider_message
        return await connect_mistral_fn(
            api_key,
            raw_event_callback=raw_event_callback,
        )

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
