#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

import modal
import modal.experimental

MINUTES = 60
PORT = 8000
REGION = "us-east"
GPU = "L40S"
MODEL_NAME = "Qwen/Qwen3.5-4B"
CONTEXT_LENGTH = 4096
STARTUP_TIMEOUT_SECONDS = 30 * MINUTES
SMOKE_TIMEOUT_SECONDS = 35 * MINUTES
SESSION_ID = "voice-todos-qwen4b-smoke"

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "backend" / "app" / "prompts" / "todo_extraction" / "v1.md"
CACHE_VOLUME = modal.Volume.from_name("voice-todos-sglang-cache", create_if_missing=True)
CACHE_PATH = "/cache"
HF_CACHE_PATH = f"{CACHE_PATH}/huggingface"
OUTLINES_WHITESPACE_PATTERN = os.environ.get(
    "VOICE_TODOS_OUTLINES_WHITESPACE_PATTERN", ""
)

SG_LANG_IMAGE = (
    modal.Image.from_registry("lmsysorg/sglang:v0.5.9-cu129-amd64-runtime")
    .entrypoint([])
    .pip_install("typing_extensions>=4.15.0")
    .env(
        {
            "HF_HUB_CACHE": HF_CACHE_PATH,
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VOICE_TODOS_OUTLINES_WHITESPACE_PATTERN": OUTLINES_WHITESPACE_PATTERN,
        }
    )
)

app = modal.App(name="voice-todos-qwen4b-sglang-outlines-smoke")


@dataclass
class SmokeSummary:
    endpoint_url: str
    model_name: str
    whitespace_pattern: str | None
    unconstrained_text: str
    constrained_raw: str
    constrained_has_newlines: bool
    constrained_has_tabs: bool
    constrained_max_space_run: int
    parsed_todos: list[dict[str, Any]]


def _todo_extraction_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "category": {"type": "string"},
                        "due_date": {"type": "string"},
                        "notification": {"type": "string"},
                        "assign_to": {"type": "string"},
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["todos"],
        "additionalProperties": False,
    }


def _read_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _build_extraction_input() -> str:
    reference_dt = datetime.now().astimezone()
    transcript = (
        "Tomorrow at 9am, email Alice the revised budget and remind me at the same time. "
        "Also ask Ben to review the onboarding checklist by Friday. "
        "Book the dentist appointment for next Tuesday afternoon. "
        "Mark the budget email as high priority and work-related. "
        "Don't create a task for 'the quarterly meeting was chaotic' because that's just commentary."
    )
    timezone_name = reference_dt.tzname() or "UTC"
    return "\n".join(
        [
            f"Current local datetime: {reference_dt.isoformat()}",
            f"Current local date: {reference_dt.date().isoformat()}",
            f"Current timezone: {timezone_name}",
            "",
            "Transcript:",
            transcript,
        ]
    )


def _json_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
    method: str = "POST",
    headers: dict[str, str] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def _wait_ready(process: subprocess.Popen[Any], *, timeout: int) -> None:
    deadline = time.time() + timeout
    health_url = f"http://127.0.0.1:{PORT}/health"
    while time.time() < deadline:
        if process.poll() is not None:
            raise subprocess.CalledProcessError(process.returncode or 1, process.args)
        try:
            request.urlopen(health_url, timeout=10).read()
            return
        except error.URLError:
            time.sleep(5)
        except TimeoutError:
            time.sleep(5)
    raise TimeoutError(f"SGLang server not ready within {timeout} seconds")


def _warmup_server() -> None:
    _json_request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        payload={
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "Reply with the single word READY."}],
            "temperature": 0,
            "max_tokens": 8,
        },
        timeout=60,
    )


def _extract_message_content(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"Missing choices in response: {response_json}")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError(f"Missing message in response: {response_json}")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"Missing text content in response: {response_json}")
    return content


