"""Opt-in end-to-end behavioral tests for the live voice todo pipeline.

These tests exercise the real FastAPI websocket endpoint, real Soniox, and real
Gemini against recorded fixture audio. They are intentionally secondary and
only run when explicitly enabled.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
import websockets
from app.backend_env import read_backend_env_var

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_BACKEND_WS_URL = "ws://localhost:8000/ws"
CHUNK_SIZE = 3200  # ~0.1s of 16kHz 16-bit mono PCM
CHUNK_DELAY_SECONDS = 0.1
CHUNK_DRAIN_TIMEOUT_SECONDS = 0.05
AFTER_AUDIO_COLLECTION_SECONDS = 5.0
AFTER_AUDIO_DRAIN_TIMEOUT_SECONDS = 0.25
# Live finalization can include Soniox finalize latency plus one or more
# Gemini extraction passes before the terminal `stopped` message arrives.
STOP_DRAIN_TIMEOUT_SECONDS = 60.0


def _e2e_enabled() -> bool:
    return bool(
        read_backend_env_var("SONIOX_API_KEY")
        and read_backend_env_var("GEMINI_API_KEY")
        and os.environ.get("RUN_E2E_INTEGRATION") == "1"
    )


pytestmark = pytest.mark.skipif(
    not _e2e_enabled(),
    reason=(
        "E2E integration tests require SONIOX_API_KEY, GEMINI_API_KEY, and "
        "RUN_E2E_INTEGRATION=1"
    ),
)


def _backend_ws_url() -> str:
    return os.environ.get("E2E_BACKEND_WS_URL", DEFAULT_BACKEND_WS_URL)


def _fixture_audio_path(fixture_name: str) -> Path:
    path = FIXTURES_DIR / fixture_name / "audio.pcm"
    if not path.exists():
        pytest.skip(f"Fixture {fixture_name} not found at {path}")
    return path


def _load_fixture_audio(fixture_name: str) -> bytes:
    return _fixture_audio_path(fixture_name).read_bytes()


def _parse_message(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


def _connect_backend(url: str | None = None):
    return websockets.connect(
        url or _backend_ws_url(),
        open_timeout=15,
        close_timeout=15,
        ping_interval=None,
    )


async def _drain_messages(ws, *, timeout: float) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        except TimeoutError:
            break
        messages.append(_parse_message(raw))
    return messages


async def _collect_messages_for(
    ws,
    *,
    total_duration: float,
    poll_timeout: float,
) -> list[dict[str, Any]]:
    deadline = asyncio.get_running_loop().time() + total_duration
    messages: list[dict[str, Any]] = []
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return messages
        messages.extend(
            await _drain_messages(ws, timeout=min(poll_timeout, remaining))
        )


async def _wait_for_started(ws) -> dict[str, Any]:
    while True:
        message = _parse_message(await asyncio.wait_for(ws.recv(), timeout=15.0))
        if message.get("type") == "started":
            return message
        if message.get("type") == "error":
            pytest.fail(f"Backend returned an error while starting: {message}")


async def _stream_audio_with_collection(
    ws,
    audio: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    during_audio: list[dict[str, Any]] = []
    after_audio_before_stop: list[dict[str, Any]] = []

    for offset in range(0, len(audio), CHUNK_SIZE):
        await ws.send(audio[offset : offset + CHUNK_SIZE])
        await asyncio.sleep(CHUNK_DELAY_SECONDS)
        during_audio.extend(
            await _drain_messages(ws, timeout=CHUNK_DRAIN_TIMEOUT_SECONDS)
        )

    after_audio_before_stop.extend(
        await _collect_messages_for(
            ws,
            total_duration=AFTER_AUDIO_COLLECTION_SECONDS,
            poll_timeout=AFTER_AUDIO_DRAIN_TIMEOUT_SECONDS,
        )
    )
    return during_audio, after_audio_before_stop


@dataclass(slots=True)
class E2ETranscript:
    during_audio: list[dict[str, Any]]
    after_audio_before_stop: list[dict[str, Any]]
    after_stop: list[dict[str, Any]]


async def _run_session(
    fixture_name: str,
    *,
    backend_ws_url: str | None = None,
) -> E2ETranscript:
    audio = _load_fixture_audio(fixture_name)
    async with _connect_backend(backend_ws_url) as ws:
        await ws.send(json.dumps({"type": "start"}))
        await _wait_for_started(ws)

        during_audio, after_audio_before_stop = await _stream_audio_with_collection(
            ws, audio
        )

        await ws.send(json.dumps({"type": "stop"}))

        after_stop: list[dict[str, Any]] = []
        while True:
            message = _parse_message(
                await asyncio.wait_for(ws.recv(), timeout=STOP_DRAIN_TIMEOUT_SECONDS)
            )
            after_stop.append(message)
            if message.get("type") == "stopped":
                break
            if message.get("type") == "error":
                pytest.fail(f"Backend returned an error after stop: {message}")

    return E2ETranscript(
        during_audio=during_audio,
        after_audio_before_stop=after_audio_before_stop,
        after_stop=after_stop,
    )


def _todos_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [message for message in messages if message.get("type") == "todos"]


def _todo_texts(message: dict[str, Any]) -> list[str]:
    return [item["text"] for item in message.get("items", []) if "text" in item]


@pytest.mark.asyncio
async def test_while_speaking_two_todos_during_audio_and_final_capture():
    """Behaviors 1+2: todos appear during audio and final capture includes both."""
    replay = await _run_session("while-speaking-two-todos")

    assert _todos_messages(replay.during_audio), (
        "Expected at least one todos message while audio was still streaming. "
        f"Messages during audio: {[m['type'] for m in replay.during_audio]}"
    )

    all_todo_messages = (
        _todos_messages(replay.during_audio)
        + _todos_messages(replay.after_audio_before_stop)
        + _todos_messages(replay.after_stop)
    )
    assert all_todo_messages, "Expected at least one todos message in the session"

    final_todos = all_todo_messages[-1]["items"]
    final_texts = " ".join(
        item["text"].lower() for item in final_todos if "text" in item
    )

    assert "oat" in final_texts and "milk" in final_texts, (
        f"Missing 'oat milk' in final todos: {final_texts}"
    )
    assert "email" in final_texts and "sarah" in final_texts, (
        f"Missing 'email Sarah' in final todos: {final_texts}"
    )
    assert "budget" in final_texts, (
        f"Missing 'revised budget' in final todos: {final_texts}"
    )


@pytest.mark.asyncio
async def test_stop_final_sweep_single_todo_sends_todos_before_stopped():
    """Behavior 5: stop produces a todos message before the terminal stopped."""
    replay = await _run_session("stop-final-sweep-single-todo")

    after_stop_types = [message["type"] for message in replay.after_stop]
    assert "todos" in after_stop_types, (
        f"Expected todos after stop. Messages after stop: {after_stop_types}"
    )
    assert after_stop_types.index("todos") < after_stop_types.index("stopped")

    final_after_stop_todos = _todos_messages(replay.after_stop)[-1]["items"]
    final_texts = " ".join(
        item["text"].lower() for item in final_after_stop_todos if "text" in item
    )
    assert "priya" in final_texts, (
        f"Missing 'Priya' in after-stop todos: {final_texts}"
    )
    assert "signed contract" in final_texts, (
        f"Missing 'signed contract' in after-stop todos: {final_texts}"
    )


@pytest.mark.asyncio
async def test_later_speech_can_refine_earlier_todos_refine_todo():
    """Behavior 3: Later speech can refine an earlier todo."""
    audio_path = FIXTURES_DIR / "refine-todo" / "audio.pcm"
    if not audio_path.exists():
        pytest.skip(f"Fixture refine-todo not found at {audio_path}")

    replay = await _run_session("refine-todo")

    todo_messages = _todos_messages(
        replay.during_audio + replay.after_audio_before_stop
    )
    if len(todo_messages) < 2:
        pytest.skip("Need at least 2 todo messages to observe refinement")

    snapshots = [_todo_texts(message) for message in todo_messages]
    assert any(first != second for first, second in pairwise(snapshots)), (
        f"Expected todo refinement. Snapshots: {snapshots}"
    )


@pytest.mark.asyncio
async def test_token_threshold_fallback_works_continuous_speech():
    """Behavior 6: Todos appear during long speech even without endpoint pauses."""
    audio_path = FIXTURES_DIR / "continuous-speech" / "audio.pcm"
    if not audio_path.exists():
        pytest.skip(f"Fixture continuous-speech not found at {audio_path}")

    replay = await _run_session("continuous-speech")

    todo_messages_before_stop = _todos_messages(
        replay.during_audio + replay.after_audio_before_stop
    )
    before_stop_messages = replay.during_audio + replay.after_audio_before_stop
    message_types = [m["type"] for m in before_stop_messages]
    assert todo_messages_before_stop, (
        "Expected todos from token-threshold fallback. "
        f"Messages before stop: {message_types}"
    )
