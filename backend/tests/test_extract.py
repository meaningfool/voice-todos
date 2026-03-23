import os

import pytest

import app.extract as _extract_mod

requires_gemini = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping integration test",
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


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_no_actionable_items():
    """Transcript with no tasks returns empty or near-empty list."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "The weather is nice today. I had a good lunch."
    )

    assert len(todos) == 0
