#!/usr/bin/env python3
"""Replay a recorded audio.pcm file through the backend WebSocket."""

import asyncio
import json
import sys

import websockets


WS_URL = "ws://localhost:8000/ws"
CHUNK_SIZE = 3200  # bytes (~0.1s of 16kHz 16-bit mono audio)
CHUNK_DELAY = 0.1  # seconds between chunks


async def main():
    if len(sys.argv) < 2:
        # Default to most recent session with audio
        import pathlib
        sessions_dir = pathlib.Path(__file__).parent.parent / "sessions" / "recent"
        candidates = sorted(
            [d for d in sessions_dir.iterdir() if (d / "audio.pcm").exists()
             and (d / "audio.pcm").stat().st_size > 0],
            reverse=True,
        )
        if not candidates:
            print("No sessions with audio found. Pass a session dir as argument.")
            sys.exit(1)
        audio_file = str(candidates[0] / "audio.pcm")
        print(f"Using latest session: {candidates[0].name}")
    else:
        audio_file = sys.argv[1]

    # Read the audio file
    with open(audio_file, "rb") as f:
        audio_data = f.read()

    total_chunks = (len(audio_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    duration_s = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit = 2 bytes/sample
    print(f"Audio file: {len(audio_data)} bytes, ~{duration_s:.1f}s, {total_chunks} chunks")

    messages_received = []
    transcript_tokens_final = []
    transcript_tokens_interim = []
    todos = []

    async with websockets.connect(WS_URL) as ws:
        # 1. Send start
        await ws.send(json.dumps({"type": "start"}))
        print("Sent: start")

        # 2. Wait for started
        msg = json.loads(await ws.recv())
        print(f"Received: {msg}")
        messages_received.append(msg)
        if msg.get("type") != "started":
            print(f"ERROR: Expected 'started', got {msg}")
            return

        # 3. Stream audio chunks
        print(f"Streaming {total_chunks} chunks...")
        for i in range(0, len(audio_data), CHUNK_SIZE):
            chunk = audio_data[i : i + CHUNK_SIZE]
            await ws.send(chunk)
            await asyncio.sleep(CHUNK_DELAY)

            # Drain any transcript messages that arrived
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.01)
                    msg = json.loads(raw)
                    messages_received.append(msg)
                    if msg.get("type") == "transcript":
                        for t in msg.get("tokens", []):
                            if t.get("is_final"):
                                transcript_tokens_final.append(t["text"])
                            else:
                                transcript_tokens_interim.append(t["text"])
                except (asyncio.TimeoutError, TimeoutError):
                    break

        print("All audio sent. Sending stop...")

        # 4. Send stop
        await ws.send(json.dumps({"type": "stop"}))

        # 5. Collect remaining messages until "stopped"
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                msg = json.loads(raw)
                messages_received.append(msg)

                if msg.get("type") == "transcript":
                    for t in msg.get("tokens", []):
                        if t.get("is_final"):
                            transcript_tokens_final.append(t["text"])
                        else:
                            transcript_tokens_interim.append(t["text"])
                elif msg.get("type") == "todos":
                    todos = msg.get("items", [])
                elif msg.get("type") == "stopped":
                    print("Received: stopped")
                    break
                elif msg.get("type") == "error":
                    print(f"ERROR from server: {msg.get('message')}")
                    break
            except (asyncio.TimeoutError, TimeoutError):
                print("TIMEOUT waiting for stopped message")
                break

    # Report
    transcript_count = sum(1 for m in messages_received if m.get("type") == "transcript")
    final_text = "".join(transcript_tokens_final)
    interim_text = "".join(transcript_tokens_interim)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total messages received: {len(messages_received)}")
    print(f"Transcript messages: {transcript_count}")
    print(f"\nFinal transcript ({len(transcript_tokens_final)} tokens):")
    print(f"  {final_text!r}")
    print(f"\nLast interim text ({len(transcript_tokens_interim)} tokens):")
    print(f"  {interim_text!r}")
    print(f"\nTodos extracted: {len(todos)}")
    for i, todo in enumerate(todos, 1):
        print(f"  {i}. {todo}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
