from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import websockets

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttSession, SttToken

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
SONIOX_CAPABILITIES = SttCapabilities(
    exposes_finalization_boundary=True,
    exposes_endpoint_boundary=True,
)


def build_soniox_config(api_key: str) -> dict[str, Any]:
    return {
        "api_key": api_key,
        "model": "stt-rt-v4",
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "num_channels": 1,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": 1000,
        "context": {
            "general": [
                {
                    "key": "topic",
                    "value": (
                        "The user is dictating tasks and todos "
                        "into a voice-driven todo list application."
                    ),
                },
            ],
        },
    }


def translate_soniox_event(raw_event: Mapping[str, Any]) -> SttEvent:
    if raw_event.get("finished"):
        return SttEvent(is_finished=True)

    raw_tokens = [
        token
        for token in raw_event.get("tokens", [])
        if isinstance(token, Mapping) and isinstance(token.get("text"), str)
    ]
    finalization_state = (
        BoundaryState.OBSERVED
        if any(token["text"] == "<fin>" for token in raw_tokens)
        else BoundaryState.NOT_OBSERVED
    )
    endpoint_state = (
        BoundaryState.OBSERVED
        if any(token["text"] == "<end>" for token in raw_tokens)
        else BoundaryState.NOT_OBSERVED
    )
    tokens = [
        SttToken(text=token["text"], is_final=bool(token.get("is_final", False)))
        for token in raw_tokens
        if token["text"] not in {"<fin>", "<end>"}
    ]
    return SttEvent(
        tokens=tokens,
        finalization_state=finalization_state,
        endpoint_state=endpoint_state,
        is_finished=False,
    )


class SonioxSession(SttSession):
    def __init__(
        self,
        ws: websockets.ClientConnection,
        *,
        raw_message_callback=None,
    ) -> None:
        self._ws = ws
        self._final_transcript_event = asyncio.Event()
        self._raw_message_callback = raw_message_callback

    @property
    def capabilities(self) -> SttCapabilities:
        return SONIOX_CAPABILITIES

    @property
    def final_transcript_text(self) -> str | None:
        return None

    async def send_audio(self, chunk: bytes) -> None:
        await self._ws.send(chunk)

    async def request_final_transcript(self) -> None:
        await self._ws.send(json.dumps({"type": "finalize"}))

    async def end_stream(self) -> None:
        await self._ws.send(b"")

    async def wait_for_final_transcript(self) -> None:
        await self._final_transcript_event.wait()

    async def close(self) -> None:
        await self._ws.close()

    async def _iter_events(self) -> AsyncIterator[SttEvent]:
        async for message in self._ws:
            if self._raw_message_callback is not None:
                payload = message if isinstance(message, str) else message.decode()
                self._raw_message_callback(payload)
            event = translate_soniox_event(json.loads(message))
            if event.finalization_state is BoundaryState.OBSERVED:
                self._final_transcript_event.set()
            yield event

    def __aiter__(self) -> AsyncIterator[SttEvent]:
        return self._iter_events()


async def connect_soniox(
    api_key: str,
    *,
    raw_message_callback=None,
    connect_fn=websockets.connect,
) -> SonioxSession:
    ws = await connect_fn(SONIOX_WS_URL)
    await ws.send(json.dumps(build_soniox_config(api_key)))
    return SonioxSession(ws, raw_message_callback=raw_message_callback)
