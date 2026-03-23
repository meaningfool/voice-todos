#!/usr/bin/env python3
"""Send audio.pcm directly to Soniox and get the full transcript.

No backend involved — just raw PCM → Soniox → transcript.
This removes any stop-timing concerns.

Usage:
    cd backend && uv run python ../scripts/soniox_transcribe.py [path/to/audio.pcm]
"""

import asyncio
import json
import sys
from pathlib import Path

import websockets

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
CHUNK_SIZE = 3200  # ~0.1s of 16kHz 16-bit mono
CHUNK_DELAY = 0.1


async def main():
    # Resolve audio file
    if len(sys.argv) >= 2:
        pcm_path = Path(sys.argv[1])
    else:
        sessions_dir = Path(__file__).parent.parent / "sessions" / "recent"
        candidates = sorted(
            [d for d in sessions_dir.iterdir() if (d / "audio.pcm").exists()
             and (d / "audio.pcm").stat().st_size > 0],
            reverse=True,
        )
        if not candidates:
            print("No sessions with audio found.")
            sys.exit(1)
        pcm_path = candidates[0] / "audio.pcm"
        print(f"Using latest session: {candidates[0].name}")

    audio_data = pcm_path.read_bytes()
    duration_s = len(audio_data) / (16000 * 2)
    print(f"Audio: {len(audio_data)} bytes, ~{duration_s:.1f}s")

    # Load API key
    from app.config import settings
    api_key = settings.soniox_api_key

    final_tokens: list[str] = []
    interim_tokens: list[str] = []

    async with websockets.connect(SONIOX_WS_URL) as ws:
        # Send config
        config = {
            "api_key": api_key,
            "model": "stt-rt-v4",
            "audio_format": "pcm_s16le",
            "sample_rate": 16000,
            "num_channels": 1,
            "context": {
                "general": [
                    {
                        "key": "topic",
                        "value": "The user is dictating tasks and todos "
                        "into a voice-driven todo list application.",
                    },
                ],
            },
        }
        await ws.send(json.dumps(config))

        # Stream audio
        total_chunks = (len(audio_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
        print(f"Streaming {total_chunks} chunks...")

        async def send_audio():
            for i in range(0, len(audio_data), CHUNK_SIZE):
                chunk = audio_data[i : i + CHUNK_SIZE]
                await ws.send(chunk)
                await asyncio.sleep(CHUNK_DELAY)
            # Finalize pending tokens, then signal end of stream
            await ws.send(json.dumps({"type": "finalize"}))
            await ws.send(b"")
            print("All audio sent + finalize + empty frame.")

        async def receive_tokens():
            async for message in ws:
                event = json.loads(message)
                if event.get("finished"):
                    print("Soniox finished.")
                    return
                tokens = event.get("tokens", [])
                for t in tokens:
                    if t.get("is_final"):
                        final_tokens.append(t["text"])
                    else:
                        interim_tokens.append(t["text"])

        await asyncio.gather(send_audio(), receive_tokens())

    # Reconstruct last interim text (same logic as ws.py)
    # interim_tokens accumulates ALL interim tokens across all messages,
    # but we only want the last interim batch. Re-parse for that.
    # For simplicity, just show finals — Soniox should finalize everything
    # when given the full audio without interruption.
    final_text = "".join(final_tokens)

    print("\n" + "=" * 60)
    print("SONIOX DIRECT TRANSCRIPTION")
    print("=" * 60)
    print(f"Final tokens: {len(final_tokens)}")
    print(f"Final text: {final_text!r}")
    print(f"\nInterim tokens seen: {len(interim_tokens)}")
    if interim_tokens:
        # Show what the last interim batch contained
        print(f"All interim text (cumulative): {(''.join(interim_tokens))!r}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
