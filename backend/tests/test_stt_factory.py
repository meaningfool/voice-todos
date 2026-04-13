from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.stt_factory import create_stt_session


@pytest.mark.asyncio
async def test_create_stt_session_routes_default_provider_to_soniox():
    settings = SimpleNamespace(
        soniox_api_key="soniox-test-key",
    )
    fake_session = object()
    connect_soniox = AsyncMock(return_value=fake_session)

    session = await create_stt_session(
        settings,
        connect_soniox_fn=connect_soniox,
    )

    assert session is fake_session
    connect_soniox.assert_awaited_once_with(
        "soniox-test-key",
        raw_message_callback=None,
    )


@pytest.mark.asyncio
async def test_create_stt_session_routes_mistral_provider_to_mistral_connector():
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
    connect_mistral.assert_awaited_once_with("mistral-test-key")
    connect_soniox.assert_not_called()


@pytest.mark.asyncio
async def test_create_stt_session_rejects_mistral_without_api_key():
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key=None,
        soniox_api_key="unused",
    )

    with pytest.raises(ValueError, match="Mistral API key is required"):
        await create_stt_session(settings, connect_mistral_fn=AsyncMock())


@pytest.mark.asyncio
async def test_create_stt_session_constructs_real_mistral_session_when_configured(
    monkeypatch,
):
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key="mistral-test-key",
        soniox_api_key="unused",
    )
    fake_session = object()
    connect_mistral = AsyncMock(return_value=fake_session)

    monkeypatch.setattr("app.stt_factory.connect_mistral", connect_mistral)

    session = await create_stt_session(settings)

    assert session is fake_session
    connect_mistral.assert_awaited_once_with("mistral-test-key")
