from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider


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


def build_model(
    model_name: str,
    *,
    gemini_api_key_getter: Callable[[], str],
) -> Any:
    if model_name.startswith("mistral-"):
        return build_mistral_model(
            model_name,
            api_key=os.getenv("MISTRAL_API_KEY"),
        )

    return build_google_model(
        model_name,
        api_key=gemini_api_key_getter(),
    )
