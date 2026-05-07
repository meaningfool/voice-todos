from __future__ import annotations

from app.extract import _parse_todo_payload


def test_parse_todo_payload_drops_blank_optional_fields():
    todo = _parse_todo_payload(
        {
            "text": "Buy oat milk",
            "category": "",
            "due_date": "",
            "notification": "",
            "assign_to": " ",
        }
    )

    assert todo is not None
    assert todo.text == "Buy oat milk"
    assert todo.category is None
    assert todo.due_date is None
    assert todo.notification is None
    assert todo.assign_to is None
