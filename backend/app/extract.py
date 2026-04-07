from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from app.config import get_settings
from app.model_providers import (
    GoogleModel as _GoogleModel,
)
from app.model_providers import (
    GoogleProvider as _GoogleProvider,
)
from app.model_providers import (
    build_model,
)
from app.models import ExtractionResult, Todo
from app.prompts.registry import PromptRef
from app.prompts.registry import get_prompt_ref as _load_prompt_ref

GoogleModel = _GoogleModel
GoogleProvider = _GoogleProvider


@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "gemini-3-flash-preview"
    provider: str | None = None
    model_settings: dict[str, Any] | None = None
    prompt_family: str = "todo_extraction"
    prompt_version: str = "v1"


_DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {"thinking_level": "minimal"}
}

_agent_cache: dict[tuple[Any, ...], Agent[None, ExtractionResult]] = {}
_BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _freeze_for_cache(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(
            sorted((key, _freeze_for_cache(inner)) for key, inner in value.items())
        )
    if isinstance(value, list):
        return tuple(_freeze_for_cache(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_for_cache(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_for_cache(item) for item in value))
    return value


def _config_cache_key(
    config: ExtractionConfig,
    *,
    prompt_sha256: str,
) -> tuple[Any, ...]:
    return (
        config.model_name,
        config.provider,
        config.prompt_family,
        config.prompt_version,
        prompt_sha256,
        _freeze_for_cache(config.model_settings),
    )


def get_extraction_prompt_ref(
    config: ExtractionConfig | None = None,
) -> PromptRef:
    resolved_config = config or ExtractionConfig()
    return _load_prompt_ref(
        family=resolved_config.prompt_family,
        version=resolved_config.prompt_version,
    )


def _resolve_model_settings(config: ExtractionConfig) -> dict[str, Any]:
    if config.model_settings is not None:
        return deepcopy(config.model_settings)
    return deepcopy(_DEFAULT_MODEL_SETTINGS)


def _read_backend_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if not _BACKEND_ENV_PATH.exists():
        return None

    for line in _BACKEND_ENV_PATH.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return raw_value.strip().strip('"').strip("'")

    return None


def _get_gemini_api_key() -> str:
    gemini_api_key = _read_backend_env_var("GEMINI_API_KEY")
    if gemini_api_key:
        return gemini_api_key
    return get_settings().gemini_api_key


def _get_mistral_api_key() -> str | None:
    return _read_backend_env_var("MISTRAL_API_KEY")


def _get_deepinfra_api_key() -> str | None:
    return _read_backend_env_var("DEEPINFRA_API_KEY")


def _build_model(config: ExtractionConfig) -> Any:
    return build_model(
        config.model_name,
        provider=config.provider,
        gemini_api_key_getter=_get_gemini_api_key,
        mistral_api_key_getter=_get_mistral_api_key,
        deepinfra_api_key_getter=_get_deepinfra_api_key,
    )


def build_extraction_agent(
    config: ExtractionConfig,
    *,
    prompt_ref: PromptRef | None = None,
) -> Agent[None, ExtractionResult]:
    resolved_prompt_ref = prompt_ref or get_extraction_prompt_ref(config)
    return Agent(
        _build_model(config),
        output_type=ExtractionResult,
        instructions=resolved_prompt_ref.content,
        model_settings=_resolve_model_settings(config),
    )


def _get_agent(
    config: ExtractionConfig | None = None,
) -> Agent[None, ExtractionResult]:
    resolved_config = config or ExtractionConfig()
    prompt_ref = get_extraction_prompt_ref(resolved_config)
    cache_key = _config_cache_key(
        resolved_config,
        prompt_sha256=prompt_ref.sha256,
    )

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = build_extraction_agent(
            resolved_config,
            prompt_ref=prompt_ref,
        )

    return _agent_cache[cache_key]


def _format_previous_todos(previous_todos: list[Todo]) -> str:
    lines: list[str] = []
    for index, todo in enumerate(previous_todos, start=1):
        parts = [todo.text]
        if todo.priority is not None:
            parts.append(f"priority: {todo.priority}")
        if todo.category is not None:
            parts.append(f"category: {todo.category}")
        if todo.due_date is not None:
            parts.append(f"due: {todo.due_date.isoformat()}")
        if todo.notification is not None:
            parts.append(f"notification: {todo.notification.isoformat()}")
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


async def extract_todos(
    transcript: str,
    *,
    reference_dt: datetime | None = None,
    previous_todos: list[Todo] | None = None,
    config: ExtractionConfig | None = None,
) -> list[Todo]:
    """Extract structured todos from a transcript using the configured LLM."""
    if not transcript.strip():
        return []

    if reference_dt is None:
        reference_dt = datetime.now().astimezone()

    agent = _get_agent(config)
    result = await agent.run(
        _build_extraction_input(transcript, reference_dt, previous_todos)
    )
    return result.output.todos
