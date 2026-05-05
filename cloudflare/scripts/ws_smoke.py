from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import websockets
from websockets.exceptions import ConnectionClosed


def _with_session(base_url: str, session_id: str) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query))
    query["session"] = session_id
    return urlunparse(parsed._replace(query=urlencode(query)))


def _print_event(prefix: str, payload) -> None:
    if isinstance(payload, (dict, list)):
        rendered = json.dumps(payload)
    else:
        rendered = str(payload)
    print(f"{prefix} {rendered}")


async def _expect_json(ws, *, timeout_seconds: float) -> dict[str, object]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
    if not isinstance(raw, str):
        raise RuntimeError(f"expected text websocket frame, got {type(raw).__name__}")
    payload = json.loads(raw)
    _print_event("server ->", payload)
    return payload


async def _run_transcript_stop(args) -> None:
    url = _with_session(args.base_url, args.session_id)
    transcript_messages = 0
    started_seen = False

    async with websockets.connect(url, max_size=None) as ws:
        start_payload = {"type": "start"}
        await ws.send(json.dumps(start_payload))
        _print_event("client ->", start_payload)

        while not started_seen:
            payload = await _expect_json(ws, timeout_seconds=5.0)
            if payload.get("type") == "started":
                started_seen = True
                break
            if payload.get("type") == "error":
                raise RuntimeError(f"server error before start: {payload['message']}")

        fixture = Path(args.fixture_path).read_bytes()
        for index in range(0, len(fixture), args.chunk_bytes):
            await ws.send(fixture[index : index + args.chunk_bytes])
            await asyncio.sleep(args.chunk_delay_ms / 1000)

        stop_payload = {"type": "stop"}
        await ws.send(json.dumps(stop_payload))
        _print_event("client ->", stop_payload)

        stopped_payload: dict[str, object] | None = None
        while stopped_payload is None:
            payload = await _expect_json(ws, timeout_seconds=20.0)
            if payload.get("type") == "transcript":
                transcript_messages += 1
            elif payload.get("type") == "error":
                raise RuntimeError(f"server error after stop: {payload['message']}")
            elif payload.get("type") == "stopped":
                stopped_payload = payload

    if args.expect_started and not started_seen:
        raise RuntimeError("expected started message")
    if transcript_messages < args.expect_transcript_min:
        raise RuntimeError(
            f"expected at least {args.expect_transcript_min} transcript messages, "
            f"saw {transcript_messages}"
        )
    if args.expect_final_transcript is not None:
        transcript = None if stopped_payload is None else stopped_payload.get("transcript")
        if transcript != args.expect_final_transcript:
            raise RuntimeError(
                f"expected final transcript {args.expect_final_transcript!r}, "
                f"got {transcript!r}"
            )


async def _run_cap_expiry(args) -> None:
    url = _with_session(args.base_url, args.session_id)
    terminal_payload: dict[str, object] | None = None
    close_code: int | None = None
    deadline = time.monotonic() + (args.hold_open_ms / 1000) + 10.0

    async with websockets.connect(url, max_size=None) as ws:
        start_payload = {"type": "start"}
        await ws.send(json.dumps(start_payload))
        _print_event("client ->", start_payload)

        while time.monotonic() < deadline:
            try:
                payload = await _expect_json(ws, timeout_seconds=1.0)
            except TimeoutError:
                continue
            except ConnectionClosed as exc:
                close_code = exc.code
                _print_event("socket closed", {"code": exc.code, "reason": exc.reason})
                break

            if payload.get("type") == args.expect_terminal_type:
                terminal_payload = payload

        if close_code is None:
            try:
                await asyncio.wait_for(ws.wait_closed(), timeout=5.0)
            except TimeoutError as exc:
                raise RuntimeError("socket did not close after cap-expiry window") from exc
            close_code = ws.close_code

    if terminal_payload is None:
        raise RuntimeError(f"expected terminal message {args.expect_terminal_type!r}")
    if args.expect_close_code is not None and close_code != args.expect_close_code:
        raise RuntimeError(
            f"expected close code {args.expect_close_code}, got {close_code}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hosted websocket smoke checks.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", required=True, choices=["transcript-stop", "cap-expiry"])
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--fixture-path")
    parser.add_argument("--chunk-bytes", type=int, default=3200)
    parser.add_argument("--chunk-delay-ms", type=int, default=100)
    parser.add_argument("--hold-open-ms", type=int, default=0)
    parser.add_argument("--expect-started", action="store_true")
    parser.add_argument("--expect-transcript-min", type=int, default=0)
    parser.add_argument("--expect-final-transcript")
    parser.add_argument("--expect-terminal-type", default="stopped")
    parser.add_argument("--expect-close-code", type=int)
    return parser


async def _main_async(args) -> None:
    if args.mode == "transcript-stop":
        if not args.fixture_path:
            raise RuntimeError("--fixture-path is required for transcript-stop mode")
        await _run_transcript_stop(args)
        return

    await _run_cap_expiry(args)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(_main_async(args))
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
