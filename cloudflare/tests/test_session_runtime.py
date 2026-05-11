from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import session_runtime
from session_runtime import HostedSessionActor


class _FakeBrowserSocket:
    def __init__(self) -> None:
        self.json_messages: list[dict] = []
        self.close_calls: list[tuple[int, str]] = []

    async def send_json(self, payload: dict) -> None:
        self.json_messages.append(payload)

    def close(self, code: int = 1000, reason: str = "") -> None:
        self.close_calls.append((code, reason))


def _todo_stop_outcome(
    *,
    items: list[dict] | None = None,
    warning: str | None = None,
    should_resend_latest_snapshot: bool = False,
    final_extraction_ran: bool = True,
):
    from app.extraction_loop import TodoStopOutcome
    from app.models import Todo

    todo_items = [] if items is None else [Todo(**item) for item in items]
    return TodoStopOutcome(
        items_to_send=todo_items,
        warning=warning,
        should_resend_latest_snapshot=should_resend_latest_snapshot,
        final_extraction_ran=final_extraction_ran,
    )


@pytest.mark.asyncio
async def test_hosted_session_start_sends_started_message():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(start=AsyncMock())
    controller_factory = Mock(return_value=controller)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=controller_factory,
        settings=SimpleNamespace(),
    )

    await session.on_text(json.dumps({"type": "start"}))

    controller.start.assert_awaited_once_with(SimpleNamespace())
    assert browser_ws.json_messages == [{"type": "started"}]


@pytest.mark.asyncio
async def test_hosted_session_fixture_start_replays_saved_result_without_live_controller():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="unexpected live transcript",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
    )
    controller_factory = Mock(return_value=controller)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=controller_factory,
        settings=SimpleNamespace(),
    )

    await session.on_text(
        json.dumps({"type": "start", "fixture": "while-speaking-two-todos"})
    )
    await session.on_bytes(b"\x00\x01")
    await session.on_text(json.dumps({"type": "stop"}))

    controller_factory.assert_not_called()
    assert browser_ws.json_messages == [
        {"type": "started"},
        {
            "type": "todos",
            "items": [
                {
                    "text": "Buy oat milk",
                    "category": "Groceries",
                    "due_date": "2026-03-24",
                },
                {
                    "text": "Email Sarah the revised budget",
                    "category": "Work",
                },
            ],
        },
        {
            "type": "stopped",
            "transcript": (
                "By oat milk tonight. Zen email Sarah the revised budget."
            ),
        },
    ]
    assert browser_ws.close_calls == [(1000, "session finished")]


@pytest.mark.asyncio
async def test_hosted_session_unknown_control_message_returns_browser_error():
    browser_ws = _FakeBrowserSocket()
    controller_factory = Mock()
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=controller_factory,
        settings=SimpleNamespace(),
    )

    await session.on_text(json.dumps({"type": "bogus"}))

    controller_factory.assert_not_called()
    assert browser_ws.json_messages == [
        {"type": "error", "message": "Unknown control message"}
    ]


@pytest.mark.asyncio
async def test_hosted_session_start_builds_controller_with_hosted_factory(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(start=AsyncMock())
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    settings = SimpleNamespace(stt_provider="soniox")
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=settings,
    )

    await session.on_text(json.dumps({"type": "start"}))

    controller_cls.assert_called_once()
    controller_kwargs = controller_cls.call_args.kwargs
    assert controller_kwargs["create_stt_session"] is session_runtime.create_stt_session
    assert callable(controller_kwargs["on_update"])
    assert callable(controller_kwargs["on_error"])
    controller.start.assert_awaited_once_with(settings)
    assert browser_ws.json_messages == [{"type": "started"}]


@pytest.mark.asyncio
async def test_hosted_session_start_surfaces_unsupported_provider_error(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()

    class _Controller:
        def __init__(self, *, create_stt_session, on_update, on_error) -> None:
            self._create_stt_session = create_stt_session
            self.close = AsyncMock()

        async def start(self, settings) -> None:
            await self._create_stt_session(
                settings,
                connect_soniox_fn=AsyncMock(),
                connect_mistral_fn=AsyncMock(),
            )

    monkeypatch.setattr(session_runtime, "LiveSessionController", _Controller)
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key="mistral-test-key",
        stop_timeout_seconds=1.5,
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=settings,
    )

    await session.on_text(json.dumps({"type": "start"}))

    assert browser_ws.json_messages == [
        {
            "type": "error",
            "message": (
                "Hosted Mistral is deferred from the free-tier public "
                "Cloudflare bundle. Use STT_PROVIDER=soniox."
            ),
        }
    ]
    assert browser_ws.close_calls == [(1011, "provider failure")]


@pytest.mark.asyncio
async def test_hosted_session_binary_audio_frames_forward_to_controller():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        send_audio=AsyncMock(),
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=Mock(return_value=controller),
        settings=SimpleNamespace(),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_bytes(b"\x00\x01")

    controller.send_audio.assert_awaited_once_with(b"\x00\x01")


