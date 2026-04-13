from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


@dataclass(frozen=True, slots=True)
class StopSemanticsSummary:
    last_delta_text: str
    streaming_text: str
    done_text: str | None
    done_differs_from_last_delta: bool
    done_differs_from_streaming_text: bool


def resolve_fixture_audio_path(fixture_name: str) -> Path:
    path = FIXTURES_DIR / fixture_name / "audio.pcm"
    if not path.exists():
        raise FileNotFoundError(f"Fixture audio not found for {fixture_name}: {path}")
    return path


def default_trace_output_path(fixture_name: str) -> Path:
    return FIXTURES_DIR / fixture_name / "mistral" / "trace.jsonl"


def build_trace_record(
    *,
    elapsed_ms: int,
    event_type: str,
    payload: dict[str, Any],
    fixture: str,
    model: str,
) -> dict[str, Any]:
    return {
        "elapsed_ms": elapsed_ms,
        "event_type": event_type,
        "fixture": fixture,
        "model": model,
        "payload": payload,
    }


def summarize_stop_semantics(events: list[dict[str, Any]]) -> StopSemanticsSummary:
    delta_parts: list[str] = []
    last_delta_text = ""
    done_text: str | None = None

    for event in events:
        event_type = event.get("type")
        text = event.get("text")
        if not isinstance(text, str):
            continue
        if event_type == "transcription.text.delta":
            delta_parts.append(text)
            last_delta_text = text
        elif event_type == "transcription.done":
            done_text = text

    streaming_text = "".join(delta_parts)

    return StopSemanticsSummary(
        last_delta_text=last_delta_text,
        streaming_text=streaming_text,
        done_text=done_text,
        done_differs_from_last_delta=done_text != last_delta_text,
        done_differs_from_streaming_text=done_text != streaming_text,
    )


def serialize_realtime_event(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return dict(event)

    model_dump = getattr(event, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", by_alias=True, exclude_none=True)

    payload = dict(getattr(event, "__dict__", {}))
    event_type = getattr(event, "type", None)
    if isinstance(event_type, str):
        payload.setdefault("type", event_type)
    return payload


async def record_probe_run(
    *,
    fixture: str,
    model: str,
    output_path: Path,
    event_stream: AsyncIterator[dict[str, Any] | Any],
) -> StopSemanticsSummary:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []

    with output_path.open("w", encoding="utf-8") as handle:
        elapsed_ms = 0
        async for raw_event in event_stream:
            payload = serialize_realtime_event(raw_event)
            event_type = payload.get("type")
            if not isinstance(event_type, str):
                event_type = "unknown"
            record = build_trace_record(
                elapsed_ms=elapsed_ms,
                event_type=event_type,
                payload=payload,
                fixture=fixture,
                model=model,
            )
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            events.append(payload)
            elapsed_ms += 1

    return summarize_stop_semantics(events)
