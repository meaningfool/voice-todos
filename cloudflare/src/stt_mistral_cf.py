from __future__ import annotations

from typing import Any, cast

from repo_bootstrap import bootstrap_backend_imports

bootstrap_backend_imports()

from shared.stt_mistral_shared import MISTRAL_MODEL, MistralSession  # noqa: E402


async def connect_mistral(
    api_key: str,
    *,
    client_factory=None,
    model: str = MISTRAL_MODEL,
    target_streaming_delay_ms: int | None = None,
    raw_event_callback=None,
) -> MistralSession:
    if client_factory is None:
        from mistralai import Mistral, models

        client_factory = Mistral
        audio_format = models.AudioFormat(encoding="pcm_s16le", sample_rate=16000)
    else:
        audio_format = {"encoding": "pcm_s16le", "sample_rate": 16000}

    client = cast(Any, client_factory(api_key=api_key))
    connection = await client.audio.realtime.connect(
        model=model,
        audio_format=audio_format,
        target_streaming_delay_ms=target_streaming_delay_ms,
    )
    return MistralSession(connection, raw_event_callback=raw_event_callback)
