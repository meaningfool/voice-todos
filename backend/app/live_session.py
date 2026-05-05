from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from app.transcript_accumulator import (
    TranscriptAccumulator,
    TranscriptAccumulatorResult,
)

UpdateCallback = Callable[[TranscriptAccumulatorResult], Awaitable[None] | None]


class LiveSessionController:
    def __init__(
        self,
        *,
        create_stt_session: Callable[..., Awaitable[Any]],
        on_update: UpdateCallback | None = None,
    ) -> None:
        self._create_stt_session = create_stt_session
        self._on_update = on_update
        self._transcript = TranscriptAccumulator()
        self._stt_session = None
        self._relay_task: asyncio.Task[None] | None = None

    async def start(self, settings: Any, *, recorder: Any = None) -> None:
        self._transcript.reset()
        self._stt_session = await self._create_stt_session(
            settings,
            recorder=recorder,
        )
        self._relay_task = asyncio.create_task(self._relay_provider_events())

    async def send_audio(self, chunk: bytes) -> None:
        if self._stt_session is None:
            return
        await self._stt_session.send_audio(chunk)

    async def close(self) -> None:
        if self._relay_task is not None:
            self._relay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._relay_task
            self._relay_task = None

        if self._stt_session is not None:
            with contextlib.suppress(Exception):
                await self._stt_session.close()
            self._stt_session = None

    async def _relay_provider_events(self) -> None:
        assert self._stt_session is not None

        async for event in self._stt_session:
            if event.is_finished:
                return

            result = self._transcript.apply_stt_event(event)
            if self._on_update is not None:
                maybe_awaitable = self._on_update(result)
                if maybe_awaitable is not None:
                    await maybe_awaitable
