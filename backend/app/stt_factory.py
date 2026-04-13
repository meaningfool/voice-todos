from __future__ import annotations

from collections.abc import Callable

from app.stt import SttSession
from app.stt_soniox import connect_soniox


async def create_stt_session(
    settings,
    *,
    recorder=None,
    connect_soniox_fn: Callable[..., object] = connect_soniox,
) -> SttSession:
    provider = getattr(settings, "stt_provider", "soniox")
    if provider != "soniox":
        raise ValueError(f"Unsupported STT provider: {provider}")

    raw_message_callback = None
    if recorder is not None:
        raw_message_callback = recorder.write_soniox_message

    return await connect_soniox_fn(
        settings.soniox_api_key,
        raw_message_callback=raw_message_callback,
    )
