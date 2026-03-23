"""Integration test — sends recorded audio to the real Soniox API.

Verifies that finalize + empty frame produces the complete transcript.
Requires SONIOX_API_KEY in the environment. Skipped otherwise.

Uses the stop-the-button fixture: 2.6s of audio saying "Stop the button."
Without finalize, Soniox only returns "Stop". With finalize, the full
sentence comes back.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import websockets

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
CHUNK_SIZE = 3200  # ~0.1s at 16kHz 16-bit mono
CHUNK_DELAY = 0.1


def _get_api_key() -> str | None:
    try:
        from app.config import settings
        return settings.soniox_api_key
    except Exception:
        return None


def _has_api_key() -> bool:
    return bool(_get_api_key())


async def _transcribe(audio: bytes, api_key: str, *, use_finalize: bool) -> str:
    """Stream audio to Soniox and return the final transcript."""
    final_tokens: list[str] = []

    async with websockets.connect(SONIOX_WS_URL) as ws:
        await ws.send(json.dumps({
            "api_key": api_key,
            "model": "stt-rt-v4",
            "audio_format": "pcm_s16le",
            "sample_rate": 16000,
            "num_channels": 1,
        }))

        # Stream at realtime pace
        for i in range(0, len(audio), CHUNK_SIZE):
            await ws.send(audio[i : i + CHUNK_SIZE])
            await asyncio.sleep(CHUNK_DELAY)

        if use_finalize:
            await ws.send(json.dumps({"type": "finalize"}))
        await ws.send(b"")

        async for message in ws:
            event = json.loads(message)
            if event.get("finished"):
                break
            for t in event.get("tokens", []):
                if t.get("text") == "<fin>":
                    continue
                if t.get("is_final"):
                    final_tokens.append(t["text"])

    return "".join(final_tokens)


@pytest.mark.skipif(not _has_api_key(), reason="SONIOX_API_KEY not set")
class TestSonioxFinalize:
    """Tests that require the real Soniox API."""

    @pytest.fixture
    def audio(self) -> bytes:
        path = FIXTURES_DIR / "stop-the-button" / "audio.pcm"
        if not path.exists():
            pytest.skip("stop-the-button fixture not found")
        return path.read_bytes()

    @pytest.fixture
    def api_key(self) -> str:
        key = _get_api_key()
        assert key
        return key

    @pytest.mark.asyncio
    async def test_without_finalize_loses_tail(self, audio: bytes, api_key: str):
        """Without finalize, short utterances lose trailing words."""
        transcript = await _transcribe(audio, api_key, use_finalize=False)
        # Soniox only finalizes "Stop" — "the button." stays interim and is lost
        assert "button" not in transcript

    @pytest.mark.asyncio
    async def test_with_finalize_captures_full_sentence(self, audio: bytes, api_key: str):
        """With finalize, all pending tokens are promoted to final."""
        transcript = await _transcribe(audio, api_key, use_finalize=True)
        assert "Stop" in transcript
        assert "button" in transcript
