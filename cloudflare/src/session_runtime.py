from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from repo_bootstrap import bootstrap_backend_imports
from settings import get_settings

bootstrap_backend_imports()

from app.extract import extract_todos  # noqa: E402
from app.extraction_loop import ExtractionLoop, TodoStopOutcome  # noqa: E402
from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD  # noqa: E402
from app.live_session import LiveSessionController, StopResult  # noqa: E402
from app.models import Todo  # noqa: E402
from stt_factory_cf import create_stt_session  # noqa: E402

TOKEN_THRESHOLD = EXTRACTION_TOKEN_THRESHOLD

WebSocketPair: Any | None

try:
    from js import WebSocketPair as js_websocket_pair
except ImportError:  # pragma: no cover - unavailable in local pytest
    WebSocketPair = None
else:
    WebSocketPair = js_websocket_pair

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
        self._extraction_loop: ExtractionLoop | Any | None = None
        self._cleanup_started = False
        self._terminal_sent = False

    async def on_text(self, raw_message: str) -> str | None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._browser_ws.send_json(
                {"type": "error", "message": "Invalid control message"}
            )
            return None

        msg_type = payload.get("type")
        if msg_type == "start":
            return await self._start()

        if msg_type == "stop":
            await self._stop(close_reason="session finished")
            return "stopped"

        await self._browser_ws.send_json(
            {"type": "error", "message": "Unknown control message"}
        )
        return None

    async def on_bytes(self, chunk: bytes) -> None:
        if self._controller is None:
            return
        await self._controller.send_audio(chunk)

    async def _start(self) -> str | None:
        self._controller = self._build_controller()
        try:
            await self._controller.start(self._settings)
            self._extraction_loop = self._build_extraction_loop(self._controller)
        except Exception as exc:
            await self._handle_session_error(exc)
            self._controller = None
            self._extraction_loop = None
            return None
        await self._browser_ws.send_json({"type": "started"})
        return "started"

    async def _stop(self, *, close_reason: str) -> None:
        if self._terminal_sent or self._cleanup_started:
            return
        stop_result = await self._stop_controller()
        stop_outcome = await self._stop_extraction_loop(stop_result)
        await self._browser_ws.send_json(
            {
                "type": "todos",
                "items": _serialize_todos(stop_outcome.items_to_send),
            }
        )
        payload = {
            "type": "stopped",
            "transcript": stop_result.transcript_text,
        }
        if stop_outcome.warning is not None:
            payload["warning"] = stop_outcome.warning
        await self._browser_ws.send_json(payload)
        self._terminal_sent = True
        await self._cleanup(close_socket=True, close_code=1000, close_reason=close_reason)

    def _build_controller(self) -> LiveSessionController | Any:
        if self._controller_factory is not None:
            return self._controller_factory()

        return LiveSessionController(
            create_stt_session=create_stt_session,
            on_update=self._handle_transcript_update,
            on_error=self._handle_session_error,
        )

    def _build_extraction_loop(self, controller: Any) -> ExtractionLoop | Any:
        if not hasattr(controller, "transcript"):
            return None
        return ExtractionLoop(
            transcript=controller.transcript,
            send_fn=self._send_todos,
            extract_fn=extract_todos,
            token_threshold=TOKEN_THRESHOLD,
        )

    async def _handle_transcript_update(self, result: Any) -> None:
        if result.tokens:
            await self._browser_ws.send_json(
                {
                    "type": "transcript",
                    "tokens": result.tokens,
                }
            )

        if self._extraction_loop is None:
            return

        if result.has_endpoint:
            await self._extraction_loop.on_endpoint()
        elif result.transcript_changed:
            self._extraction_loop.on_transcript_changed()

    async def _handle_session_error(self, exc: Exception) -> None:
        await self.on_provider_failure(exc)

    def _stop_timeout_seconds(self) -> float:
        if hasattr(self._settings, "stop_timeout_seconds"):
            return float(self._settings.stop_timeout_seconds)
        return float(getattr(self._settings, "soniox_stop_timeout_seconds", 15.0))

    async def close(self) -> None:
        await self._cleanup(close_socket=False, close_code=1000, close_reason="")

    async def on_cap_expiry(self) -> None:
        await self._stop(close_reason="session cap reached")

    async def on_provider_failure(self, exc: Exception) -> None:
        if self._cleanup_started:
            return
        await self._browser_ws.send_json({"type": "error", "message": str(exc)})
        await self._cleanup(
            close_socket=True,
            close_code=1011,
            close_reason="provider failure",
        )

    async def _stop_controller(self):
        if self._controller is None:
            return StopResult(transcript_text="", timed_out=False)

        controller = self._controller
        self._controller = None
        return await controller.stop(timeout_seconds=self._stop_timeout_seconds())

    async def _stop_extraction_loop(self, stop_result: Any) -> TodoStopOutcome:
        if self._extraction_loop is None:
            return TodoStopOutcome(
                items_to_send=[],
                warning=None,
                should_resend_latest_snapshot=True,
                final_extraction_ran=False,
            )

        extraction_loop = self._extraction_loop
        self._extraction_loop = None
        return await extraction_loop.on_stop(
            final_transcript_text=stop_result.transcript_text,
            transcript_timed_out=stop_result.timed_out,
        )

    async def _send_todos(self, todos: list[Todo]) -> None:
        await self._browser_ws.send_json(
            {
                "type": "todos",
                "items": _serialize_todos(todos),
            }
        )

    async def _cleanup(
        self,
        *,
        close_socket: bool,
        close_code: int,
        close_reason: str,
    ) -> None:
        if self._cleanup_started:
            return
        self._cleanup_started = True

        if self._controller is None:
            controller = None
        else:
            controller = self._controller
            self._controller = None

        if self._extraction_loop is not None:
            self._extraction_loop.cancel()
            self._extraction_loop = None

        if controller is not None:
            await controller.close()

        if close_socket and hasattr(self._browser_ws, "close"):
            self._browser_ws.close(close_code, close_reason)


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


