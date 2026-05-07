from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import stt_soniox_cf as stt_soniox_cf


class _FakeJsWebSocket:
    def __init__(self) -> None:
        self.accept_calls = 0
        self.listeners: list[tuple[str, object]] = []

    def accept(self) -> None:
        self.accept_calls += 1

    def addEventListener(self, event_name: str, handler: object) -> None:
        self.listeners.append((event_name, handler))

    def close(self) -> None:
        return None


class _FakeOutboundClient:
    def __init__(self, messages: list[str] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self._messages = list(messages or [])

    async def wait_until_open(self, timeout_seconds: float = 10.0) -> None:
        self.calls.append(("wait_until_open", timeout_seconds))

    def send_text(self, payload: str) -> None:
        self.calls.append(("send_text", payload))

    def send_binary(self, payload: bytes) -> None:
        self.calls.append(("send_binary", payload))

    async def close(self) -> None:
        self.calls.append(("close", None))

    async def _iterate(self):
        for message in self._messages:
            yield message

    def __aiter__(self):
        return self._iterate()


@pytest.mark.asyncio
async def test_cf_soniox_connect_uses_fetch_upgrade_websocket(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_ws = _FakeJsWebSocket()
    fetch_calls: list[tuple[str, dict[str, str]]] = []

    async def fake_fetch(url: str, *, headers: dict[str, str]):
        fetch_calls.append((url, headers))
        return SimpleNamespace(js_object=SimpleNamespace(webSocket=fake_ws))

    monkeypatch.setattr(stt_soniox_cf, "fetch", fake_fetch)
    monkeypatch.setattr(stt_soniox_cf, "create_proxy", lambda fn: fn)

    client = await stt_soniox_cf.OutboundWebSocketClient.connect(
        stt_soniox_cf.SONIOX_FETCH_URL
    )

    assert fetch_calls == [
        (stt_soniox_cf.SONIOX_FETCH_URL, {"Upgrade": "websocket"})
    ]
    assert fake_ws.accept_calls == 1
    assert client.ws is fake_ws


@pytest.mark.asyncio
async def test_cf_soniox_session_preserves_finalize_then_eos_calls():
    client = _FakeOutboundClient()
    session = stt_soniox_cf.CloudflareSonioxSession(client)

    await session.request_final_transcript()
    await session.end_stream()

    assert client.calls == [
        ("send_text", json.dumps({"type": "finalize"})),
        ("send_binary", b""),
    ]


@pytest.mark.asyncio
async def test_cf_soniox_session_sets_finalization_event_on_fin_token():
    client = _FakeOutboundClient(
        messages=[
            json.dumps(
                {
                    "tokens": [
                        {"text": "Stop ", "is_final": True},
                        {"text": "<fin>", "is_final": True},
                    ]
                }
            )
        ]
    )
    session = stt_soniox_cf.CloudflareSonioxSession(client)

    event = await anext(session.__aiter__())

    assert event.finalization_state.value == "observed"
    assert len(event.tokens) == 1
    assert event.tokens[0].text == "Stop "
    assert event.tokens[0].is_final is True
    await asyncio.wait_for(session.wait_for_final_transcript(), timeout=0.01)
