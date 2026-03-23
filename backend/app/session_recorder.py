"""Record WebSocket sessions for replay testing.

Captures audio bytes, Soniox messages, and extraction results
so sessions can be replayed without a microphone or Soniox connection.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "sessions" / "recent"
MAX_RECENT_SESSIONS = 10


class SessionRecorder:
    """Records a single WebSocket session to disk."""

    def __init__(self) -> None:
        self._dir: Path | None = None
        self._audio_file = None
        self._soniox_file = None

    def start(self) -> None:
        """Begin recording a new session."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        self._dir = SESSIONS_DIR / timestamp
        self._dir.mkdir(parents=True, exist_ok=True)

        self._audio_file = open(self._dir / "audio.pcm", "wb")
        self._soniox_file = open(self._dir / "soniox.jsonl", "w")

        logger.info("Recording session to %s", self._dir)

    def write_audio(self, data: bytes) -> None:
        """Record a chunk of audio data."""
        if self._audio_file:
            self._audio_file.write(data)

    def write_soniox_message(self, message: str) -> None:
        """Record a raw Soniox WebSocket message."""
        if self._soniox_file:
            self._soniox_file.write(message.rstrip("\n") + "\n")
            self._soniox_file.flush()

    def write_result(self, transcript: str, todos: list[dict]) -> None:
        """Record the final extraction result."""
        if self._dir:
            result = {"transcript": transcript, "todos": todos}
            (self._dir / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False)
            )

    def stop(self) -> None:
        """Finish recording and close files."""
        if self._audio_file:
            self._audio_file.close()
            self._audio_file = None
        if self._soniox_file:
            self._soniox_file.close()
            self._soniox_file = None

        if self._dir:
            logger.info("Session recorded: %s", self._dir)

        self._dir = None
        _prune_old_sessions()


def _prune_old_sessions() -> None:
    """Keep only the most recent sessions."""
    if not SESSIONS_DIR.exists():
        return

    sessions = sorted(SESSIONS_DIR.iterdir(), reverse=True)
    for old in sessions[MAX_RECENT_SESSIONS:]:
        if old.is_dir():
            shutil.rmtree(old)
            logger.info("Pruned old session: %s", old.name)
