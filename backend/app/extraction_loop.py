from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import logfire

from app.models import Todo
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)


class ExtractionLoop:
    def __init__(
        self,
        transcript: TranscriptAccumulator,
        send_fn: Callable[[list[Todo]], Awaitable[None]],
        extract_fn: Callable[..., Awaitable[list[Todo]]],
        token_threshold: int = 30,
    ) -> None:
        self._transcript = transcript
        self._send_fn = send_fn
        self._extract_fn = extract_fn
        self._token_threshold = token_threshold

        self._previous_todos: list[Todo] = []
        self._tokens_since_last_extraction = 0
        self._dirty = False
        self._stopping = False
        self._generation = 0
        self._in_flight_task: asyncio.Task[None] | None = None

    async def on_endpoint(self) -> None:
        self._trigger_background_extraction(trigger_reason="endpoint")

    def on_tokens(self, count: int) -> None:
        if count <= 0:
            return

        self._tokens_since_last_extraction += count
        if self._tokens_since_last_extraction >= self._token_threshold:
            self._trigger_background_extraction(trigger_reason="token_threshold")

    async def on_stop(self) -> None:
        self._stopping = True
        try:
            task = self._in_flight_task
            if task is not None:
                await task

            await self._run_extraction(propagate_errors=True, trigger_reason="stop")
        finally:
            self._dirty = False
            self._stopping = False

    def cancel(self) -> None:
        self._generation += 1
        task = self._in_flight_task
        if task is not None:
            task.cancel()

        self._in_flight_task = None
        self._dirty = False
        self._stopping = False
        self._tokens_since_last_extraction = 0
        self._previous_todos = []

    def _trigger_background_extraction(self, *, trigger_reason: str) -> None:
        if self._stopping or not self._transcript_text().strip():
            return

        if self._in_flight_task is not None and not self._in_flight_task.done():
            self._dirty = True
            return

        self._dirty = False
        generation = self._generation
        self._in_flight_task = asyncio.create_task(
            self._run_background_loop(generation, trigger_reason=trigger_reason)
        )

    async def _run_background_loop(
        self,
        generation: int,
        *,
        trigger_reason: str,
    ) -> None:
        try:
            while True:
                self._dirty = False
                await self._run_extraction(
                    propagate_errors=False,
                    generation=generation,
                    trigger_reason=trigger_reason,
                )

                if self._stopping or generation != self._generation or not self._dirty:
                    return
        except asyncio.CancelledError:
            raise
        finally:
            if self._in_flight_task is asyncio.current_task():
                self._in_flight_task = None

    async def _run_extraction(
        self,
        *,
        propagate_errors: bool,
        trigger_reason: str,
        generation: int | None = None,
    ) -> bool:
        transcript_text = self._transcript_text()
        if not transcript_text.strip():
            return False

        try:
            previous_todos = list(self._previous_todos) or None
            with logfire.span(
                "extraction_cycle",
                _span_name="extraction_cycle",
                trigger_reason=trigger_reason,
                transcript_length=len(transcript_text),
                previous_todo_count=len(previous_todos) if previous_todos else 0,
            ):
                todos = await self._extract_fn(
                    transcript_text,
                    previous_todos=previous_todos,
                )

            if generation is not None and generation != self._generation:
                return False

            await self._send_fn(todos)

            if generation is not None and generation != self._generation:
                return False

            self._previous_todos = list(todos)
            self._tokens_since_last_extraction = 0
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            if propagate_errors:
                raise

            logger.exception("Background todo extraction failed")
            return False

    def _transcript_text(self) -> str:
        return self._transcript.full_text
