from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncIterator
from typing import Any

from repo_bootstrap import bootstrap_backend_imports

bootstrap_backend_imports()

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttSession  # noqa: E402
from shared.stt_soniox_shared import (  # noqa: E402
    SONIOX_CAPABILITIES,
    build_soniox_config,
    translate_soniox_event,
)

Uint8Array: Any | None

try:
    from js import Uint8Array as js_uint8_array
except ImportError:  # pragma: no cover - unavailable in local pytest
    Uint8Array = None
else:
    Uint8Array = js_uint8_array

try:
    from pyodide.ffi import create_proxy
except ImportError:  # pragma: no cover - unavailable in local pytest
    def create_proxy(handler):
        return handler

fetch: Any | None

try:
    from workers import fetch as workers_fetch
except ModuleNotFoundError:  # pragma: no cover - unavailable in local pytest
    fetch = None
else:
    fetch = workers_fetch


SONIOX_FETCH_URL = "https://stt-rt.soniox.com/transcribe-websocket"
def _to_outbound_binary(chunk: bytes) -> Any:
    if Uint8Array is None:
        return chunk
    return Uint8Array.new(list(chunk))


class OutboundWebSocketClient:
    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.opened = asyncio.Event()
        self.closed = asyncio.Event()
        self.messages: asyncio.Queue[str] = asyncio.Queue()
        self.error_message: str | None = None
        self.close_info: dict[str, object] | None = None
        self._proxies: list[Any] = []

        def on_open(event: Any) -> None:
            del event
            self.opened.set()

        def on_message(event: Any) -> None:
            self.messages.put_nowait(str(event.data))

        def on_error(event: Any) -> None:
            self.error_message = f"websocket error: {event}"

        def on_close(event: Any) -> None:
            self.close_info = {
                "code": getattr(event, "code", None),
                "reason": getattr(event, "reason", None),
                "was_clean": getattr(event, "wasClean", None),
            }
            self.closed.set()

        if hasattr(self.ws, "addEventListener"):
            for event_name, handler in (
                ("open", on_open),
                ("message", on_message),
                ("error", on_error),
                ("close", on_close),
            ):
                proxy = create_proxy(handler)
                self._proxies.append(proxy)
                self.ws.addEventListener(event_name, proxy)

    @classmethod
    async def connect(cls, url: str):
        if fetch is None:
            raise RuntimeError("Cloudflare fetch runtime is unavailable")

        response = await fetch(url, headers={"Upgrade": "websocket"})
        ws = response.js_object.webSocket
        if not ws:
            raise RuntimeError("server did not accept the outbound websocket")
        ws.accept()
        client = cls(ws)
        client.opened.set()
        return client

    async def wait_until_open(self, timeout_seconds: float = 10.0) -> None:
        await asyncio.wait_for(self.opened.wait(), timeout=timeout_seconds)

    def send_text(self, payload: str) -> None:
        self.ws.send(payload)

    def send_binary(self, payload: bytes) -> None:
        self.ws.send(_to_outbound_binary(payload))

    async def close(self) -> None:
        maybe_awaitable = self.ws.close()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def _iterate_messages(self) -> AsyncIterator[str]:
        while True:
            yield await self.messages.get()

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iterate_messages()


class CloudflareSonioxSession(SttSession):
    def __init__(
        self,
        client: Any,
        *,
        raw_message_callback=None,
    ) -> None:
        self._client = client
        self._final_transcript_event = asyncio.Event()
        self._raw_message_callback = raw_message_callback

    @property
    def capabilities(self) -> SttCapabilities:
        return SONIOX_CAPABILITIES

    @property
    def final_transcript_text(self) -> str | None:
        return None

    async def send_audio(self, chunk: bytes) -> None:
        self._client.send_binary(chunk)

    async def request_final_transcript(self) -> None:
        self._client.send_text(json.dumps({"type": "finalize"}))

    async def end_stream(self) -> None:
        self._client.send_binary(b"")

    async def wait_for_final_transcript(self) -> None:
        await self._final_transcript_event.wait()

    async def close(self) -> None:
        await self._client.close()

    async def _iter_events(self) -> AsyncIterator[SttEvent]:
        async for message in self._client:
            payload = message if isinstance(message, str) else message.decode()
            if self._raw_message_callback is not None:
                self._raw_message_callback(payload)
            event = translate_soniox_event(json.loads(payload))
            if event.finalization_state is BoundaryState.OBSERVED:
                self._final_transcript_event.set()
            yield event

    def __aiter__(self) -> AsyncIterator[SttEvent]:
        return self._iter_events()


async def connect_soniox(
    api_key: str,
    *,
    raw_message_callback=None,
    client_cls=OutboundWebSocketClient,
) -> CloudflareSonioxSession:
    client = await client_cls.connect(SONIOX_FETCH_URL)
    await client.wait_until_open()
    client.send_text(json.dumps(build_soniox_config(api_key)))
    return CloudflareSonioxSession(
        client,
        raw_message_callback=raw_message_callback,
    )
