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

    async def send_json(self, payload: dict) -> None:
        self.json_messages.append(payload)


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
    controller = SimpleNamespace(start=AsyncMock())
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
