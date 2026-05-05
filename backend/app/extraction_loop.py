from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import logfire

from app.models import Todo
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TodoStopOutcome:
    items_to_send: list[Todo]
    warning: str | None
    should_resend_latest_snapshot: bool
    final_extraction_ran: bool


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
        self._dirty = False
        self._stopping = False
        self._generation = 0
        self._in_flight_task: asyncio.Task[None] | None = None
        self._last_successful_transcript: str | None = None

    async def on_endpoint(self) -> None:
        self._trigger_background_extraction(trigger_reason="endpoint")

    def on_transcript_changed(self) -> None:
        if self._transcript_growth_since_last_extraction() >= self._token_threshold:
            self._trigger_background_extraction(trigger_reason="transcript_threshold")
        elif self._in_flight_task is not None and not self._in_flight_task.done():
            self._dirty = True

    async def on_stop(
        self,
        *,
        final_transcript_text: str | None = None,
        transcript_timed_out: bool = False,
    ) -> TodoStopOutcome:
        self._stopping = True
        try:
            task = self._in_flight_task
            if task is not None:
                await task

            stop_transcript = final_transcript_text
            if stop_transcript is None:
                stop_transcript = self._transcript_text()

            if transcript_timed_out:
                return TodoStopOutcome(
                    items_to_send=list(self._previous_todos),
                    warning=(
                        "Timed out waiting for the final transcript; "
                        "todos were not extracted."
                    ),
                    should_resend_latest_snapshot=True,
                    final_extraction_ran=False,
                )

            if not stop_transcript.strip():
                return TodoStopOutcome(
                    items_to_send=list(self._previous_todos),
                    warning=None,
                    should_resend_latest_snapshot=True,
                    final_extraction_ran=False,
                )

            if stop_transcript == self._last_successful_transcript:
                return TodoStopOutcome(
                    items_to_send=list(self._previous_todos),
                    warning=None,
                    should_resend_latest_snapshot=True,
                    final_extraction_ran=False,
                )

            previous_todos = list(self._previous_todos) or None
            try:
                todos = await self._extract_todos(
                    stop_transcript,
                    trigger_reason="stop",
                    previous_todos=previous_todos,
                )
            except Exception:
                return TodoStopOutcome(
                    items_to_send=list(self._previous_todos),
                    warning="Todo extraction failed.",
                    should_resend_latest_snapshot=True,
                    final_extraction_ran=True,
                )

            self._record_success(todos, transcript_text=stop_transcript)
            return TodoStopOutcome(
                items_to_send=list(todos),
                warning=None,
                should_resend_latest_snapshot=False,
                final_extraction_ran=True,
            )
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
        self._previous_todos = []
        self._last_successful_transcript = None

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

                if (
                    trigger_reason == "transcript_threshold"
                    and self._transcript_growth_since_last_extraction()
                    < self._token_threshold
                ):
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
            todos = await self._extract_todos(
                transcript_text,
                trigger_reason=trigger_reason,
                previous_todos=previous_todos,
            )

            if generation is not None and generation != self._generation:
                return False

            await self._send_fn(todos)

            if generation is not None and generation != self._generation:
                return False

            self._record_success(todos, transcript_text=transcript_text)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            if propagate_errors:
                raise

            logger.exception("Background todo extraction failed")
            return False

    async def _extract_todos(
        self,
        transcript_text: str,
        *,
        trigger_reason: str,
        previous_todos: list[Todo] | None,
    ) -> list[Todo]:
        with logfire.span(
            "extraction_cycle",
            _span_name="extraction_cycle",
            trigger_reason=trigger_reason,
            transcript_length=len(transcript_text),
            previous_todo_count=len(previous_todos) if previous_todos else 0,
        ):
            return await self._extract_fn(
                transcript_text,
                previous_todos=previous_todos,
            )

    def _record_success(self, todos: list[Todo], *, transcript_text: str) -> None:
        self._previous_todos = list(todos)
        self._last_successful_transcript = transcript_text

    def _transcript_text(self) -> str:
        return self._transcript.full_text

    def _transcript_growth_since_last_extraction(self) -> int:
        baseline = 0
        if self._last_successful_transcript is not None:
            baseline = len(self._last_successful_transcript.split())
        return self._transcript.full_token_count - baseline
