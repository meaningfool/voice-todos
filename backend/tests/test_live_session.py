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


@pytest.mark.asyncio
async def test_controller_stop_requests_finalize_before_end_stream():
    from app.live_session import LiveSessionController

    call_order: list[str] = []
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy groceries. ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            )
        ]
    )
    fake_session.request_final_transcript.side_effect = lambda: call_order.append(
        "finalize"
    )
    fake_session.end_stream.side_effect = lambda: call_order.append("end_stream")
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)
    session_factory = AsyncMock(return_value=fake_session)
    controller = LiveSessionController(create_stt_session=session_factory)

    await controller.start(SimpleNamespace())
    result = await controller.stop(timeout_seconds=0.1)

    assert result.transcript_text == "Buy groceries. "
    fake_session.request_final_transcript.assert_awaited_once()
    fake_session.end_stream.assert_awaited_once()
    assert call_order == ["finalize", "end_stream"]


@pytest.mark.asyncio
async def test_controller_stop_prefers_provider_final_transcript_text_when_available():
    from app.live_session import LiveSessionController

    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)
    session_factory = AsyncMock(return_value=fake_session)
    controller = LiveSessionController(create_stt_session=session_factory)

    await controller.start(SimpleNamespace())
    result = await controller.stop(timeout_seconds=0.1)

    assert result.transcript_text == "Buy milk tomorrow"
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_controller_stop_returns_timeout_result_without_raising():
    from app.live_session import LiveSessionController

    async def never_finish():
        await asyncio.sleep(1)

    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text=None,
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )
    fake_session.wait_for_final_transcript = AsyncMock(side_effect=never_finish)
    session_factory = AsyncMock(return_value=fake_session)
    controller = LiveSessionController(create_stt_session=session_factory)

    await controller.start(SimpleNamespace())
    result = await controller.stop(timeout_seconds=0.01)

    assert result.transcript_text == "Buy milk"
    assert result.timed_out is True


@pytest.mark.asyncio
async def test_controller_close_is_idempotent_after_stop_or_relay_cancel():
    from app.live_session import LiveSessionController

    fake_session = _FakeSttSession(events=[SttEvent(is_finished=True)])
    session_factory = AsyncMock(return_value=fake_session)
    controller = LiveSessionController(create_stt_session=session_factory)

    await controller.start(SimpleNamespace())
    await controller.close()
    await controller.close()

    fake_session.close.assert_awaited_once()
