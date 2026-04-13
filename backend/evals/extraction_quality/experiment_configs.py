from __future__ import annotations

import importlib
from dataclasses import dataclass

from app.backend_env import read_backend_env_var
from app.extract import ExtractionConfig, get_extraction_prompt_ref


def _google_unavailable_reason() -> str | None:
    if read_backend_env_var("GEMINI_API_KEY"):
        return None
    return "missing GEMINI_API_KEY"


def _mistral_unavailable_reason() -> str | None:
    try:
        importlib.import_module("pydantic_ai.models.mistral")
        importlib.import_module("pydantic_ai.providers.mistral")
    except Exception as exc:
        return f"mistral provider unavailable: {exc}"

    if read_backend_env_var("MISTRAL_API_KEY"):
        return None

    return "missing MISTRAL_API_KEY"


def _deepinfra_unavailable_reason() -> str | None:
    try:
        importlib.import_module("pydantic_ai.models.openai")
        importlib.import_module("pydantic_ai.providers.openai")
    except Exception as exc:
        return f"deepinfra provider unavailable: {exc}"

    if read_backend_env_var("DEEPINFRA_API_KEY"):
        return None

    return "missing DEEPINFRA_API_KEY"


@dataclass(frozen=True)
class ExperimentDefinition:
    name: str
    extraction_config: ExtractionConfig
    provider: str
    thinking_mode: str

    @property
    def prompt_metadata(self) -> dict[str, str]:
        prompt_ref = get_extraction_prompt_ref(self.extraction_config)
        return {
            "prompt_family": prompt_ref.family,
            "prompt_version": prompt_ref.version,
            "prompt_sha": prompt_ref.sha256,
        }

    @property
    def identity_metadata(self) -> dict[str, str]:
        return {
            "experiment": self.name,
            "model_name": self.extraction_config.model_name,
            "provider": self.provider,
            "thinking_mode": self.thinking_mode,
            **self.prompt_metadata,
        }

    def unavailable_reason(self) -> str | None:
        if self.provider == "google-gla":
            return _google_unavailable_reason()
        if self.provider == "mistral":
            return _mistral_unavailable_reason()
        if self.provider == "deepinfra":
            return _deepinfra_unavailable_reason()
        return None

    @property
    def is_available(self) -> bool:
        return self.unavailable_reason() is None


EXPERIMENTS: dict[str, ExperimentDefinition] = {
    "gemini3_flash_default": ExperimentDefinition(
        name="gemini3_flash_default",
        extraction_config=ExtractionConfig(
            model_name="gemini-3-flash-preview",
            model_settings={},
            prompt_version="v1",
        ),
        provider="google-gla",
        thinking_mode="provider_default",
    ),
    "gemini3_flash_minimal_thinking": ExperimentDefinition(
        name="gemini3_flash_minimal_thinking",
        extraction_config=ExtractionConfig(
            model_name="gemini-3-flash-preview",
            model_settings={
                "google_thinking_config": {"thinking_level": "minimal"},
            },
            prompt_version="v1",
        ),
        provider="google-gla",
        thinking_mode="minimal",
    ),
    "gemini31_flash_lite_default": ExperimentDefinition(
        name="gemini31_flash_lite_default",
        extraction_config=ExtractionConfig(
            model_name="gemini-3.1-flash-lite-preview",
            model_settings={},
            prompt_version="v1",
        ),
        provider="google-gla",
        thinking_mode="provider_default",
    ),
    "gemini31_flash_lite_minimal_thinking": ExperimentDefinition(
        name="gemini31_flash_lite_minimal_thinking",
        extraction_config=ExtractionConfig(
            model_name="gemini-3.1-flash-lite-preview",
            model_settings={
                "google_thinking_config": {"thinking_level": "minimal"},
            },
            prompt_version="v1",
        ),
        provider="google-gla",
        thinking_mode="minimal",
    ),
    "mistral_small_4_default": ExperimentDefinition(
        name="mistral_small_4_default",
        extraction_config=ExtractionConfig(
            model_name="mistral-small-2603",
            provider="mistral",
            model_settings={},
            prompt_version="v1",
        ),
        provider="mistral",
        thinking_mode="provider_default",
    ),
    "deepinfra_qwen35_9b_default": ExperimentDefinition(
        name="deepinfra_qwen35_9b_default",
        extraction_config=ExtractionConfig(
            model_name="Qwen/Qwen3.5-9B",
            provider="deepinfra",
            model_settings={},
            prompt_version="v1",
        ),
        provider="deepinfra",
        thinking_mode="provider_default",
    ),
    "deepinfra_qwen35_4b_structured_tuned": ExperimentDefinition(
        name="deepinfra_qwen35_4b_structured_tuned",
        extraction_config=ExtractionConfig(
            model_name="Qwen/Qwen3.5-4B",
            provider="deepinfra",
            model_settings={
                "temperature": 0,
                "max_tokens": 1024,
            },
            prompt_version="v1",
        ),
        provider="deepinfra",
        thinking_mode="structured_output_tuned",
    ),
}


def experiment_definition_from_entry_config(
    *,
    experiment_name_hint: str,
    provider: str,
    model_name: str,
    prompt_version: str,
    model_settings: dict[str, object] | None = None,
) -> ExperimentDefinition:
    legacy = EXPERIMENTS.get(experiment_name_hint)
    if legacy is not None:
        same_config = (
            legacy.provider == provider
            and legacy.extraction_config.model_name == model_name
            and legacy.extraction_config.prompt_version == prompt_version
            and legacy.extraction_config.model_settings == (model_settings or {})
        )
        if same_config:
            return legacy

    resolved_model_settings = dict(model_settings or {})
    if provider == "google-gla":
        extraction_provider = None
        if resolved_model_settings.get("google_thinking_config", {}).get(
            "thinking_level"
        ) == "minimal":
            thinking_mode = "minimal"
        elif resolved_model_settings:
            thinking_mode = "custom"
        else:
            thinking_mode = "provider_default"
    else:
        extraction_provider = provider
        thinking_mode = "provider_default" if not resolved_model_settings else "custom"

    return ExperimentDefinition(
        name=experiment_name_hint,
        extraction_config=ExtractionConfig(
            model_name=model_name,
            provider=extraction_provider,
            model_settings=resolved_model_settings,
            prompt_version=prompt_version,
        ),
        provider=provider,
        thinking_mode=thinking_mode,
    )
