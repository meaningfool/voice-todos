from __future__ import annotations

from datetime import datetime

from pydantic_ai import Agent

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
)

_agent: Agent[None, ExtractionResult] | None = None


def _get_agent() -> Agent[None, ExtractionResult]:
    global _agent
    if _agent is None:
        get_settings()  # ensures .env is loaded before the provider is used

        _agent = Agent(
            "google-gla:gemini-3-flash-preview",
            output_type=ExtractionResult,
            system_prompt=_SYSTEM_PROMPT,
        )
    return _agent


def _build_extraction_input(transcript: str, reference_dt: datetime) -> str:
    timezone_name = reference_dt.tzname() or "UTC"
    return (
        f"Current local datetime: {reference_dt.isoformat()}\n"
        f"Current local date: {reference_dt.date().isoformat()}\n"
        f"Current timezone: {timezone_name}\n\n"
        "Transcript:\n"
        f"{transcript}"
    )


async def extract_todos(
    transcript: str, *, reference_dt: datetime | None = None
) -> list[Todo]:
    """Extract structured todos from a transcript using Gemini."""
    if not transcript.strip():
        return []

    if reference_dt is None:
        reference_dt = datetime.now().astimezone()

    agent = _get_agent()
    result = await agent.run(_build_extraction_input(transcript, reference_dt))
    return result.output.todos
