import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.extract as _extract_mod
from app.models import ExtractionResult, Todo

requires_gemini = pytest.mark.skipif(
    not (
        os.environ.get("GEMINI_API_KEY")
        and os.environ.get("RUN_GEMINI_INTEGRATION") == "1"
    ),
    reason=(
        "Gemini integration tests require GEMINI_API_KEY and "
        "RUN_GEMINI_INTEGRATION=1"
    ),
)


@pytest.fixture(autouse=True)
def _reset_agent():
    """Reset the cached agent between tests.

    pytest-asyncio creates a new event loop per test, but the cached agent
    holds an httpx client bound to the previous loop. Clearing it forces a
    fresh client on each test's loop.
    """
    _extract_mod._agent = None
    yield
    _extract_mod._agent = None


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_from_clear_transcript():
    """Given a transcript with obvious todos, extract_todos returns them."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "I need to buy groceries and I have to call the dentist. "
        "Also ask Marie to review the budget."
    )

    assert len(todos) >= 2
    texts = [t.text.lower() for t in todos]
    # Should find something about groceries and dentist
    assert any("grocer" in t for t in texts)
    assert any("dentist" in t for t in texts)


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_with_priority_and_deadline():
    """When the speaker uses urgency language and dates, those fields are populated."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "I urgently need to finish the report by Friday."
    )

    assert len(todos) >= 1
    report_todo = todos[0]
    assert report_todo.text  # Has text
    assert report_todo.priority == "high"  # "urgently" → high
    assert report_todo.due_date is not None  # "by Friday" → a date


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_with_assignment():
    """When the speaker delegates to someone, assign_to is populated."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "I need to delegate the invoice review to Jean, he should handle it."
    )

    assert len(todos) >= 1
    # LLM output is non-deterministic — check that Jean appears somewhere
    # (assign_to field or in the text itself)
    todo = todos[0]
    jean_in_assign = todo.assign_to is not None and "jean" in todo.assign_to.lower()
    jean_in_text = "jean" in todo.text.lower()
    assert jean_in_assign or jean_in_text, (
        f"Expected Jean mentioned: assign_to={todo.assign_to!r}, text={todo.text!r}"
    )


@pytest.mark.asyncio
async def test_extract_todos_empty_transcript():
    """Empty transcript returns empty list without calling the API."""
    from app.extract import extract_todos

    todos = await extract_todos("")
    assert todos == []


@pytest.mark.asyncio
async def test_extract_todos_whitespace_only():
    """Whitespace-only transcript returns empty list without calling the API."""
    from app.extract import extract_todos

    todos = await extract_todos("   \n  ")
    assert todos == []


@pytest.mark.asyncio
async def test_extract_todos_passes_reference_context_to_agent():
    """The extraction prompt includes deterministic local date context."""
    from app.extract import extract_todos

    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=[])))
    )
    reference_dt = datetime(2026, 3, 23, 9, 30, tzinfo=UTC)

    with patch("app.extract._get_agent", return_value=fake_agent):
        await extract_todos(
            "Remind me tomorrow to call Marie.", reference_dt=reference_dt
        )

    sent_prompt = fake_agent.run.await_args.args[0]
    assert "Current local datetime: 2026-03-23T09:30:00+00:00" in sent_prompt
    assert "Current local date: 2026-03-23" in sent_prompt
    assert "Current timezone: UTC" in sent_prompt


@pytest.mark.asyncio
async def test_extract_todos_includes_previous_todos_in_prompt():
    """Previous todos are threaded into the prompt with metadata."""
    from app.extract import extract_todos

    previous_todos = [
        Todo(
            text="Call Marie",
            priority="high",
            category="work",
            due_date=datetime(2026, 3, 24).date(),
            notification=datetime(2026, 3, 24, 9, 0, tzinfo=UTC),
            assign_to="Marie",
        )
    ]
    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=[])))
    )

    with patch("app.extract._get_agent", return_value=fake_agent):
        await extract_todos(
            "Call Marie tomorrow morning.",
            reference_dt=datetime(2026, 3, 23, 9, 30, tzinfo=UTC),
            previous_todos=previous_todos,
        )

    sent_prompt = fake_agent.run.await_args.args[0]
    assert "Previously extracted todos:" in sent_prompt
    assert "1. Call Marie" in sent_prompt
    assert "priority: high" in sent_prompt
    assert "category: work" in sent_prompt
    assert "due: 2026-03-24" in sent_prompt
    assert "notification: 2026-03-24T09:00:00+00:00" in sent_prompt
    assert "assign to: Marie" in sent_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("previous_todos", [[], None])
async def test_extract_todos_omits_previous_section_when_empty_or_none(
    previous_todos,
):
    """Empty previous_todos should not add an extra prompt section."""
    from app.extract import extract_todos

    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=[])))
    )

    with patch("app.extract._get_agent", return_value=fake_agent):
        await extract_todos(
            "Call Marie tomorrow.",
            reference_dt=datetime(2026, 3, 23, 9, 30, tzinfo=UTC),
            previous_todos=previous_todos,
        )

    sent_prompt = fake_agent.run.await_args.args[0]
    assert "Previously extracted todos:" not in sent_prompt


@pytest.mark.asyncio
async def test_extract_todos_returns_agent_output():
    """Structured agent output is returned unchanged to the caller."""
    from app.extract import extract_todos

    fake_todos = [
        Todo(text="Call Marie", due_date="2026-03-24", assign_to="Marie")
    ]
    fake_agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(output=ExtractionResult(todos=fake_todos))
        )
    )

    with patch("app.extract._get_agent", return_value=fake_agent):
        todos = await extract_todos("Call Marie tomorrow.")

    assert todos == fake_todos


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_no_actionable_items():
    """Transcript with no tasks returns empty or near-empty list."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "The weather is nice today. I had a good lunch."
    )

    assert len(todos) == 0
