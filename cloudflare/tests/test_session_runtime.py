from __future__ import annotations

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
    controller = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
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
        {"type": "stopped", "transcript": "Stop the button."},
    ]
    assert browser_ws.close_calls == [(1000, "session finished")]


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
