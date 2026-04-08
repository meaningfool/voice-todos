import builtins
import os
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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


def _guard_optional_mistral_import(
    name, globals=None, locals=None, fromlist=(), level=0
):
    if name.startswith("pydantic_ai.models.mistral") or name.startswith(
        "pydantic_ai.providers.mistral"
    ):
        raise AssertionError(f"unexpected optional import: {name}")
    return _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)


_ORIGINAL_IMPORT = builtins.__import__


@pytest.fixture(autouse=True)
def _reset_agent():
    """Reset the cached agent between tests.

    pytest-asyncio creates a new event loop per test, but the cached agent
    holds an httpx client bound to the previous loop. Clearing it forces a
    fresh client on each test's loop.
    """
    if hasattr(_extract_mod, "_agent_cache"):
        _extract_mod._agent_cache.clear()
    if hasattr(_extract_mod, "_agent"):
        _extract_mod._agent = None
    yield
    if hasattr(_extract_mod, "_agent_cache"):
        _extract_mod._agent_cache.clear()
    if hasattr(_extract_mod, "_agent"):
        _extract_mod._agent = None


def test_get_agent_uses_configured_gemini_api_key():
    """The cached agent should be built with the configured Gemini API key."""
    fake_gemini_lookup = Mock(return_value="gemini-test-key")
    fake_mistral_lookup = Mock(return_value=None)
    fake_deepinfra_lookup = Mock(return_value=None)
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract._get_gemini_api_key", fake_gemini_lookup),
        patch("app.extract._get_mistral_api_key", fake_mistral_lookup),
        patch("app.extract._get_deepinfra_api_key", fake_deepinfra_lookup),
        patch("app.extract.build_model", return_value=fake_model) as mock_build_model,
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        agent = _extract_mod._get_agent()

    assert agent is fake_agent
    mock_build_model.assert_called_once_with(
        "gemini-3-flash-preview",
        provider=None,
        gemini_api_key_getter=fake_gemini_lookup,
        mistral_api_key_getter=fake_mistral_lookup,
        deepinfra_api_key_getter=fake_deepinfra_lookup,
    )
    gemini_api_key_getter = mock_build_model.call_args.kwargs["gemini_api_key_getter"]
    assert gemini_api_key_getter() == "gemini-test-key"
    fake_gemini_lookup.assert_called_once_with()
    fake_mistral_lookup.assert_not_called()
    fake_deepinfra_lookup.assert_not_called()
    mock_agent.assert_called_once_with(
        fake_model,
        output_type=ExtractionResult,
        instructions=_extract_mod.get_extraction_prompt_ref().content,
        model_settings={
            "google_thinking_config": {"thinking_level": "minimal"}
        },
    )


def test_build_model_uses_google_factory_for_gemini():
    from app import model_providers

    gemini_api_key_getter = Mock(return_value="gemini-test-key")
    fake_provider = object()
    fake_model = object()

    with (
        patch("app.model_providers.GoogleProvider", return_value=fake_provider)
        as mock_provider,
        patch("app.model_providers.GoogleModel", return_value=fake_model)
        as mock_model,
        patch("builtins.__import__", side_effect=_guard_optional_mistral_import),
    ):
        model = model_providers.build_model(
            "gemini-3-flash-preview",
            gemini_api_key_getter=gemini_api_key_getter,
        )

    assert model is fake_model
    gemini_api_key_getter.assert_called_once_with()
    mock_provider.assert_called_once_with(api_key="gemini-test-key")
    mock_model.assert_called_once_with(
        "gemini-3-flash-preview",
        provider=fake_provider,
    )


def test_build_model_uses_mistral_factory_lazily():
    from app import model_providers

    gemini_api_key_getter = Mock(
        side_effect=AssertionError("Gemini lookup should not happen for Mistral")
    )
    mistral_api_key_getter = Mock(return_value="mistral-test-key")

    class FakeMistralProvider:
        def __init__(self, *, api_key):
            self.api_key = api_key

    class FakeMistralModel:
        def __init__(self, model_name, *, provider):
            self.model_name = model_name
            self.provider = provider

    fake_mistral_module = SimpleNamespace(MistralModel=FakeMistralModel)
    fake_provider_module = SimpleNamespace(MistralProvider=FakeMistralProvider)

    with patch.dict(
        sys.modules,
        {
            "pydantic_ai.models.mistral": fake_mistral_module,
            "pydantic_ai.providers.mistral": fake_provider_module,
        },
    ):
        model = model_providers.build_model(
            "mistral-small-latest",
            provider="mistral",
            gemini_api_key_getter=gemini_api_key_getter,
            mistral_api_key_getter=mistral_api_key_getter,
        )

    assert isinstance(model, FakeMistralModel)
    assert model.model_name == "mistral-small-latest"
    assert model.provider.api_key == "mistral-test-key"
    gemini_api_key_getter.assert_not_called()
    mistral_api_key_getter.assert_called_once_with()


