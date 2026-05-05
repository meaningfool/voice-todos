from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.session_runtime import HostedSessionActor


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
