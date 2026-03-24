"""Replay tests — feed recorded Soniox messages through accumulation logic.

These tests use saved session data (soniox.jsonl) to verify transcript
accumulation without needing a microphone or Soniox API.

Test fixtures live in tests/fixtures/ and are copied from sessions/recent/
when needed. Each fixture has: audio.pcm, soniox.jsonl, result.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.transcript_accumulator import TranscriptAccumulator

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_soniox_messages(fixture_name: str) -> list[dict]:
    """Load recorded Soniox messages from a fixture."""
    path = FIXTURES_DIR / fixture_name / "soniox.jsonl"
    if not path.exists():
        pytest.skip(f"Fixture {fixture_name} not found at {path}")
    messages = []
    for line in path.read_text().splitlines():
        if line.strip():
            messages.append(json.loads(line))
    return messages


def _accumulate_transcript(messages: list[dict]) -> str:
    """Run recorded Soniox messages through the production accumulator."""
    accumulator = TranscriptAccumulator()
    for event in messages:
        if event.get("finished"):
            break
        accumulator.apply_event(event)
    return accumulator.full_text


def _fixture_names() -> list[str]:
    """List available fixture directories that have soniox.jsonl."""
    if not FIXTURES_DIR.exists():
        return []
    return [
        d.name
        for d in sorted(FIXTURES_DIR.iterdir())
        if d.is_dir() and (d / "soniox.jsonl").exists()
    ]


def has_fixtures() -> bool:
    return bool(_fixture_names())


@pytest.mark.skipif(not has_fixtures(), reason="No replay fixtures available")
class TestReplay:
    """Replay recorded Soniox sessions through accumulation logic."""

    def test_transcript_not_empty(self):
        """Every recorded session should produce a non-empty transcript."""
        for name in _fixture_names():
            messages = _load_soniox_messages(name)
            transcript = _accumulate_transcript(messages)
            assert transcript.strip(), (
                f"Fixture {name}: transcript is empty after accumulation"
            )

    def test_result_matches_transcript(self):
        """Accumulated transcript matches the saved result.json for each fixture."""
        for name in _fixture_names():
            result_path = FIXTURES_DIR / name / "result.json"
            if not result_path.exists():
                continue
            result = json.loads(result_path.read_text())
            messages = _load_soniox_messages(name)
            transcript = _accumulate_transcript(messages)
            assert transcript.strip() == result["transcript"].strip(), (
                f"Fixture {name}: accumulated transcript doesn't match result.json\n"
                f"  Accumulated: {transcript!r}\n"
                f"  result.json: {result['transcript']!r}"
            )
