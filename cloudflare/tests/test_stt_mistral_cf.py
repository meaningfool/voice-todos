from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.stt_mistral_shared import MistralSession
from stt_mistral_cf import connect_mistral


@pytest.mark.asyncio
async def test_cf_mistral_connect_builds_shared_mistral_session() -> None:
    connection = _FakeRealtimeConnection([])
    client_factory = _FakeMistralClientFactory(connection)

    session = await connect_mistral(
        "mistral-test-key",
        client_factory=client_factory,
        target_streaming_delay_ms=250,
    )

    assert isinstance(session, MistralSession)
    assert client_factory.api_key == "mistral-test-key"
    assert client_factory.connect_calls == [
        {
            "model": "voxtral-mini-transcribe-realtime-2602",
            "target_streaming_delay_ms": 250,
        }
    ]


@pytest.mark.asyncio
async def test_cf_mistral_session_uses_shared_final_transcript_semantics() -> None:
    session = await connect_mistral(
        "mistral-test-key",
        client_factory=_FakeMistralClientFactory(
            _FakeRealtimeConnection(
                [
                    {"type": "transcription.text.delta", "text": "Buy milk"},
                    {"type": "transcription.done", "text": "Buy milk tomorrow"},
                ]
            )
        ),
    )

    events = [event async for event in session]

    assert [token.text for token in events[0].tokens] == ["Buy milk"]
    assert events[1].is_finished is True
    assert session.final_transcript_text == "Buy milk tomorrow"


class _FakeMistralClientFactory:
    def __init__(self, connection: "_FakeRealtimeConnection") -> None:
        self.connection = connection
        self.api_key: str | None = None
        self.connect_calls: list[dict] = []

    def __call__(self, *, api_key: str):
        self.api_key = api_key
        return self

    @property
    def audio(self):
        return self

    @property
    def realtime(self):
        return self

    async def connect(self, **kwargs):
        self.connect_calls.append(
            {
                "model": kwargs["model"],
                "target_streaming_delay_ms": kwargs["target_streaming_delay_ms"],
            }
        )
        return self.connection


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
