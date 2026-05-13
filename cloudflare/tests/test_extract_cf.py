from __future__ import annotations

from app.extract import ExtractionConfig, _parse_todo_payload, _resolve_model_settings


def test_hosted_extraction_defaults_to_flash_lite_with_provider_thinking():
    config = ExtractionConfig()

    assert config.model_name == "gemini-3.1-flash-lite-preview"
    assert _resolve_model_settings(config) == {}


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
