from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from stt_factory_cf import create_stt_session


@pytest.mark.asyncio
async def test_create_stt_session_routes_soniox_provider_to_hosted_connector() -> None:
    settings = SimpleNamespace(
        stt_provider="soniox",
        soniox_api_key="soniox-test-key",
    )
    fake_session = object()
    connect_soniox = AsyncMock(return_value=fake_session)
    connect_mistral = AsyncMock()

    session = await create_stt_session(
        settings,
        connect_soniox_fn=connect_soniox,
        connect_mistral_fn=connect_mistral,
    )

    assert session is fake_session
    connect_soniox.assert_awaited_once_with(
        "soniox-test-key",
        raw_message_callback=None,
    )
    connect_mistral.assert_not_called()


@pytest.mark.asyncio
async def test_create_stt_session_rejects_mistral_for_free_tier_public_bundle() -> None:
    settings = SimpleNamespace(
        stt_provider="mistral",
        mistral_api_key="mistral-test-key",
        soniox_api_key="unused",
    )
    connect_mistral = AsyncMock()

    with pytest.raises(
        ValueError,
        match="Hosted Mistral is deferred from the free-tier public Cloudflare bundle",
    ):
        await create_stt_session(settings, connect_mistral_fn=connect_mistral)

    connect_mistral.assert_not_called()