def test_build_model_uses_deepinfra_factory_lazily():
    from app import model_providers

    gemini_api_key_getter = Mock(
        side_effect=AssertionError("Gemini lookup should not happen for DeepInfra")
    )
    deepinfra_api_key_getter = Mock(return_value="deepinfra-test-key")

    class FakeOpenAIProvider:
        def __init__(self, *, base_url, api_key):
            self.base_url = base_url
            self.api_key = api_key

    class FakeOpenAIChatModel:
        def __init__(self, model_name, *, provider):
            self.model_name = model_name
            self.provider = provider

    fake_openai_module = SimpleNamespace(OpenAIChatModel=FakeOpenAIChatModel)
    fake_provider_module = SimpleNamespace(OpenAIProvider=FakeOpenAIProvider)

    with patch.dict(
        sys.modules,
        {
            "pydantic_ai.models.openai": fake_openai_module,
            "pydantic_ai.providers.openai": fake_provider_module,
        },
    ):
        model = model_providers.build_model(
            "Qwen/Qwen3.5-9B",
            provider="deepinfra",
            gemini_api_key_getter=gemini_api_key_getter,
            deepinfra_api_key_getter=deepinfra_api_key_getter,
        )

    assert isinstance(model, FakeOpenAIChatModel)
    assert model.model_name == "Qwen/Qwen3.5-9B"
    assert model.provider.base_url == "https://api.deepinfra.com/v1/openai"
    assert model.provider.api_key == "deepinfra-test-key"
    gemini_api_key_getter.assert_not_called()
    deepinfra_api_key_getter.assert_called_once_with()


def test_build_extraction_agent_delegates_to_model_provider():
    from app.extract import ExtractionConfig, build_extraction_agent

    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract._get_gemini_api_key") as mock_gemini_key,
        patch("app.extract._get_mistral_api_key") as mock_mistral_key,
        patch("app.extract._get_deepinfra_api_key") as mock_deepinfra_key,
        patch("app.extract.build_model", return_value=fake_model) as mock_build_model,
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        agent = build_extraction_agent(
            ExtractionConfig(
                model_name="Qwen/Qwen3.5-9B",
                provider="deepinfra",
                model_settings={},
            )
        )

    assert agent is fake_agent
    mock_build_model.assert_called_once_with(
        "Qwen/Qwen3.5-9B",
        provider="deepinfra",
        gemini_api_key_getter=mock_gemini_key,
        mistral_api_key_getter=mock_mistral_key,
        deepinfra_api_key_getter=mock_deepinfra_key,
    )
    mock_gemini_key.assert_not_called()
    mock_mistral_key.assert_not_called()
    mock_deepinfra_key.assert_not_called()
    mock_agent.assert_called_once_with(
        fake_model,
        output_type=ExtractionResult,
        instructions=_extract_mod.get_extraction_prompt_ref(
            ExtractionConfig(
                model_name="Qwen/Qwen3.5-9B",
                provider="deepinfra",
                model_settings={},
            )
        ).content,
        model_settings={},
    )


def test_get_agent_uses_minimal_google_thinking():
    """The cached agent should request minimal Google thinking."""
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract._get_gemini_api_key", return_value="test-key"),
        patch("app.extract._get_mistral_api_key", return_value=None),
        patch("app.extract._get_deepinfra_api_key", return_value=None),
        patch("app.extract.build_model", return_value=fake_model),
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        _extract_mod._agent = None
        _extract_mod._get_agent()

    assert mock_agent.call_args.kwargs["model_settings"] == {
        "google_thinking_config": {"thinking_level": "minimal"}
    }


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


