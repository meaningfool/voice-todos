"""Replay tests — feed recorded Soniox messages through the handler.

These tests use saved session data (soniox.jsonl) to verify transcript
accumulation and extraction without needing a microphone or Soniox API.

Test fixtures live in tests/fixtures/ and are copied from sessions/golden/
or sessions/recent/ when needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _accumulate_transcript(messages: list[dict]) -> tuple[str, str]:
    """Simulate the backend's transcript accumulation logic.

    Returns (final_text, interim_text) matching ws.py behavior.
    """
    final_parts: list[str] = []
    interim_parts: list[str] = []

    for event in messages:
        if event.get("finished"):
            break
        tokens = event.get("tokens", [])
        if tokens:
            for t in tokens:
                if t.get("is_final", False):
                    final_parts.append(t["text"])
            interim_text = "".join(
                t["text"] for t in tokens if not t.get("is_final", False)
            )
            if interim_text:
                interim_parts.clear()
                interim_parts.append(interim_text)

    final_text = "".join(final_parts)
    if not final_text.strip() and interim_parts:
        final_text = "".join(interim_parts)

    return final_text, "".join(interim_parts)


def has_fixtures() -> bool:
    """Check if any replay fixtures exist."""
    if not FIXTURES_DIR.exists():
        return False
    return any(
        (d / "soniox.jsonl").exists()
        for d in FIXTURES_DIR.iterdir()
        if d.is_dir()
    )


@pytest.mark.skipif(not has_fixtures(), reason="No replay fixtures available")
class TestReplay:
    """Tests that replay recorded Soniox sessions."""

    def _fixture_names(self) -> list[str]:
        """List available fixture directories."""
        if not FIXTURES_DIR.exists():
            return []
        return [
            d.name
            for d in sorted(FIXTURES_DIR.iterdir())
            if d.is_dir() and (d / "soniox.jsonl").exists()
        ]

    def test_transcript_not_empty(self):
        """Every recorded session should produce a non-empty transcript."""
        for name in self._fixture_names():
            messages = _load_soniox_messages(name)
            final_text, _ = _accumulate_transcript(messages)
            assert final_text.strip(), (
                f"Fixture {name}: transcript is empty after accumulation. "
                f"This means no final tokens AND no interim fallback."
            )

    def test_result_matches_transcript(self):
        """The saved result.json transcript should match what accumulation produces."""
        for name in self._fixture_names():
            result_path = FIXTURES_DIR / name / "result.json"
            if not result_path.exists():
                continue
            result = json.loads(result_path.read_text())
            messages = _load_soniox_messages(name)
            final_text, _ = _accumulate_transcript(messages)
            assert final_text.strip() == result["transcript"].strip(), (
                f"Fixture {name}: accumulated transcript doesn't match result.json"
            )
