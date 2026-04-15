import asyncio
from unittest.mock import AsyncMock

import pytest

from app.stt import BoundaryState
from app.stt_mistral import MistralSession, translate_mistral_event


def test_translate_mistral_text_delta_emits_additive_final_token():
    event = translate_mistral_event(
        {"type": "transcription.text.delta", "text": "Buy"}
    )

    assert [token.text for token in event.tokens] == ["Buy"]
    assert all(token.is_final for token in event.tokens)
    assert event.finalization_state is BoundaryState.NOT_OBSERVED
    assert event.endpoint_state is BoundaryState.UNSUPPORTED
    assert event.is_finished is False


def test_translate_mistral_done_marks_finished_without_fake_boundaries():
    event = translate_mistral_event(
        {"type": "transcription.done", "text": "Buy milk tomorrow"}
    )

    assert event.tokens == []
    assert event.finalization_state is BoundaryState.NOT_OBSERVED
    assert event.endpoint_state is BoundaryState.UNSUPPORTED
    assert event.is_finished is True


def test_translate_mistral_session_metadata_emits_empty_event():
    event = translate_mistral_event({"type": "session.updated"})

    assert event.tokens == []
    assert event.finalization_state is BoundaryState.NOT_OBSERVED
    assert event.endpoint_state is BoundaryState.UNSUPPORTED
    assert event.is_finished is False


@pytest.mark.asyncio
async def test_mistral_session_sets_final_transcript_text_on_done():
    connection = _FakeRealtimeConnection(
        [
            {"type": "session.created"},
            {"type": "transcription.text.delta", "text": "Buy milk"},
            {"type": "transcription.done", "text": "Buy milk tomorrow"},
        ]
    )
    session = MistralSession(connection)
    wait_task = asyncio.create_task(session.wait_for_final_transcript())

    events = [event async for event in session]

    assert len(events) == 3
    assert events[0].tokens == []
    assert [token.text for token in events[1].tokens] == ["Buy milk"]
    assert events[2].is_finished is True
    await wait_task
    assert session.final_transcript_text == "Buy milk tomorrow"


@pytest.mark.asyncio
async def test_mistral_session_maps_stream_controls_to_realtime_connection():
    connection = _FakeRealtimeConnection([])
    session = MistralSession(connection)

    await session.send_audio(b"pcm")
    await session.request_final_transcript()
    await session.end_stream()
    await session.close()

    connection.send_audio.assert_awaited_once_with(b"pcm")
    connection.flush_audio.assert_awaited_once_with()
    connection.end_audio.assert_awaited_once_with()
    connection.close.assert_awaited_once_with()


def test_mistral_session_exposes_final_transcript_accessor():
    session = MistralSession(_FakeRealtimeConnection([]))

    assert session.final_transcript_text is None


@pytest.mark.asyncio
async def test_mistral_session_records_raw_events_through_callback():
    recorded = []
    connection = _FakeRealtimeConnection(
        [
            {"type": "session.created"},
            {"type": "transcription.text.delta", "text": "Buy milk"},
            {"type": "transcription.done", "text": "Buy milk tomorrow"},
        ]
    )
    session = MistralSession(connection, raw_event_callback=recorded.append)

    [event async for event in session]

    assert recorded == [
        {"type": "session.created"},
        {"type": "transcription.text.delta", "text": "Buy milk"},
        {"type": "transcription.done", "text": "Buy milk tomorrow"},
    ]


class _FakeRealtimeConnection:
    def __init__(self, events):
        self._events = list(events)
        self.send_audio = AsyncMock()
        self.flush_audio = AsyncMock()
        self.end_audio = AsyncMock()
        self.close = AsyncMock()

    async def events(self):
        for event in self._events:
            yield event
