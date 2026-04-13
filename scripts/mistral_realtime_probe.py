#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mistralai import Mistral, models


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream fixture audio to Voxtral realtime and record raw traces."
    )
    parser.add_argument(
        "--fixture",
        required=True,
        help="Fixture directory under backend/tests/fixtures/",
    )
    parser.add_argument(
        "--model",
        default="voxtral-mini-transcribe-realtime-2602",
        help="Realtime transcription model name.",
    )
    parser.add_argument(
        "--output-path",
        help="Optional JSONL output path. Defaults to the fixture mistral trace path.",
    )
    parser.add_argument(
        "--chunk-bytes",
        type=int,
        default=3200,
        help="PCM bytes per audio chunk. Defaults to ~100ms at 16kHz mono s16le.",
    )
    parser.add_argument(
        "--chunk-delay-ms",
        type=int,
        default=100,
        help="Delay between chunks to approximate realtime streaming.",
    )
    return parser.parse_args()


async def _iter_fixture_audio(
    audio_path: Path,
    *,
    chunk_bytes: int,
    chunk_delay_ms: int,
):
    audio_data = audio_path.read_bytes()
    delay_s = chunk_delay_ms / 1000
    for i in range(0, len(audio_data), chunk_bytes):
        yield audio_data[i : i + chunk_bytes]
        if delay_s > 0:
            await asyncio.sleep(delay_s)


async def _provider_events(
    *,
    api_key: str,
    model: str,
    audio_path: Path,
    chunk_bytes: int,
    chunk_delay_ms: int,
):
    client = Mistral(api_key=api_key)
    connection = await client.audio.realtime.connect(
        model=model,
        audio_format=models.AudioFormat(encoding="pcm_s16le", sample_rate=16000),
    )
    try:
        async def _send_audio() -> None:
            async for chunk in _iter_fixture_audio(
                audio_path,
                chunk_bytes=chunk_bytes,
                chunk_delay_ms=chunk_delay_ms,
            ):
                await connection.send_audio(chunk)
            await connection.flush_audio()
            await connection.end_audio()

        send_task = asyncio.create_task(_send_audio())
        try:
            async for event in connection.events():
                yield event
        finally:
            await send_task
    finally:
        await connection.close()


async def main() -> int:
    args = _parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.backend_env import read_backend_env_var
    from app.stt_mistral_probe import (
        default_trace_output_path,
        record_probe_run,
        resolve_fixture_audio_path,
    )

    api_key = read_backend_env_var("MISTRAL_API_KEY")
    if not api_key:
        print("Missing MISTRAL_API_KEY in env or backend/.env", file=sys.stderr)
        return 1

    audio_path = resolve_fixture_audio_path(args.fixture)
    output_path = (
        Path(args.output_path)
        if args.output_path
        else default_trace_output_path(args.fixture)
    )

    summary = await record_probe_run(
        fixture=args.fixture,
        model=args.model,
        output_path=output_path,
        event_stream=_provider_events(
            api_key=api_key,
            model=args.model,
            audio_path=audio_path,
            chunk_bytes=args.chunk_bytes,
            chunk_delay_ms=args.chunk_delay_ms,
        ),
    )

    print(f"Trace written to {output_path}")
    print(f"last_delta_text={summary.last_delta_text!r}")
    print(f"streaming_text={summary.streaming_text!r}")
    print(f"done_text={summary.done_text!r}")
    print(
        "done_differs_from_streaming_text="
        f"{summary.done_differs_from_streaming_text}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