def _serialize_todos(todos: list[Todo]) -> list[dict[str, Any]]:
    return [
        todo.model_dump(exclude_none=True, mode="json")
        for todo in todos
    ]


class SessionRuntime(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env
        self._session: HostedSessionActor | None = None
        self._settings = get_settings(env)
        self._cap_task: asyncio.Task[None] | None = None

    async def fetch(self, request):
        if WebSocketPair is None:
            return Response("WebSocketPair is unavailable", status=500)

        client, server = WebSocketPair.new().object_values()
        self.ctx.acceptWebSocket(server)
        self._session = HostedSessionActor(
            browser_ws=BrowserSocketAdapter(server),
            settings=self._settings,
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
            outcome = await self._session.on_text(str(message))
            if outcome == "started":
                self.ctx.storage.setAlarm(
                    int(time.time() * 1000) + self._settings.session_cap_ms
                )
                self._schedule_cap_timer()
            elif outcome == "stopped":
                self._cancel_cap_timer()
                self._session = None
            return

        await self._session.on_bytes(_message_to_bytes(message))

    async def webSocketClose(self, ws, code, reason, was_clean):
        del ws, code, reason, was_clean

        if self._session is None:
            return

        self._cancel_cap_timer()
        await self._session.close()
        self._session = None

    async def alarm(self):
        if self._session is None:
            return

        self._cancel_cap_timer()
        await self._session.on_cap_expiry()
        self._session = None

    def _schedule_cap_timer(self) -> None:
        self._cancel_cap_timer()
        self._cap_task = asyncio.create_task(self._run_cap_timer())

    def _cancel_cap_timer(self) -> None:
        if self._cap_task is None:
            return
        self._cap_task.cancel()
        self._cap_task = None

    async def _run_cap_timer(self) -> None:
        try:
            await asyncio.sleep(self._settings.session_cap_ms / 1000)
            if self._session is None:
                return
            await self._session.on_cap_expiry()
            self._session = None
        except asyncio.CancelledError:
            raise