@pytest.mark.asyncio
async def test_hosted_session_relay_errors_return_browser_error(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), transcript=object())
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox"),
    )

    await session.on_text(json.dumps({"type": "start"}))

    on_error = controller_cls.call_args.kwargs["on_error"]
    await on_error(RuntimeError("boom"))

    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "error", "message": "boom"},
    ]
    assert browser_ws.close_calls == [(1011, "provider failure")]


@pytest.mark.asyncio
async def test_hosted_session_manual_stop_sends_terminal_message_once():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Stop the button.",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=Mock(return_value=controller),
        settings=SimpleNamespace(stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    controller.stop.assert_awaited_once_with(timeout_seconds=1.5)
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": []},
        {"type": "stopped", "transcript": "Stop the button."},
    ]
    assert browser_ws.close_calls == [(1000, "session finished")]


@pytest.mark.asyncio
async def test_hosted_session_sends_todos_during_recording(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), transcript=object())
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)

    def build_loop(*, send_fn, **kwargs):
        del kwargs
        loop = Mock()
        loop.cancel = Mock()
        loop.on_stop = AsyncMock()
        loop.on_transcript_changed = Mock()

        async def on_endpoint():
            from app.models import Todo

            await send_fn([Todo(text="Buy milk")])

        loop.on_endpoint = AsyncMock(side_effect=on_endpoint)
        return loop

    loop_cls = Mock(side_effect=build_loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox"),
    )

    await session.on_text(json.dumps({"type": "start"}))

    on_update = controller_cls.call_args.kwargs["on_update"]
    await on_update(
        SimpleNamespace(
            tokens=[{"text": "Buy milk. ", "is_final": True}],
            has_endpoint=True,
            transcript_changed=True,
        )
    )

    assert browser_ws.json_messages == [
        {"type": "started"},
        {
            "type": "transcript",
            "tokens": [{"text": "Buy milk. ", "is_final": True}],
        },
        {"type": "todos", "items": [{"text": "Buy milk"}]},
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_uses_finalized_transcript_for_final_pass_from_streaming_controller(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy milk tomorrow",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(items=[{"text": "Buy milk tomorrow"}])
    )
    loop_cls = Mock(return_value=loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    loop.on_stop.assert_awaited_once_with(
        final_transcript_text="Buy milk tomorrow",
        transcript_timed_out=False,
    )
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": [{"text": "Buy milk tomorrow"}]},
        {"type": "stopped", "transcript": "Buy milk tomorrow"},
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy milk tomorrow",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(
            items=[{"text": "Buy milk tomorrow"}],
            should_resend_latest_snapshot=True,
            final_extraction_ran=False,
        )
    )
    loop_cls = Mock(return_value=loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": [{"text": "Buy milk tomorrow"}]},
        {"type": "stopped", "transcript": "Buy milk tomorrow"},
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_surfaces_final_extraction_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy milk tomorrow",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(
            warning="Todo extraction failed.",
            should_resend_latest_snapshot=True,
            final_extraction_ran=True,
        )
    )
    loop_cls = Mock(return_value=loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": []},
        {
            "type": "stopped",
            "transcript": "Buy milk tomorrow",
            "warning": "Todo extraction failed.",
        },
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy milk tomorrow",
                timed_out=True,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(
            warning=(
                "Timed out waiting for the final transcript; "
                "todos were not extracted."
            ),
            should_resend_latest_snapshot=True,
            final_extraction_ran=False,
        )
    )
    loop_cls = Mock(return_value=loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    loop.on_stop.assert_awaited_once_with(
        final_transcript_text="Buy milk tomorrow",
        transcript_timed_out=True,
    )
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": []},
        {
            "type": "stopped",
            "transcript": "Buy milk tomorrow",
            "warning": (
                "Timed out waiting for the final transcript; "
                "todos were not extracted."
            ),
        },
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_sends_todos_before_stopped_from_streaming_controller(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy milk tomorrow",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(items=[{"text": "Buy milk tomorrow"}])
    )
    loop_cls = Mock(return_value=loop)
    monkeypatch.setattr(session_runtime, "ExtractionLoop", loop_cls, raising=False)
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": [{"text": "Buy milk tomorrow"}]},
        {"type": "stopped", "transcript": "Buy milk tomorrow"},
    ]


