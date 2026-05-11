from __future__ import annotations

from mistralai import Mistral, models

from app.repo_bootstrap import bootstrap_repo_imports

bootstrap_repo_imports()

from shared.stt_mistral_shared import (  # noqa: E402
    MISTRAL_MODEL,
    MistralSession,
)


async def connect_mistral(
    api_key: str,
    *,
    client_factory=Mistral,
    model: str = MISTRAL_MODEL,
    target_streaming_delay_ms: int | None = None,
    raw_event_callback=None,
) -> MistralSession:
    client = client_factory(api_key=api_key)
    connection = await client.audio.realtime.connect(
        model=model,
        audio_format=models.AudioFormat(encoding="pcm_s16le", sample_rate=16000),
        target_streaming_delay_ms=target_streaming_delay_ms,
    )
    return MistralSession(connection, raw_event_callback=raw_event_callback)
