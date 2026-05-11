from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import websockets

from app.repo_bootstrap import bootstrap_repo_imports

bootstrap_repo_imports()

from shared.stt_soniox_shared import (  # noqa: E402
    SONIOX_CAPABILITIES,
    build_soniox_config,
    translate_soniox_event,
)

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttSession  # noqa: E402

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
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
