from __future__ import annotations

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
