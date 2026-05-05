from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.repo_bootstrap import bootstrap_backend_imports

bootstrap_backend_imports()

from app.live_session import LiveSessionController
from src.stt_factory_cf import create_stt_session

try:
    from workers import DurableObject
except ModuleNotFoundError:  # pragma: no cover - local pytest import fallback
    class DurableObject:
        def __init__(self, ctx: Any, env: Any) -> None:
            self.ctx = ctx
            self.env = env


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


class SessionRuntime(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env
