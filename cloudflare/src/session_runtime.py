from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

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
        controller_factory: Callable[[], Any],
        settings: Any,
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
            self._controller = self._controller_factory()
            await self._controller.start(self._settings)
            await self._browser_ws.send_json({"type": "started"})
            return

        await self._browser_ws.send_json(
            {"type": "error", "message": "Unknown control message"}
        )


class SessionRuntime(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env
