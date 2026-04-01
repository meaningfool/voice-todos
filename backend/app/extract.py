from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.config import get_settings
from app.models import ExtractionResult, Todo

_SYSTEM_PROMPT = (
    "You extract actionable todo items from a voice transcript.\n\n"
    "Rules:\n"
    "- Extract only clearly actionable tasks, not observations or commentary.\n"
    "- Write each todo as a clean, concise imperative sentence (not verbatim speech).\n"
    "- Only set optional fields "
    "(priority, category, due_date, notification, assign_to) "
    "when the speaker clearly indicates them.\n"
    "- priority: 'high' for urgent/important emphasis, 'medium' for moderate, "
    "'low' for minor.\n"
    "- due_date: extract dates/deadlines as ISO format (YYYY-MM-DD). "
    "Resolve relative dates "
    "(e.g., 'tomorrow', 'next Friday') relative to the current date.\n"
    "- notification: extract reminder times as ISO datetime "
    "(YYYY-MM-DDTHH:MM:SS).\n"
    "- assign_to: extract person names when the speaker delegates a task.\n"
    "- category: infer a short category label only when the context is clear.\n"
    "- If no actionable todos are found, return an empty list.\n"
    "\n"
    "Incremental extraction rules:\n"
    "- You may receive a list of previously extracted todos. "
    "Return the updated complete list.\n"
    "- Preserve the order of existing todos where that order still makes sense. "
    "Append genuinely new todos at the end.\n"
    "- If new speech adds details to an existing todo, update it in place.\n"
    "- If later context shows an earlier todo was over-split, duplicated, misheard, "
    "or should be absorbed into another todo, merge or remove it.\n"
    "- Explicit cancellation is one reason to remove a todo, but not the only one.\n"
    "- If no previous todos are provided, extract from scratch.\n"
)


@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "google-gla:gemini-3-flash-preview"
    model_settings: dict[str, Any] | None = None
    prompt_version: str = "v1"


_DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {"thinking_level": "minimal"}
}

_PROMPT_VERSIONS: dict[str, str] = {
    "v1": _SYSTEM_PROMPT,
}

_agent_cache: dict[tuple[Any, ...], Agent[None, ExtractionResult]] = {}


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


def _config_cache_key(config: ExtractionConfig) -> tuple[Any, ...]:
    return (
        config.model_name,
        config.prompt_version,
        _freeze_for_cache(config.model_settings),
    )


def _resolve_system_prompt(prompt_version: str) -> str:
    try:
        return _PROMPT_VERSIONS[prompt_version]
    except KeyError as exc:
        available = ", ".join(sorted(_PROMPT_VERSIONS))
        raise ValueError(
            f"Unsupported extraction prompt version: {prompt_version!r}. "
            f"Available versions: {available}"
        ) from exc


def _resolve_model_settings(config: ExtractionConfig) -> dict[str, Any]:
    if config.model_settings is not None:
        return deepcopy(config.model_settings)
    return deepcopy(_DEFAULT_MODEL_SETTINGS)


def build_extraction_agent(config: ExtractionConfig) -> Agent[None, ExtractionResult]:
    settings = get_settings()

    return Agent(
        GoogleModel(
            config.model_name,
            provider=GoogleProvider(api_key=settings.gemini_api_key),
        ),
        output_type=ExtractionResult,
        system_prompt=_resolve_system_prompt(config.prompt_version),
        model_settings=_resolve_model_settings(config),
    )


def _get_agent(
    config: ExtractionConfig | None = None,
) -> Agent[None, ExtractionResult]:
    resolved_config = config or ExtractionConfig()
    cache_key = _config_cache_key(resolved_config)

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = build_extraction_agent(resolved_config)

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
    """Extract structured todos from a transcript using Gemini."""
    if not transcript.strip():
        return []

    if reference_dt is None:
        reference_dt = datetime.now().astimezone()

    agent = _get_agent(config)
    result = await agent.run(
        _build_extraction_input(transcript, reference_dt, previous_todos)
    )
    return result.output.todos
