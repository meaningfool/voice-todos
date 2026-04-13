from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

from mistralai import Mistral, models

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttSession, SttToken

MISTRAL_MODEL = "voxtral-mini-transcribe-realtime-2602"
MISTRAL_CAPABILITIES = SttCapabilities(
    exposes_finalization_boundary=False,
    exposes_endpoint_boundary=False,
)


def _serialize_realtime_event(event: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)

    model_dump = getattr(event, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", by_alias=True, exclude_none=True)

    payload = dict(getattr(event, "__dict__", {}))
    event_type = getattr(event, "type", None)
    if isinstance(event_type, str):
        payload.setdefault("type", event_type)
    return payload


def translate_mistral_event(raw_event: Mapping[str, Any] | Any) -> SttEvent:
    payload = _serialize_realtime_event(raw_event)
    event_type = payload.get("type")
    if event_type == "transcription.text.delta":
        text = payload.get("text")
        tokens = []
        if isinstance(text, str) and text:
            tokens.append(SttToken(text=text, is_final=True))
        return SttEvent(
            tokens=tokens,
            finalization_state=BoundaryState.NOT_OBSERVED,
            endpoint_state=BoundaryState.UNSUPPORTED,
        )

    if event_type == "transcription.done":
        return SttEvent(
            finalization_state=BoundaryState.NOT_OBSERVED,
            endpoint_state=BoundaryState.UNSUPPORTED,
            is_finished=True,
        )

    return SttEvent(
        finalization_state=BoundaryState.NOT_OBSERVED,
        endpoint_state=BoundaryState.UNSUPPORTED,
    )


class MistralSession(SttSession):
    def __init__(self, connection) -> None:
        self._connection = connection
        self._final_transcript_event = asyncio.Event()
        self._final_transcript_text: str | None = None

    @property
    def capabilities(self) -> SttCapabilities:
        return MISTRAL_CAPABILITIES

    @property
    def final_transcript_text(self) -> str | None:
        return self._final_transcript_text

    async def send_audio(self, chunk: bytes) -> None:
        await self._connection.send_audio(chunk)

    async def request_final_transcript(self) -> None:
        await self._connection.flush_audio()

    async def end_stream(self) -> None:
        await self._connection.end_audio()

    async def wait_for_final_transcript(self) -> None:
        await self._final_transcript_event.wait()

    async def close(self) -> None:
        await self._connection.close()

    async def _iter_events(self) -> AsyncIterator[SttEvent]:
        async for raw_event in self._connection.events():
            payload = _serialize_realtime_event(raw_event)
            if payload.get("type") == "transcription.done":
                text = payload.get("text")
                self._final_transcript_text = text if isinstance(text, str) else None
                self._final_transcript_event.set()
            yield translate_mistral_event(payload)

    def __aiter__(self) -> AsyncIterator[SttEvent]:
        return self._iter_events()


async def connect_mistral(
    api_key: str,
    *,
    client_factory=Mistral,
    model: str = MISTRAL_MODEL,
    target_streaming_delay_ms: int | None = None,
) -> MistralSession:
    client = client_factory(api_key=api_key)
    connection = await client.audio.realtime.connect(
        model=model,
        audio_format=models.AudioFormat(encoding="pcm_s16le", sample_rate=16000),
        target_streaming_delay_ms=target_streaming_delay_ms,
    )
    return MistralSession(connection)
