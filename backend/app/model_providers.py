from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

_DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
_DEEPINFRA_MODEL_NAMES = frozenset(
    {
        "Qwen/Qwen3.5-9B",
        "Qwen/Qwen3.5-4B",
    }
)


def build_google_model(
    model_name: str,
    *,
    api_key: str,
    model_cls: type[Any] | None = None,
    provider_cls: type[Any] | None = None,
) -> Any:
    if model_cls is None:
        model_cls = GoogleModel
    if provider_cls is None:
        provider_cls = GoogleProvider
    return model_cls(model_name, provider=provider_cls(api_key=api_key))


def build_mistral_model(
    model_name: str,
    *,
    api_key: str | None,
) -> Any:
    from pydantic_ai.models.mistral import MistralModel
    from pydantic_ai.providers.mistral import MistralProvider

    return MistralModel(model_name, provider=MistralProvider(api_key=api_key))


def build_deepinfra_model(
    model_name: str,
    *,
    api_key: str | None,
    model_cls: type[Any] | None = None,
    provider_cls: type[Any] | None = None,
) -> Any:
    if model_cls is None:
        from pydantic_ai.models.openai import OpenAIChatModel

        model_cls = OpenAIChatModel
    if provider_cls is None:
        from pydantic_ai.providers.openai import OpenAIProvider

        provider_cls = OpenAIProvider

    return model_cls(
        model_name,
        provider=provider_cls(
            base_url=_DEEPINFRA_BASE_URL,
            api_key=api_key,
        ),
    )


def build_model(
    model_name: str,
    *,
    provider: str | None = None,
    gemini_api_key_getter: Callable[[], str],
    mistral_api_key_getter: Callable[[], str | None] | None = None,
    deepinfra_api_key_getter: Callable[[], str | None] | None = None,
) -> Any:
    resolved_provider = provider
    if resolved_provider is None and model_name.startswith("mistral-"):
        resolved_provider = "mistral"
    if resolved_provider is None and model_name in _DEEPINFRA_MODEL_NAMES:
        resolved_provider = "deepinfra"

    if resolved_provider == "mistral":
        return build_mistral_model(
            model_name,
            api_key=(
                mistral_api_key_getter()
                if mistral_api_key_getter is not None
                else os.getenv("MISTRAL_API_KEY")
            ),
        )
    if resolved_provider == "deepinfra":
        return build_deepinfra_model(
            model_name,
            api_key=(
                deepinfra_api_key_getter()
                if deepinfra_api_key_getter is not None
                else os.getenv("DEEPINFRA_API_KEY")
            ),
        )
    if resolved_provider not in {None, "google-gla"}:
        raise ValueError(f"Unsupported model provider: {resolved_provider}")

    return build_google_model(
        model_name,
        api_key=gemini_api_key_getter(),
    )
