from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from repo_bootstrap import bootstrap_backend_imports
from settings import get_settings

bootstrap_backend_imports()

from app.live_session import LiveSessionController
from stt_factory_cf import create_stt_session

try:
    from js import WebSocketPair
except ImportError:  # pragma: no cover - unavailable in local pytest
    WebSocketPair = None

try:
    from workers import DurableObject, Response
except ModuleNotFoundError:  # pragma: no cover - local pytest import fallback
    class DurableObject:
        def __init__(self, ctx: Any, env: Any) -> None:
            self.ctx = ctx
            self.env = env

    class Response:
        def __init__(
            self,
            body: Any = None,
            *,
            status: int = 200,
            web_socket: Any = None,
        ) -> None:
            self.body = body
            self.status = status
            self.web_socket = web_socket


class BrowserSocketAdapter:
    def __init__(self, ws: Any) -> None:
        self._ws = ws

    async def send_json(self, payload: dict[str, Any]) -> None:
        self._ws.send(json.dumps(payload))

    def close(self, code: int = 1000, reason: str = "") -> None:
        self._ws.close(code, reason)


class HostedSessionActor:
    def __init__(
        self,
        *,
        browser_ws: Any,
        settings: Any,
        controller_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._browser_ws = browser_ws
        self._controller_factory = controller_factory
        self._settings = settings
        self._controller = None

    async def on_text(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._browser_ws.send_json(
                {"type": "error", "message": "Invalid control message"}
            )
            return

        msg_type = payload.get("type")
        if msg_type == "start":
            await self._start()
            return

        if msg_type == "stop":
            await self._stop()
            return

        await self._browser_ws.send_json(
            {"type": "error", "message": "Unknown control message"}
        )

    async def on_bytes(self, chunk: bytes) -> None:
        if self._controller is None:
            return
        await self._controller.send_audio(chunk)

    async def _start(self) -> None:
        self._controller = self._build_controller()
        try:
            await self._controller.start(self._settings)
        except Exception as exc:
            await self._handle_session_error(exc)
            self._controller = None
            return
        await self._browser_ws.send_json({"type": "started"})

    async def _stop(self) -> None:
        if self._controller is None:
            return

        stop_result = await self._controller.stop(
            timeout_seconds=self._stop_timeout_seconds()
        )
        await self._browser_ws.send_json(
            {
                "type": "stopped",
                "transcript": stop_result.transcript_text,
            }
        )
        self._controller = None

    def _build_controller(self) -> LiveSessionController | Any:
        if self._controller_factory is not None:
            return self._controller_factory()

        return LiveSessionController(
            create_stt_session=create_stt_session,
            on_update=self._handle_transcript_update,
            on_error=self._handle_session_error,
        )

    async def _handle_transcript_update(self, result: Any) -> None:
        if not result.tokens:
            return
        await self._browser_ws.send_json(
            {
                "type": "transcript",
                "tokens": result.tokens,
            }
        )

    async def _handle_session_error(self, exc: Exception) -> None:
        await self._browser_ws.send_json({"type": "error", "message": str(exc)})

    def _stop_timeout_seconds(self) -> float:
        if hasattr(self._settings, "stop_timeout_seconds"):
            return float(self._settings.stop_timeout_seconds)
        return float(getattr(self._settings, "soniox_stop_timeout_seconds", 15.0))

    async def close(self) -> None:
        if self._controller is None:
            return
        await self._controller.close()
        self._controller = None


def _message_to_bytes(message: Any) -> bytes:
    if isinstance(message, bytes):
        return message
    if isinstance(message, bytearray):
        return bytes(message)
    if isinstance(message, memoryview):
        return message.tobytes()
    if hasattr(message, "to_py"):
        converted = message.to_py()
        if isinstance(converted, list):
            return bytes(converted)
        return _message_to_bytes(converted)
    return bytes(message)


class SessionRuntime(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env
        self._session: HostedSessionActor | None = None

    async def fetch(self, request):
        if WebSocketPair is None:
            return Response("WebSocketPair is unavailable", status=500)

        client, server = WebSocketPair.new().object_values()
        self.ctx.acceptWebSocket(server)
        self._session = HostedSessionActor(
            browser_ws=BrowserSocketAdapter(server),
            settings=get_settings(self.env),
        )
        return Response(
            None,
            status=101,
            web_socket=client,
        )

    async def webSocketMessage(self, ws, message):
        del ws

        if self._session is None:
            return

        if isinstance(message, str):
            await self._session.on_text(str(message))
            return

        await self._session.on_bytes(_message_to_bytes(message))

    async def webSocketClose(self, ws, code, reason, was_clean):
        del ws, code, reason, was_clean

        if self._session is None:
            return

        await self._session.close()
        self._session = None
