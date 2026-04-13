import asyncio
from contextlib import nullcontext
from unittest.mock import AsyncMock, patch

import pytest

from app.extraction_loop import ExtractionLoop
from app.models import Todo
from app.transcript_accumulator import TranscriptAccumulator


async def _wait_for_background(loop: ExtractionLoop) -> None:
    task = loop._in_flight_task
    if task is not None:
        await task


async def _trigger_endpoint(loop: ExtractionLoop) -> None:
    await loop.on_endpoint()
    await _wait_for_background(loop)


async def _trigger_token_threshold(loop: ExtractionLoop) -> None:
    loop.on_transcript_changed()
    await _wait_for_background(loop)


async def _trigger_stop(loop: ExtractionLoop) -> None:
    await loop.on_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger_reason", "trigger"),
    [
        ("endpoint", _trigger_endpoint),
        ("transcript_threshold", _trigger_token_threshold),
        ("stop", _trigger_stop),
    ],
)
async def test_extraction_cycle_span_includes_expected_attributes(
    trigger_reason: str,
    trigger,
):
    transcript_text = (
        "Buy milk tomorrow"
        if trigger_reason == "transcript_threshold"
        else "Buy milk"
    )
    transcript = TranscriptAccumulator(final_parts=[transcript_text])
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
        token_threshold=3,
    )

    with patch(
        "app.extraction_loop.logfire.span",
        return_value=nullcontext(),
    ) as mock_span:
        await trigger(loop)

    mock_span.assert_called_once()
    _, kwargs = mock_span.call_args
    assert kwargs["_span_name"] == "extraction_cycle"
    assert kwargs["trigger_reason"] == trigger_reason
    assert kwargs["transcript_length"] == len(transcript_text)
    assert kwargs["previous_todo_count"] == 0


@pytest.mark.asyncio
async def test_on_endpoint_triggers_extraction():
    transcript = TranscriptAccumulator(
        final_parts=["Buy milk"],
        interim_parts=[" tomorrow"],
    )
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    await _wait_for_background(loop)

    extract_fn.assert_awaited_once_with("Buy milk tomorrow", previous_todos=None)
    send_fn.assert_awaited_once_with([Todo(text="Buy milk")])


@pytest.mark.asyncio
async def test_on_transcript_changed_triggers_extraction_when_threshold_is_reached():
    transcript = TranscriptAccumulator(final_parts=["Buy milk tomorrow"])
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
        token_threshold=3,
    )

    loop.on_transcript_changed()
    await _wait_for_background(loop)

    extract_fn.assert_awaited_once_with("Buy milk tomorrow", previous_todos=None)
    send_fn.assert_awaited_once_with([Todo(text="Buy milk")])


@pytest.mark.asyncio
async def test_on_transcript_changed_below_threshold_does_not_trigger_extraction():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
        token_threshold=3,
    )

    loop.on_transcript_changed()
    await asyncio.sleep(0)

    extract_fn.assert_not_awaited()
    send_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_dirty_flag_collapses_multiple_triggers_into_one_rerun():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    send_fn = AsyncMock()
    started = asyncio.Event()
    release_first = asyncio.Event()
    call_count = 0

    async def extract_fn(text: str, *, previous_todos: list[Todo]) -> list[Todo]:
        nonlocal call_count
        call_count += 1
        if not started.is_set():
            started.set()
            await release_first.wait()
            return [Todo(text="Buy milk")]
        return [Todo(text="Buy milk"), Todo(text="Call mom")]

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
        token_threshold=3,
    )

    await loop.on_endpoint()
    await started.wait()

    transcript.final_parts.append(" and call mom")
    await loop.on_endpoint()
    loop.on_transcript_changed()
    await loop.on_endpoint()

    release_first.set()
    await _wait_for_background(loop)

    assert call_count == 2
    assert send_fn.await_count == 2


