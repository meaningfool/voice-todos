from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
STARTUP_TIMEOUT_SECONDS = 35 * 60
SHUTDOWN_TIMEOUT_SECONDS = 30
MANAGED_API_KEY = "modal-managed-placeholder-key"


@dataclass(frozen=True)
class ManagedSessionLease:
    base_url: str
    api_key: str
    headers: dict[str, str]
    process: subprocess.Popen[str]


async def open_managed_session(*, resolved_config) -> ManagedSessionLease:
    managed_session = getattr(resolved_config, "managed_session", None)
    if managed_session is None:
        raise ValueError("Managed session config is required")
    if managed_session.stack != "sglang-outlines":
        raise ValueError(f"Unsupported managed stack: {managed_session.stack}")
    if managed_session.host != "modal":
        raise ValueError(f"Unsupported managed host: {managed_session.host}")

    session_id = f"benchmark-{uuid4().hex[:12]}"
    process = subprocess.Popen(
        [
            "modal",
            "run",
            "scripts/qwen_sglang_outlines_smoke.py",
            "--mode",
            "serve",
            "--model-name",
            resolved_config.model_name,
            "--context-length",
            str(managed_session.context_window),
            "--session-id",
            session_id,
            "--api-key",
            MANAGED_API_KEY,
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("Managed session launcher did not expose stdout")

    try:
        ready_payload = await asyncio.wait_for(
            asyncio.to_thread(_read_ready_payload, process),
            timeout=STARTUP_TIMEOUT_SECONDS,
        )
    except Exception:
        await _terminate_process(process)
        raise

    return ManagedSessionLease(
        base_url=ready_payload["base_url"],
        api_key=ready_payload["api_key"],
        headers=ready_payload["headers"],
        process=process,
    )


async def close_managed_session(lease: ManagedSessionLease) -> None:
    await _terminate_process(lease.process)


def _read_ready_payload(process: subprocess.Popen[str]) -> dict[str, Any]:
    assert process.stdout is not None
    recent_output: list[str] = []

    while True:
        line = process.stdout.readline()
        if line == "":
            exit_code = process.poll()
            output = "\n".join(recent_output[-10:])
            raise RuntimeError(
                "Managed session exited before announcing readiness "
                f"(code={exit_code}). Output:\n{output}"
            )

        stripped = line.strip()
        if stripped:
            recent_output.append(stripped)

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict) or payload.get("status") != "ready":
            continue

        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        headers = payload.get("headers")
        if not isinstance(base_url, str) or not base_url:
            raise ValueError(f"Invalid managed session base_url: {payload!r}")
        if not isinstance(api_key, str) or not api_key:
            raise ValueError(f"Invalid managed session api_key: {payload!r}")
        if not isinstance(headers, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            raise ValueError(f"Invalid managed session headers: {payload!r}")
        return {
            "base_url": base_url,
            "api_key": api_key,
            "headers": dict(headers),
        }


async def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        await asyncio.to_thread(process.wait, SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        await asyncio.to_thread(process.wait, SHUTDOWN_TIMEOUT_SECONDS)
