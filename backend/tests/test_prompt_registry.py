from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_get_prompt_ref_returns_expected_metadata():
    from app.prompts.registry import get_prompt_ref

    prompt = get_prompt_ref(family="todo_extraction", version="v1")
    prompt_path = (
        Path(__file__).resolve().parents[1]
        / "app/prompts/todo_extraction/v1.md"
    )
    expected_content = prompt_path.read_text()

    assert prompt.family == "todo_extraction"
    assert prompt.version == "v1"
    assert prompt.path == prompt_path
    assert prompt.content == expected_content
    assert prompt.sha256 == hashlib.sha256(expected_content.encode()).hexdigest()


def test_build_extraction_agent_uses_prompt_ref_content():
    import app.extract as extract_mod
    from app.models import ExtractionResult
    from app.prompts.registry import get_prompt_ref

    fake_provider = object()
    fake_model = object()
    fake_agent = object()

    with (
        patch(
            "app.extract.get_settings",
            return_value=SimpleNamespace(gemini_api_key="gemini-test-key"),
        ),
        patch("app.extract.GoogleProvider", return_value=fake_provider),
        patch("app.extract.GoogleModel", return_value=fake_model),
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        extract_mod.build_extraction_agent(extract_mod.ExtractionConfig())

    prompt = get_prompt_ref(
        family="todo_extraction",
        version="v1",
    )
    assert mock_agent.call_args.kwargs["instructions"] == prompt.content
    assert "system_prompt" not in mock_agent.call_args.kwargs
    assert mock_agent.call_args.kwargs["output_type"] is ExtractionResult


def test_unknown_prompt_version_raises_value_error():
    from app.prompts.registry import get_prompt_ref

    with pytest.raises(ValueError, match="Unsupported prompt version"):
        get_prompt_ref(family="todo_extraction", version="v9")
