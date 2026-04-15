"""Record WebSocket sessions for replay testing.

Captures audio bytes, provider trace messages, and extraction results
so sessions can be replayed without a microphone or live STT connection.
"""

from __future__ import annotations

import json
import logging
import shutil
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_ROOT = Path(__file__).resolve().parent.parent.parent / "sessions"
RECENT_SESSIONS_DIR = SESSIONS_ROOT / "recent"
MAX_RECENT_SESSIONS = 10


class SessionRecorder:
    """Records a single WebSocket session to disk."""

    def __init__(self) -> None:
        self._dir: Path | None = None
        self._audio_file = None
        self._provider_trace_file = None
        self._provider_name = "soniox"
        self._stack: ExitStack | None = None

    def start(self, *, provider_name: str = "soniox") -> None:
        """Begin recording a new session."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        self._provider_name = provider_name
        self._dir = RECENT_SESSIONS_DIR / timestamp
        self._dir.mkdir(parents=True, exist_ok=True)

        self._stack = ExitStack()
        self._audio_file = self._stack.enter_context(
            (self._dir / "audio.pcm").open("wb")
        )
        self._provider_trace_file = self._stack.enter_context(
            (self._dir / f"{self._provider_name}.jsonl").open("w", encoding="utf-8")
        )

        logger.info("Recording session to %s", self._dir)

    def write_audio(self, data: bytes) -> None:
        """Record a chunk of audio data."""
        if self._audio_file:
            self._audio_file.write(data)

    def write_provider_message(self, message: str) -> None:
        """Record a raw provider trace event for the active session."""
        if self._provider_trace_file:
            self._provider_trace_file.write(message.rstrip("\n") + "\n")
            self._provider_trace_file.flush()

    def write_soniox_message(self, message: str) -> None:
        """Backward-compatible alias for older Soniox-only call sites."""
        self.write_provider_message(message)

    def write_result(self, transcript: str, todos: list[dict]) -> None:
        """Record the final extraction result."""
        if self._dir:
            result = {"transcript": transcript, "todos": todos}
            (self._dir / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False)
            )

    def stop(self) -> None:
        """Finish recording and close files."""
        if self._stack:
            self._stack.close()
            self._stack = None
        self._audio_file = None
        self._provider_trace_file = None

        if self._dir:
            logger.info("Session recorded: %s", self._dir)

        self._dir = None
        self._provider_name = "soniox"
        _prune_old_sessions()


def _prune_old_sessions() -> None:
    """Keep only the most recent sessions."""
    if not RECENT_SESSIONS_DIR.exists():
        return

    sessions = sorted(RECENT_SESSIONS_DIR.iterdir(), reverse=True)
    for old in sessions[MAX_RECENT_SESSIONS:]:
        if old.is_dir():
            shutil.rmtree(old)
            logger.info("Pruned old session: %s", old.name)