@pytest.mark.asyncio
async def test_extract_todos_uses_override_model():
    """A runtime config override should drive agent model selection."""
    from app.extract import ExtractionConfig, extract_todos

    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=[])))
    )
    fake_model = object()
    fake_key = Mock(return_value="test-key")
    fake_mistral_key = Mock(return_value=None)
    fake_deepinfra_key = Mock(return_value=None)

    with (
        patch("app.extract._get_gemini_api_key", fake_key),
        patch("app.extract._get_mistral_api_key", fake_mistral_key),
        patch("app.extract._get_deepinfra_api_key", fake_deepinfra_key),
        patch("app.extract.build_model", return_value=fake_model) as mock_build_model,
        patch("app.extract.Agent", return_value=fake_agent),
    ):
        await extract_todos(
            "Call Marie tomorrow.",
            reference_dt=datetime(2026, 3, 23, 9, 30, tzinfo=UTC),
            config=ExtractionConfig(model_name="google-gla:gemini-3-pro-preview"),
        )

    mock_build_model.assert_called_once_with(
        "google-gla:gemini-3-pro-preview",
        provider=None,
        gemini_api_key_getter=fake_key,
        mistral_api_key_getter=fake_mistral_key,
        deepinfra_api_key_getter=fake_deepinfra_key,
    )
    assert _extract_mod.ExtractionConfig().model_name == "gemini-3-flash-preview"


def test_extract_todos_passes_model_settings():
    """Provider-specific settings should be forwarded into agent creation."""
    from app.extract import ExtractionConfig, build_extraction_agent

    fake_key = Mock(return_value="gemini-test-key")
    fake_mistral_key = Mock(return_value=None)
    fake_deepinfra_key = Mock(return_value=None)
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract._get_gemini_api_key", fake_key),
        patch("app.extract._get_mistral_api_key", fake_mistral_key),
        patch("app.extract._get_deepinfra_api_key", fake_deepinfra_key),
        patch("app.extract.build_model", return_value=fake_model) as mock_build_model,
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        agent = build_extraction_agent(
            ExtractionConfig(
                model_settings={"google_thinking_config": {"thinking_level": "high"}}
            )
        )

    assert agent is fake_agent
    mock_build_model.assert_called_once_with(
        "gemini-3-flash-preview",
        provider=None,
        gemini_api_key_getter=fake_key,
        mistral_api_key_getter=fake_mistral_key,
        deepinfra_api_key_getter=fake_deepinfra_key,
    )
    mock_agent.assert_called_once_with(
        fake_model,
        output_type=ExtractionResult,
        instructions=_extract_mod.get_extraction_prompt_ref(
            ExtractionConfig(
                model_settings={"google_thinking_config": {"thinking_level": "high"}}
            )
        ).content,
        model_settings={
            "google_thinking_config": {"thinking_level": "high"}
        },
    )


def test_unknown_prompt_version_raises_value_error():
    from app.extract import ExtractionConfig, build_extraction_agent

    with pytest.raises(ValueError, match="Unsupported prompt version"):
        build_extraction_agent(ExtractionConfig(prompt_version="v9"))


def test_get_agent_does_not_reuse_different_model_config():
    """Agent caching should distinguish different extraction configs."""
    from app.extract import ExtractionConfig, _get_agent

    first_agent = object()
    second_agent = object()
    fake_model = object()

    with (
        patch("app.extract._get_gemini_api_key", return_value="gemini-test-key"),
        patch("app.extract.build_model", return_value=fake_model),
        patch("app.extract.Agent", side_effect=[first_agent, second_agent]),
    ):
        agent_one = _get_agent(ExtractionConfig(model_name="model-a"))
        agent_two = _get_agent(ExtractionConfig(model_name="model-b"))

    assert agent_one is first_agent
    assert agent_two is second_agent
    assert agent_one is not agent_two


def test_get_agent_rebuilds_when_prompt_sha_changes():
    """Changing prompt content should invalidate the cached agent."""
    from pathlib import Path

    from app.extract import ExtractionConfig, _get_agent
    from app.prompts.registry import PromptRef

    first_agent = object()
    second_agent = object()
    first_prompt = PromptRef(
        family="todo_extraction",
        version="v1",
        path=Path("/tmp/todo_extraction_v1.md"),
        content="prompt one",
        sha256="sha-one",
    )
    second_prompt = PromptRef(
        family="todo_extraction",
        version="v1",
        path=Path("/tmp/todo_extraction_v1.md"),
        content="prompt two",
        sha256="sha-two",
    )

    with (
        patch("app.extract._get_gemini_api_key", return_value="gemini-test-key"),
        patch(
            "app.extract.get_extraction_prompt_ref",
            side_effect=[first_prompt, second_prompt],
        ),
        patch("app.extract.build_model", return_value=object()),
        patch(
            "app.extract.Agent",
            side_effect=[first_agent, second_agent],
        ) as mock_agent,
    ):
        agent_one = _get_agent(ExtractionConfig(model_name="model-a"))
        agent_two = _get_agent(ExtractionConfig(model_name="model-a"))

    assert agent_one is first_agent
    assert agent_two is second_agent
    assert agent_one is not agent_two
    assert mock_agent.call_count == 2


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