def _validate_todo_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"Expected top-level object, got: {type(payload).__name__}")

    todos = payload.get("todos")
    if not isinstance(todos, list):
        raise ValueError(f"Expected todos list, got: {payload}")

    for index, todo in enumerate(todos, start=1):
        if not isinstance(todo, dict):
            raise ValueError(f"Todo #{index} is not an object: {todo!r}")
        text = todo.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Todo #{index} has invalid text: {todo!r}")
        priority = todo.get("priority")
        if priority is not None and priority not in {"high", "medium", "low"}:
            raise ValueError(f"Todo #{index} has invalid priority: {todo!r}")
    return todos


def _max_space_run(text: str) -> int:
    best = 0
    current = 0
    for char in text:
        if char == " ":
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _probe_chat_completion(
    base_url: str,
    *,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    url = f"{base_url}/v1/chat/completions"
    headers = {"Modal-Session-ID": SESSION_ID}
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = _json_request(url, payload=payload, timeout=120, headers=headers)
            if not isinstance(response, dict):
                raise ValueError(f"Unexpected response type: {type(response).__name__}")
            return response
        except error.HTTPError as exc:
            if exc.code == 503:
                last_error = exc
                time.sleep(2)
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            time.sleep(2)

    raise TimeoutError(
        f"No successful response from {url} within {timeout} seconds; "
        f"last_error={last_error!r}"
    )


@app.cls(
    image=SG_LANG_IMAGE,
    gpu=GPU,
    volumes={CACHE_PATH: CACHE_VOLUME},
    region=REGION,
    min_containers=0,
    startup_timeout=STARTUP_TIMEOUT_SECONDS,
)
@modal.experimental.http_server(
    port=PORT,
    proxy_regions=[REGION],
    exit_grace_period=15,
)
class SGLangServer:
    @modal.enter()
    def startup(self) -> None:
        cmd = [
            "python",
            "-m",
            "sglang.launch_server",
            "--model-path",
            MODEL_NAME,
            "--served-model-name",
            MODEL_NAME,
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--tp",
            "1",
            "--context-length",
            str(CONTEXT_LENGTH),
            "--download-dir",
            HF_CACHE_PATH,
            "--grammar-backend",
            "outlines",
            "--sampling-defaults",
            "openai",
            "--log-level-http",
            "warning",
        ]
        if OUTLINES_WHITESPACE_PATTERN:
            cmd.extend(
                [
                    "--constrained-json-whitespace-pattern",
                    OUTLINES_WHITESPACE_PATTERN,
                ]
            )

        self.process = subprocess.Popen(cmd)
        _wait_ready(self.process, timeout=STARTUP_TIMEOUT_SECONDS)
        _warmup_server()

    @modal.exit()
    def shutdown(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=30)


@app.local_entrypoint()
async def main(
    test_timeout: int = SMOKE_TIMEOUT_SECONDS,
) -> None:
    base_url = (await SGLangServer._experimental_get_flash_urls.aio())[0]

    unconstrained_response = await asyncio.to_thread(
        _probe_chat_completion,
        base_url,
        payload={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": _read_prompt()},
                {"role": "user", "content": _build_extraction_input()},
            ],
            "temperature": 0,
            "max_tokens": 512,
        },
        timeout=test_timeout,
    )
    unconstrained_text = _extract_message_content(unconstrained_response)

    constrained_response = await asyncio.to_thread(
        _probe_chat_completion,
        base_url,
        payload={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": _read_prompt()},
                {
                    "role": "user",
                    "content": (
                        _build_extraction_input()
                        + "\n\nReturn pretty-printed JSON with indentation and line breaks."
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "todo_extraction",
                    "schema": _todo_extraction_schema(),
                },
            },
        },
        timeout=test_timeout,
    )
    constrained_raw = _extract_message_content(constrained_response)
    constrained_payload = json.loads(constrained_raw)
    parsed_todos = _validate_todo_payload(constrained_payload)

    summary = SmokeSummary(
        endpoint_url=base_url,
        model_name=MODEL_NAME,
        whitespace_pattern=OUTLINES_WHITESPACE_PATTERN or None,
        unconstrained_text=unconstrained_text,
        constrained_raw=constrained_raw,
        constrained_has_newlines="\n" in constrained_raw,
        constrained_has_tabs="\t" in constrained_raw,
        constrained_max_space_run=_max_space_run(constrained_raw),
        parsed_todos=parsed_todos,
    )
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
