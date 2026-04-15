from __future__ import annotations

from collections.abc import Callable

from app.stt import SttSession
from app.stt_mistral import connect_mistral
from app.stt_soniox import connect_soniox


async def create_stt_session(
    settings,
    *,
    recorder=None,
    connect_soniox_fn: Callable[..., object] = connect_soniox,
    connect_mistral_fn: Callable[..., object] | None = None,
) -> SttSession:
    provider = getattr(settings, "stt_provider", "soniox")
    if provider == "mistral":
        api_key = getattr(settings, "mistral_api_key", None)
        if not api_key:
            raise ValueError("Mistral API key is required")
        if connect_mistral_fn is None:
            connect_mistral_fn = connect_mistral
        raw_event_callback = None
        if recorder is not None:
            raw_event_callback = recorder.write_provider_message
        return await connect_mistral_fn(
            api_key,
            raw_event_callback=raw_event_callback,
        )

    if provider != "soniox":
        raise ValueError(f"Unsupported STT provider: {provider}")

    raw_message_callback = None
    if recorder is not None:
        raw_message_callback = recorder.write_provider_message

    return await connect_soniox_fn(
        settings.soniox_api_key,
        raw_message_callback=raw_message_callback,
    )
