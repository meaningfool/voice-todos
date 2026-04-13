#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real backend /ws STT smoke test for a configured provider."
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=("mistral", "soniox"),
        help="STT provider to validate through the backend websocket flow.",
    )
    parser.add_argument(
        "--fixture",
        required=True,
        help="Fixture directory under backend/tests/fixtures/.",
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
    parser.add_argument(
        "--allow-warning",
        action="store_true",
        help="Do not fail the smoke run if the backend returns a stop warning.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.backend_env import read_backend_env_var
    from app.stt_smoke import (
        provider_api_key_env_var,
        resolve_fixture_audio_path,
        run_ws_smoke,
        validate_smoke_result,
    )

    env_var = provider_api_key_env_var(args.provider)
    api_key = read_backend_env_var(env_var)
    if not api_key:
        print(f"Missing {env_var} in env or backend/.env", file=sys.stderr)
        return 1

    try:
        result = run_ws_smoke(
            provider=args.provider,
            fixture=args.fixture,
            audio_path=resolve_fixture_audio_path(args.fixture),
            api_key=api_key,
            chunk_bytes=args.chunk_bytes,
            chunk_delay_ms=args.chunk_delay_ms,
        )
        validate_smoke_result(result, allow_warning=args.allow_warning)
    except Exception as exc:
        print(f"Smoke failed: {exc}", file=sys.stderr)
        return 1

    print(f"provider={result.provider}")
    print(f"fixture={result.fixture}")
    print(f"transcript_messages={result.transcript_message_count}")
    print(f"stopped_transcript={result.stopped_transcript!r}")
    print(f"warning={result.warning!r}")
    print(f"extraction_calls={result.extraction_call_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
