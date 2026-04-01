from __future__ import annotations

from datetime import datetime

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

_agent: Agent[None, ExtractionResult] | None = None


def _get_agent() -> Agent[None, ExtractionResult]:
    global _agent
    if _agent is None:
        settings = get_settings()

        _agent = Agent(
            GoogleModel(
                "gemini-3-flash-preview",
                provider=GoogleProvider(api_key=settings.gemini_api_key),
            ),
            output_type=ExtractionResult,
            system_prompt=_SYSTEM_PROMPT,
            model_settings={
                "google_thinking_config": {"thinking_level": "minimal"},
            },
        )
    return _agent


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
) -> list[Todo]:
    """Extract structured todos from a transcript using Gemini."""
    if not transcript.strip():
        return []

    if reference_dt is None:
        reference_dt = datetime.now().astimezone()

    agent = _get_agent()
    result = await agent.run(
        _build_extraction_input(transcript, reference_dt, previous_todos)
    )
    return result.output.todos
