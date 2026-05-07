from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.transcript_accumulator import (
    TranscriptAccumulator,
    TranscriptAccumulatorResult,
)

UpdateCallback = Callable[[TranscriptAccumulatorResult], Awaitable[None] | None]
ErrorCallback = Callable[[Exception], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class StopResult:
    transcript_text: str
    timed_out: bool


class LiveSessionController:
    def __init__(
        self,
        *,
        create_stt_session: Callable[..., Awaitable[Any]],
        on_update: UpdateCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        self._create_stt_session = create_stt_session
        self._on_update = on_update
        self._on_error = on_error
        self._transcript = TranscriptAccumulator()
        self._stt_session = None
        self._relay_task: asyncio.Task[None] | None = None
        self._finalized_event = asyncio.Event()

    @property
    def transcript(self) -> TranscriptAccumulator:
        return self._transcript

    async def start(self, settings: Any, *, recorder: Any = None) -> None:
        self._transcript.reset()
        self._finalized_event = asyncio.Event()
        self._stt_session = await self._create_stt_session(
            settings,
            recorder=recorder,
        )
        self._relay_task = asyncio.create_task(self._relay_provider_events())

    async def send_audio(self, chunk: bytes) -> None:
        if self._stt_session is None:
            return
        await self._stt_session.send_audio(chunk)

    async def stop(self, *, timeout_seconds: float) -> StopResult:
        if self._stt_session is None:
            return StopResult(
                transcript_text=self._transcript.full_text,
                timed_out=False,
            )

        await self._stt_session.request_final_transcript()
        await self._stt_session.end_stream()

        timed_out = False
        try:
            await asyncio.wait_for(
                self._wait_for_final_transcript(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            timed_out = True

        transcript_text = (
            self._stt_session.final_transcript_text
            if self._stt_session.final_transcript_text is not None
            else self._transcript.full_text
        )
        if self._stt_session.final_transcript_text is not None:
            self._transcript.final_parts = [transcript_text]
            self._transcript.interim_parts.clear()

        await self.close()
        return StopResult(transcript_text=transcript_text, timed_out=timed_out)

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

        try:
            async for event in self._stt_session:
                if event.is_finished:
                    return

                result = self._transcript.apply_stt_event(event)
                if result.has_fin:
                    self._finalized_event.set()
                if self._on_update is not None:
                    maybe_awaitable = self._on_update(result)
                    if maybe_awaitable is not None:
                        await maybe_awaitable
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._on_error is not None:
                maybe_awaitable = self._on_error(exc)
                if maybe_awaitable is not None:
                    await maybe_awaitable

    async def _wait_for_final_transcript(self) -> None:
        assert self._stt_session is not None

        wait_tasks = [
            asyncio.create_task(self._stt_session.wait_for_final_transcript()),
            asyncio.create_task(self._finalized_event.wait()),
        ]
        done, pending = await asyncio.wait(
            wait_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        for task in done:
            task.result()
