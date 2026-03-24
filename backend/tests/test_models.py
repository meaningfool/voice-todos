from datetime import date, datetime

import pytest
from pydantic import ValidationError


def test_todo_text_only():
    """Todo with just text is valid — all other fields default to None."""
    from app.models import Todo

    todo = Todo(text="Buy groceries")
    assert todo.text == "Buy groceries"
    assert todo.priority is None
    assert todo.category is None
    assert todo.due_date is None
    assert todo.notification is None
    assert todo.assign_to is None


def test_todo_all_fields():
    """Todo accepts all optional fields."""
    from app.models import Todo

    todo = Todo(
        text="Call dentist",
        priority="high",
        category="health",
        due_date="2026-03-27",
        notification="2026-03-27T09:00:00",
        assign_to="Marie",
    )
    assert todo.text == "Call dentist"
    assert todo.priority == "high"
    assert todo.due_date == date(2026, 3, 27)
    assert todo.notification == datetime(2026, 3, 27, 9, 0, 0)
    assert todo.assign_to == "Marie"
    assert todo.model_dump(mode="json", exclude_none=True)["due_date"] == "2026-03-27"


def test_todo_requires_text():
    """Todo without text raises ValidationError."""
    from app.models import Todo

    with pytest.raises(ValidationError):
        Todo()


def test_todo_invalid_priority():
    """Priority must be high, medium, or low."""
    from app.models import Todo

    with pytest.raises(ValidationError):
        Todo(text="test", priority="critical")


def test_extraction_result():
    """ExtractionResult wraps a list of todos."""
    from app.models import ExtractionResult, Todo

    result = ExtractionResult(
        todos=[Todo(text="Task A"), Todo(text="Task B", priority="low")]
    )
    assert len(result.todos) == 2
    assert result.todos[0].text == "Task A"
    assert result.todos[1].priority == "low"


def test_extraction_result_empty():
    """ExtractionResult with empty list is valid (no todos found)."""
    from app.models import ExtractionResult

    result = ExtractionResult(todos=[])
    assert result.todos == []