@pytest.mark.asyncio
async def test_on_stop_waits_for_in_flight_then_runs_exactly_one_final_pass():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    send_fn = AsyncMock()
    started = asyncio.Event()
    release_first = asyncio.Event()
    call_texts: list[str] = []

    async def extract_fn(text: str, *, previous_todos: list[Todo]) -> list[Todo]:
        call_texts.append(text)
        if not started.is_set():
            started.set()
            await release_first.wait()
            return [Todo(text="Buy milk")]
        return [Todo(text="Buy milk and call mom")]

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    await started.wait()

    transcript.final_parts.append(" and call mom")
    await loop.on_endpoint()
    stop_task = asyncio.create_task(loop.on_stop())
    await asyncio.sleep(0)

    release_first.set()
    await stop_task

    assert call_texts == ["Buy milk", "Buy milk and call mom"]
    assert send_fn.await_count == 2


@pytest.mark.asyncio
async def test_on_stop_skips_redundant_final_pass_when_transcript_is_unchanged():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    send_fn = AsyncMock()
    started = asyncio.Event()
    release_first = asyncio.Event()
    call_texts: list[str] = []

    async def extract_fn(text: str, *, previous_todos: list[Todo]) -> list[Todo]:
        call_texts.append(text)
        started.set()
        await release_first.wait()
        return [Todo(text="Buy milk")]

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    await started.wait()

    stop_task = asyncio.create_task(loop.on_stop())
    await asyncio.sleep(0)

    release_first.set()
    await stop_task

    assert call_texts == ["Buy milk"]
    assert send_fn.await_count == 1


@pytest.mark.asyncio
async def test_on_stop_without_in_flight_runs_one_pass():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_stop()

    extract_fn.assert_awaited_once_with("Buy milk", previous_todos=None)
    send_fn.assert_awaited_once_with([Todo(text="Buy milk")])


@pytest.mark.asyncio
async def test_on_stop_propagates_final_pass_failure():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    extract_fn = AsyncMock(side_effect=RuntimeError("boom"))
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    with pytest.raises(RuntimeError, match="boom"):
        await loop.on_stop()

    send_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_previous_todos_are_forwarded_into_later_extractions():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    extract_fn = AsyncMock(
        side_effect=[
            [Todo(text="Buy milk")],
            [Todo(text="Buy milk"), Todo(text="Call mom")],
        ]
    )
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    await _wait_for_background(loop)

    transcript.final_parts.append(" and call mom")
    await loop.on_endpoint()
    await _wait_for_background(loop)

    assert extract_fn.await_args_list[0].kwargs["previous_todos"] is None
    assert extract_fn.await_args_list[1].kwargs["previous_todos"] == [
        Todo(text="Buy milk")
    ]


@pytest.mark.asyncio
async def test_cancel_stops_in_flight_task_and_resets_state():
    transcript = TranscriptAccumulator(final_parts=["Buy milk"])
    send_fn = AsyncMock()
    started = asyncio.Event()
    release_second = asyncio.Event()
    call_count = 0

    async def extract_fn(text: str, *, previous_todos: list[Todo]) -> list[Todo]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [Todo(text="Buy milk")]

        started.set()
        await release_second.wait()
        return [Todo(text="Buy milk"), Todo(text="Call mom")]

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    await _wait_for_background(loop)

    transcript.final_parts.append(" and call mom")
    await loop.on_endpoint()
    await started.wait()
    task = loop._in_flight_task

    loop.on_transcript_changed()
    loop.cancel()

    assert task is not None
    with pytest.raises(asyncio.CancelledError):
        await task

    assert loop._in_flight_task is None
    assert loop._dirty is False
    assert loop._last_successful_transcript is None
    assert loop._previous_todos == []


@pytest.mark.asyncio
async def test_empty_transcript_skips_extraction():
    transcript = TranscriptAccumulator()
    extract_fn = AsyncMock(return_value=[Todo(text="Buy milk")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=extract_fn,
    )

    await loop.on_endpoint()
    loop.on_transcript_changed()
    await asyncio.sleep(0)
    await loop.on_stop()

    extract_fn.assert_not_awaited()
    send_fn.assert_not_awaited()