@pytest.mark.asyncio
async def test_hosted_session_streams_and_stops_with_final_done_text(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="By oat milk tonight. Zen email Sarah the revised budget.",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(return_value=_todo_stop_outcome())
    monkeypatch.setattr(
        session_runtime,
        "ExtractionLoop",
        Mock(return_value=loop),
        raising=False,
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    on_update = controller_cls.call_args.kwargs["on_update"]
    await on_update(
        SimpleNamespace(
            tokens=[{"text": "By oat milk tonight. ", "is_final": True}],
            has_endpoint=False,
            transcript_changed=True,
        )
    )
    await session.on_text(json.dumps({"type": "stop"}))

    assert browser_ws.json_messages == [
        {"type": "started"},
        {
            "type": "transcript",
            "tokens": [{"text": "By oat milk tonight. ", "is_final": True}],
        },
        {"type": "todos", "items": []},
        {
            "type": "stopped",
            "transcript": "By oat milk tonight. Zen email Sarah the revised budget.",
        },
    ]


@pytest.mark.asyncio
async def test_hosted_session_transcript_state_acceptance(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), transcript=object())
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    monkeypatch.setattr(
        session_runtime,
        "ExtractionLoop",
        Mock(return_value=loop),
        raising=False,
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox"),
    )

    await session.on_text(json.dumps({"type": "start"}))
    on_update = controller_cls.call_args.kwargs["on_update"]
    await on_update(
        SimpleNamespace(
            tokens=[{"text": "Buy oat milk", "is_final": True}],
            has_endpoint=False,
            transcript_changed=True,
        )
    )

    loop.on_transcript_changed.assert_called_once_with()
    loop.on_endpoint.assert_not_called()
    assert browser_ws.json_messages == [
        {"type": "started"},
        {
            "type": "transcript",
            "tokens": [{"text": "Buy oat milk", "is_final": True}],
        },
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_uses_finalized_transcript_for_final_pass(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy oat milk tonight",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(items=[{"text": "Buy oat milk tonight"}])
    )
    monkeypatch.setattr(
        session_runtime,
        "ExtractionLoop",
        Mock(return_value=loop),
        raising=False,
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    loop.on_stop.assert_awaited_once_with(
        final_transcript_text="Buy oat milk tonight",
        transcript_timed_out=False,
    )
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": [{"text": "Buy oat milk tonight"}]},
        {"type": "stopped", "transcript": "Buy oat milk tonight"},
    ]


@pytest.mark.asyncio
async def test_hosted_session_stop_sends_todos_before_stopped(
    monkeypatch: pytest.MonkeyPatch,
):
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Buy oat milk tonight",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
        transcript=object(),
    )
    controller_cls = Mock(return_value=controller)
    monkeypatch.setattr(session_runtime, "LiveSessionController", controller_cls)
    monkeypatch.setattr(session_runtime, "extract_todos", AsyncMock(), raising=False)
    monkeypatch.setattr(session_runtime, "TOKEN_THRESHOLD", 3, raising=False)
    loop = Mock()
    loop.cancel = Mock()
    loop.on_endpoint = AsyncMock()
    loop.on_transcript_changed = Mock()
    loop.on_stop = AsyncMock(
        return_value=_todo_stop_outcome(items=[{"text": "Buy oat milk tonight"}])
    )
    monkeypatch.setattr(
        session_runtime,
        "ExtractionLoop",
        Mock(return_value=loop),
        raising=False,
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        settings=SimpleNamespace(stt_provider="soniox", stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_text(json.dumps({"type": "stop"}))

    assert [message["type"] for message in browser_ws.json_messages] == [
        "started",
        "todos",
        "stopped",
    ]


@pytest.mark.asyncio
async def test_hosted_session_cap_expiry_sends_terminal_message_once():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(
            return_value=SimpleNamespace(
                transcript_text="Stop the button.",
                timed_out=False,
            )
        ),
        close=AsyncMock(),
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=Mock(return_value=controller),
        settings=SimpleNamespace(stop_timeout_seconds=1.5),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_cap_expiry()
    await session.on_cap_expiry()

    controller.stop.assert_awaited_once_with(timeout_seconds=1.5)
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "todos", "items": []},
        {"type": "stopped", "transcript": "Stop the button."},
    ]
    assert browser_ws.close_calls == [(1000, "session cap reached")]


@pytest.mark.asyncio
async def test_hosted_session_browser_disconnect_after_provider_failure_cleanup_is_idempotent():
    browser_ws = _FakeBrowserSocket()
    controller = SimpleNamespace(
        start=AsyncMock(),
        close=AsyncMock(),
    )
    session = HostedSessionActor(
        browser_ws=browser_ws,
        controller_factory=Mock(return_value=controller),
        settings=SimpleNamespace(),
    )

    await session.on_text(json.dumps({"type": "start"}))
    await session.on_provider_failure(RuntimeError("boom"))
    await session.close()

    controller.close.assert_awaited_once()
    assert browser_ws.json_messages == [
        {"type": "started"},
        {"type": "error", "message": "boom"},
    ]
    assert browser_ws.close_calls == [(1011, "provider failure")]


@pytest.mark.asyncio
async def test_session_runtime_duplicate_cap_paths_stop_only_once():
    storage = SimpleNamespace(setAlarm=Mock())
    ctx = SimpleNamespace(storage=storage)
    on_cap_expiry = AsyncMock()
    runtime = session_runtime.SessionRuntime(ctx, env=SimpleNamespace())
    runtime._session = SimpleNamespace(on_cap_expiry=on_cap_expiry)

    await asyncio.gather(runtime.alarm(), runtime.alarm())

    on_cap_expiry.assert_awaited_once()
