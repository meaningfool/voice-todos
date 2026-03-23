import os

import pytest

requires_gemini = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping integration test",
)


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

    todos = await extract_todos("Ask Jean to send the invoice.")

    assert len(todos) >= 1
    assert todos[0].assign_to is not None
    assert "jean" in todos[0].assign_to.lower()


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
