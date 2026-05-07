from __future__ import annotations

import asyncio
import hashlib
import json
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from app.backend_env import read_backend_env_var
from app.config import get_settings
from app.models import Priority, Todo

try:
    from workers import fetch as workers_fetch
except ModuleNotFoundError:  # pragma: no cover - unavailable in local pytest
    workers_fetch: Any | None = None

_GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model_name}:generateContent"
)
_DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {"thinking_level": "minimal"}
}
_HOSTED_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "todo_extraction" / "v1.md"
_HOSTED_PROMPT_CONTENT = """You extract actionable todo items from a voice transcript.

Rules:
- Extract only clearly actionable tasks, not observations or commentary.
- Write each todo as a clean, concise imperative sentence (not verbatim speech).
- Only set optional fields (priority, category, due_date, notification, assign_to) when the speaker clearly indicates them.
- priority: 'high' for urgent/important emphasis, 'medium' for moderate, 'low' for minor.
- due_date: extract dates/deadlines as ISO format (YYYY-MM-DD). Resolve relative dates (e.g., 'tomorrow', 'next Friday') relative to the current date.
- notification: extract reminder times as ISO datetime (YYYY-MM-DDTHH:MM:SS).
- assign_to: extract person names when the speaker delegates a task.
- category: infer a short category label only when the context is clear.
- If no actionable todos are found, return an empty list.

Incremental extraction rules:
- You may receive a list of previously extracted todos. Return the updated complete list.
- Preserve the order of existing todos where that order still makes sense. Append genuinely new todos at the end.
- If new speech adds details to an existing todo, update it in place.
- If later context shows an earlier todo was over-split, duplicated, misheard, or should be absorbed into another todo, merge or remove it.
- Explicit cancellation is one reason to remove a todo, but not the only one.
- If no previous todos are provided, extract from scratch.
"""
_TODO_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "todos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "text": {"type": "STRING"},
                    "priority": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "due_date": {"type": "STRING"},
                    "notification": {"type": "STRING"},
                    "assign_to": {"type": "STRING"},
                },
                "required": ["text"],
                "propertyOrdering": [
                    "text",
                    "priority",
                    "category",
                    "due_date",
                    "notification",
                    "assign_to",
                ],
            },
        }
    },
    "required": ["todos"],
    "propertyOrdering": ["todos"],
}


@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "gemini-3-flash-preview"
    provider: str | None = None
    model_settings: dict[str, Any] | None = None
    prompt_family: str = "todo_extraction"
    prompt_version: str = "v1"


@dataclass(frozen=True)
class PromptRef:
    family: str
    version: str
    path: Path
    content: str
    sha256: str


def get_extraction_prompt_ref(
    config: ExtractionConfig | None = None,
) -> PromptRef:
    resolved_config = config or ExtractionConfig()
    return PromptRef(
        family=resolved_config.prompt_family,
        version=resolved_config.prompt_version,
        path=_HOSTED_PROMPT_PATH,
        content=_HOSTED_PROMPT_CONTENT,
        sha256=hashlib.sha256(_HOSTED_PROMPT_CONTENT.encode("utf-8")).hexdigest(),
    )


def _resolve_model_settings(config: ExtractionConfig) -> dict[str, Any]:
    if config.model_settings is not None:
        return deepcopy(config.model_settings)
    return deepcopy(_DEFAULT_MODEL_SETTINGS)


def _get_gemini_api_key() -> str:
    gemini_api_key = read_backend_env_var("GEMINI_API_KEY")
    if gemini_api_key:
        return gemini_api_key
    return get_settings().gemini_api_key or ""


