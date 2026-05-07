from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_ws_smoke_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ws_smoke.py"
    spec = importlib.util.spec_from_file_location("ws_smoke", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent_messages: list[object] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, payload):
        self.sent_messages.append(payload)

    async def recv(self):
        if not self._messages:
            raise RuntimeError("no more websocket messages")
        return self._messages.pop(0)


@pytest.mark.asyncio
async def test_todo_stop_mode_counts_transcripts_and_todos(tmp_path, monkeypatch):
    ws_smoke = _load_ws_smoke_module()
    fixture_path = tmp_path / "audio.pcm"
    fixture_path.write_bytes(b"\x00" * 6400)
    fake_ws = _FakeWebSocket(
        [
            json.dumps({"type": "started"}),
            json.dumps(
                {
                    "type": "transcript",
                    "tokens": [{"text": "Buy milk. ", "is_final": True}],
                }
            ),
            json.dumps({"type": "todos", "items": [{"text": "Buy milk"}]}),
            json.dumps({"type": "stopped", "transcript": "Buy milk. "}),
        ]
    )
    monkeypatch.setattr(
        ws_smoke.websockets,
        "connect",
        lambda *args, **kwargs: fake_ws,
    )

    args = SimpleNamespace(
        base_url="ws://127.0.0.1:8788/ws",
        session_id="todo-stop-test",
        fixture_path=str(fixture_path),
        chunk_bytes=3200,
        chunk_delay_ms=0,
        expect_started=True,
        expect_transcript_min=1,
        expect_todos_min=1,
        expect_terminal_type="stopped",
    )

    await ws_smoke._run_todo_stop(args)

    assert fake_ws.sent_messages[0] == json.dumps({"type": "start"})
    assert fake_ws.sent_messages[-1] == json.dumps({"type": "stop"})


@pytest.mark.asyncio
async def test_todo_stop_mode_rejects_stopped_before_todos(tmp_path, monkeypatch):
    ws_smoke = _load_ws_smoke_module()
    fixture_path = tmp_path / "audio.pcm"
    fixture_path.write_bytes(b"\x00" * 3200)
    fake_ws = _FakeWebSocket(
        [
            json.dumps({"type": "started"}),
            json.dumps({"type": "stopped", "transcript": "Buy milk. "}),
        ]
    )
    monkeypatch.setattr(
        ws_smoke.websockets,
        "connect",
        lambda *args, **kwargs: fake_ws,
    )

    args = SimpleNamespace(
        base_url="ws://127.0.0.1:8788/ws",
        session_id="todo-stop-ordering",
        fixture_path=str(fixture_path),
        chunk_bytes=3200,
        chunk_delay_ms=0,
        expect_started=True,
        expect_transcript_min=0,
        expect_todos_min=1,
        expect_terminal_type="stopped",
    )

    with pytest.raises(RuntimeError, match="expected at least 1 todos messages"):
        await ws_smoke._run_todo_stop(args)
