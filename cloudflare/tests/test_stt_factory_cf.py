from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from stt_factory_cf import create_stt_session


@pytest.mark.asyncio
async def test_create_stt_session_routes_mistral_provider_to_hosted_connector() -> None:
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key="mistral-test-key",
        soniox_api_key="unused",
    )
    fake_session = object()
    connect_soniox = AsyncMock()
    connect_mistral = AsyncMock(return_value=fake_session)

    session = await create_stt_session(
        settings,
        connect_soniox_fn=connect_soniox,
        connect_mistral_fn=connect_mistral,
    )

    assert session is fake_session
    connect_mistral.assert_awaited_once_with(
        "mistral-test-key",
        raw_event_callback=None,
    )
    connect_soniox.assert_not_called()


@pytest.mark.asyncio
async def test_create_stt_session_rejects_mistral_without_api_key() -> None:
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key=None,
        soniox_api_key="unused",
    )

    with pytest.raises(ValueError, match="Mistral API key is required"):
        await create_stt_session(settings, connect_mistral_fn=AsyncMock())
