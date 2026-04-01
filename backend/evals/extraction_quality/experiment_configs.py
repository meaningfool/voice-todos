from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

from app.extract import ExtractionConfig

_BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _read_backend_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if not _BACKEND_ENV_PATH.exists():
        return None

    for line in _BACKEND_ENV_PATH.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return raw_value.strip().strip('"').strip("'")

    return None


def _google_unavailable_reason() -> str | None:
    if _read_backend_env_var("GEMINI_API_KEY"):
        return None
    return "missing GEMINI_API_KEY"


def _mistral_unavailable_reason() -> str | None:
    try:
        importlib.import_module("pydantic_ai.models.mistral")
        importlib.import_module("pydantic_ai.providers.mistral")
    except Exception as exc:
        return f"mistral provider unavailable: {exc}"

    if _read_backend_env_var("MISTRAL_API_KEY"):
        return None

    return "missing MISTRAL_API_KEY"


@dataclass(frozen=True)
class ExperimentDefinition:
    name: str
    extraction_config: ExtractionConfig
    provider: str
    thinking_mode: str

    def unavailable_reason(self) -> str | None:
        if self.provider == "google-gla":
            return _google_unavailable_reason()
        if self.provider == "mistral":
            return _mistral_unavailable_reason()
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
            model_settings={},
            prompt_version="v1",
        ),
        provider="mistral",
        thinking_mode="provider_default",
    ),
}
