from __future__ import annotations


def test_hosted_app_can_import_shared_todo_stack():
    from app.extract import extract_todos
    from app.extraction_loop import ExtractionLoop
    from app.prompts.registry import get_prompt_ref

    prompt_ref = get_prompt_ref(family="todo_extraction", version="v1")

    assert ExtractionLoop is not None
    assert extract_todos is not None
    assert prompt_ref.family == "todo_extraction"
    assert prompt_ref.version == "v1"
    assert "todo_extraction" in str(prompt_ref.path)