def _isoformat_optional(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _format_previous_todos(previous_todos: list[Todo]) -> str:
    lines: list[str] = []
    for index, todo in enumerate(previous_todos, start=1):
        parts = [todo.text]
        if todo.priority is not None:
            parts.append(f"priority: {todo.priority}")
        if todo.category is not None:
            parts.append(f"category: {todo.category}")
        if todo.due_date is not None:
            parts.append(f"due: {_isoformat_optional(todo.due_date)}")
        if todo.notification is not None:
            parts.append(f"notification: {_isoformat_optional(todo.notification)}")
        if todo.assign_to is not None:
            parts.append(f"assign to: {todo.assign_to}")
        text = parts[0]
        metadata = ", ".join(parts[1:])
        if metadata:
            lines.append(f"{index}. {text} ({metadata})")
        else:
            lines.append(f"{index}. {text}")
    return "\n".join(lines)


def _build_extraction_input(
    transcript: str,
    reference_dt: datetime,
    previous_todos: list[Todo] | None = None,
) -> str:
    timezone_name = reference_dt.tzname() or "UTC"
    sections = [
        f"Current local datetime: {reference_dt.isoformat()}",
        f"Current local date: {reference_dt.date().isoformat()}",
        f"Current timezone: {timezone_name}",
    ]

    if previous_todos:
        sections.extend(
            [
                "",
                "Previously extracted todos:",
                _format_previous_todos(previous_todos),
            ]
        )

    sections.extend(["", "Transcript:", transcript])
    return "\n".join(sections)


def _normalize_priority(value: Any) -> Priority | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"high", "medium", "low"}:
        return lowered
    return None


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _parse_todo_payload(raw_item: Any) -> Todo | None:
    if not isinstance(raw_item, dict):
        return None
    text = raw_item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return Todo(
        text=text.strip(),
        priority=_normalize_priority(raw_item.get("priority")),
        category=_normalize_optional_string(raw_item.get("category")),
        due_date=_normalize_optional_string(raw_item.get("due_date")),
        notification=_normalize_optional_string(raw_item.get("notification")),
        assign_to=_normalize_optional_string(raw_item.get("assign_to")),
    )


def _extract_text_part(response_payload: dict[str, Any]) -> str:
    candidates = response_payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini response did not include candidates")
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise RuntimeError("Gemini response did not include candidate content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("Gemini response did not include content parts")
    chunks = [
        part.get("text")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not chunks:
        raise RuntimeError("Gemini response did not include text output")
    return "".join(chunks)


async def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = json.dumps(payload)
    if workers_fetch is not None:
        response = await workers_fetch(
            url,
            method=cast("Any", "POST"),
            headers=headers,
            body=body,
        )
        response_text = await response.text()
        if response.status >= 400:
            raise RuntimeError(
                f"Gemini request failed with {response.status}: {response_text}"
            )
        return cast("dict[str, Any]", json.loads(response_text))

    def _urllib_post() -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return cast("dict[str, Any]", json.load(response))

    return await asyncio.to_thread(_urllib_post)


async def _run_gemini_extraction(
    *,
    transcript: str,
    previous_todos: list[Todo] | None,
    reference_dt: datetime,
    config: ExtractionConfig,
) -> list[Todo]:
    api_key = _get_gemini_api_key()
    if not api_key:
        raise ValueError("Gemini API key is required")

    prompt_ref = get_extraction_prompt_ref(config)
    request_payload = {
        "systemInstruction": {
            "parts": [{"text": prompt_ref.content}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": _build_extraction_input(
                            transcript,
                            reference_dt,
                            previous_todos,
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _TODO_RESPONSE_SCHEMA,
        },
    }

    thinking_level = (
        _resolve_model_settings(config)
        .get("google_thinking_config", {})
        .get("thinking_level")
    )
    if thinking_level is not None:
        request_payload["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": 0 if thinking_level == "minimal" else None
        }
        if request_payload["generationConfig"]["thinkingConfig"]["thinkingBudget"] is None:
            del request_payload["generationConfig"]["thinkingConfig"]

    response_payload = await _post_json(
        _GEMINI_API_URL.format(model_name=config.model_name),
        headers={
            "content-type": "application/json",
            "x-goog-api-key": api_key,
        },
        payload=request_payload,
    )
    raw_result = json.loads(_extract_text_part(response_payload))
    raw_todos = raw_result.get("todos", []) if isinstance(raw_result, dict) else []
    if not isinstance(raw_todos, list):
        raise RuntimeError("Gemini structured response did not contain a todo list")

    todos: list[Todo] = []
    for raw_item in raw_todos:
        todo = _parse_todo_payload(raw_item)
        if todo is not None:
            todos.append(todo)
    return todos


async def extract_todos(
    transcript: str,
    *,
    reference_dt: datetime | None = None,
    previous_todos: list[Todo] | None = None,
    config: ExtractionConfig | None = None,
) -> list[Todo]:
    if not transcript.strip():
        return []

    resolved_config = config or ExtractionConfig()
    resolved_reference_dt = reference_dt or datetime.now().astimezone()

    if resolved_config.provider not in {None, "google-gla"}:
        raise ValueError(
            f"Unsupported hosted extraction provider: {resolved_config.provider}"
        )

    return await _run_gemini_extraction(
        transcript=transcript,
        previous_todos=previous_todos,
        reference_dt=resolved_reference_dt,
        config=resolved_config,
    )
