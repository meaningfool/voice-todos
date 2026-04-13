from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


@dataclass(frozen=True, slots=True)
class SmokeResult:
    provider: str
    fixture: str
    transcript_message_count: int
    stopped_transcript: str
    warning: str | None
    extraction_call_count: int


def provider_api_key_env_var(provider: str) -> str:
    if provider == "mistral":
        return "MISTRAL_API_KEY"
    if provider == "soniox":
        return "SONIOX_API_KEY"
    raise ValueError(f"Unsupported STT provider: {provider}")


def resolve_fixture_audio_path(fixture_name: str) -> Path:
    path = FIXTURES_DIR / fixture_name / "audio.pcm"
    if not path.exists():
        raise FileNotFoundError(f"Fixture audio not found for {fixture_name}: {path}")
    return path


def build_smoke_settings(
    *,
    provider: str,
    api_key: str,
    stop_timeout_seconds: float = 30.0,
):
    return SimpleNamespace(
        stt_provider=provider,
        soniox_api_key=api_key if provider == "soniox" else "unused",
        mistral_api_key=api_key if provider == "mistral" else None,
        record_sessions=False,
        soniox_stop_timeout_seconds=stop_timeout_seconds,
    )


def run_ws_smoke(
    *,
    provider: str,
    fixture: str,
    audio_path: Path,
    api_key: str,
    chunk_bytes: int = 3200,
    chunk_delay_ms: int = 100,
    stop_timeout_seconds: float = 30.0,
) -> SmokeResult:
    settings = build_smoke_settings(
        provider=provider,
        api_key=api_key,
        stop_timeout_seconds=stop_timeout_seconds,
    )
    extract_todos = AsyncMock(return_value=[])
    data = audio_path.read_bytes()
    messages: list[dict] = []

    with (
        patch("app.ws.get_settings", return_value=settings),
        patch("app.ws.extract_todos", new=extract_todos),
        TestClient(app) as client,
        client.websocket_connect("/ws") as ws,
    ):
        ws.send_json({"type": "start"})
        started = ws.receive_json()
        if started != {"type": "started"}:
            raise ValueError(f"Unexpected start response: {started!r}")

        for i in range(0, len(data), chunk_bytes):
            ws.send_bytes(data[i : i + chunk_bytes])
            if chunk_delay_ms > 0:
                time.sleep(chunk_delay_ms / 1000)

        ws.send_json({"type": "stop"})
        while True:
            message = ws.receive_json()
            messages.append(message)
            if message.get("type") == "stopped":
                break

    stopped = next(
        (message for message in messages if message.get("type") == "stopped"),
        None,
    )
    if stopped is None:
        raise ValueError("No stopped message was received")

    return SmokeResult(
        provider=provider,
        fixture=fixture,
        transcript_message_count=sum(
            1 for message in messages if message.get("type") == "transcript"
        ),
        stopped_transcript=stopped.get("transcript", ""),
        warning=stopped.get("warning"),
        extraction_call_count=extract_todos.await_count,
    )


def validate_smoke_result(
    result: SmokeResult,
    *,
    allow_warning: bool = False,
) -> None:
    if result.transcript_message_count < 1:
        raise ValueError("No transcript messages were received")
    if not result.stopped_transcript.strip():
        raise ValueError("Final transcript was empty")
    if result.warning and not allow_warning:
        raise ValueError(f"Smoke run returned warning: {result.warning}")
