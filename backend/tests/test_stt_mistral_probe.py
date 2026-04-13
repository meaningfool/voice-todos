from __future__ import annotations

import json

import pytest

from app.stt_mistral_probe import (
    FIXTURES_DIR,
    build_trace_record,
    default_trace_output_path,
    record_probe_run,
    resolve_fixture_audio_path,
    summarize_stop_semantics,
)


def test_resolve_fixture_audio_path_points_to_audio_pcm():
    path = resolve_fixture_audio_path("stop-the-button")

    assert path == FIXTURES_DIR / "stop-the-button" / "audio.pcm"
    assert path.exists() is True


def test_default_trace_path_points_into_fixture_mistral_dir():
    path = default_trace_output_path("continuous-speech")

    assert path == FIXTURES_DIR / "continuous-speech" / "mistral" / "trace.jsonl"


def test_build_trace_record_preserves_raw_payload_and_event_type():
    payload = {"type": "transcription.text.delta", "text": "Buy milk"}

    record = build_trace_record(
        elapsed_ms=125,
        event_type="transcription.text.delta",
        payload=payload,
        fixture="stop-the-button",
        model="voxtral-mini-transcribe-realtime-2602",
    )

    assert record == {
        "elapsed_ms": 125,
        "event_type": "transcription.text.delta",
        "fixture": "stop-the-button",
        "model": "voxtral-mini-transcribe-realtime-2602",
        "payload": payload,
    }


def test_summarize_stop_semantics_compares_last_delta_and_done_text():
    summary = summarize_stop_semantics(
        [
            {"type": "transcription.text.delta", "text": "Buy milk"},
            {"type": "transcription.text.delta", "text": " tomorrow"},
            {"type": "transcription.done", "text": "Buy milk tomorrow"},
        ]
    )

    assert summary.last_delta_text == " tomorrow"
    assert summary.streaming_text == "Buy milk tomorrow"
    assert summary.done_text == "Buy milk tomorrow"
    assert summary.done_differs_from_last_delta is True
    assert summary.done_differs_from_streaming_text is False


def test_resolve_fixture_audio_path_raises_for_missing_fixture():
    with pytest.raises(FileNotFoundError, match="does-not-exist"):
        resolve_fixture_audio_path("does-not-exist")


@pytest.mark.asyncio
async def test_record_probe_run_writes_trace_and_returns_stop_summary(tmp_path):
    async def fake_events():
        yield {"type": "transcription.text.delta", "text": "Buy milk"}
        yield {
            "type": "transcription.segment",
            "text": "Buy milk",
            "start": 0.0,
            "end": 0.8,
        }
        yield {"type": "transcription.done", "text": "Buy milk tomorrow"}

    output_path = tmp_path / "trace.jsonl"

    summary = await record_probe_run(
        fixture="stop-the-button",
        model="voxtral-mini-transcribe-realtime-2602",
        output_path=output_path,
        event_stream=fake_events(),
    )

    lines = [json.loads(line) for line in output_path.read_text().splitlines()]

    assert [line["event_type"] for line in lines] == [
        "transcription.text.delta",
        "transcription.segment",
        "transcription.done",
    ]
    assert summary.streaming_text == "Buy milk"
    assert summary.done_text == "Buy milk tomorrow"
    assert summary.done_differs_from_streaming_text is True
