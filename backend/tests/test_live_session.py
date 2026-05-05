import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttToken


class _FakeSttSession:
    def __init__(
        self,
        events=None,
        *,
        final_transcript_text=None,
        capabilities=None,
        per_event_delay: float = 0.0,
    ):
        self._events = list(events or [])
        self.capabilities = capabilities or SttCapabilities(
            exposes_finalization_boundary=True,
            exposes_endpoint_boundary=True,
        )
        self.final_transcript_text = final_transcript_text
        self._per_event_delay = per_event_delay
        self.send_audio = AsyncMock()
        self.request_final_transcript = AsyncMock()
        self.end_stream = AsyncMock()
        self.wait_for_final_transcript = AsyncMock()
        self.close = AsyncMock()

    async def _iterate(self):
        for event in self._events:
            if self._per_event_delay > 0:
                await asyncio.sleep(self._per_event_delay)
            yield event

    def __aiter__(self):
        return self._iterate()


@pytest.mark.asyncio
async def test_controller_start_emits_transcript_tokens_in_order():
    from app.live_session import LiveSessionController

    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            ),
            SttEvent(
                tokens=[SttToken(text="milk", is_final=False)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            ),
            SttEvent(is_finished=True),
        ]
    )
    session_factory = AsyncMock(return_value=fake_session)
    updates = []
    done = asyncio.Event()

    async def on_update(result):
        updates.append(result.tokens)
        if len(updates) == 2:
            done.set()

    controller = LiveSessionController(
        create_stt_session=session_factory,
        on_update=on_update,
    )

    await controller.start(SimpleNamespace())
    await asyncio.wait_for(done.wait(), timeout=1)
    await controller.close()

    assert updates == [
        [{"text": "Buy ", "is_final": True}],
        [{"text": "milk", "is_final": False}],
    ]


@pytest.mark.asyncio
async def test_controller_send_audio_forwards_bytes_to_active_session():
    from app.live_session import LiveSessionController

    fake_session = _FakeSttSession(events=[SttEvent(is_finished=True)])
    session_factory = AsyncMock(return_value=fake_session)
    controller = LiveSessionController(create_stt_session=session_factory)

    await controller.start(SimpleNamespace())
    await controller.send_audio(b"\x00\x01")
    await controller.close()

    fake_session.send_audio.assert_awaited_once_with(b"\x00\x01")
