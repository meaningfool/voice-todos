from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.stt import BoundaryState, SttCapabilities, SttEvent, SttToken
from app.stt_smoke import (
    SmokeResult,
    provider_api_key_env_var,
    run_ws_smoke,
    validate_smoke_result,
)


def test_provider_api_key_env_var_maps_supported_providers():
    assert provider_api_key_env_var("mistral") == "MISTRAL_API_KEY"
    assert provider_api_key_env_var("soniox") == "SONIOX_API_KEY"


def test_provider_api_key_env_var_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported STT provider"):
        provider_api_key_env_var("bogus")


def test_validate_smoke_result_requires_non_empty_final_transcript():
    with pytest.raises(ValueError, match="Final transcript was empty"):
        validate_smoke_result(
            SmokeResult(
                provider="mistral",
                fixture="demo",
                transcript_message_count=1,
                stopped_transcript="",
                warning=None,
                extraction_call_count=1,
            )
        )


def test_validate_smoke_result_requires_at_least_one_transcript_message():
    with pytest.raises(ValueError, match="No transcript messages"):
        validate_smoke_result(
            SmokeResult(
                provider="mistral",
                fixture="demo",
                transcript_message_count=0,
                stopped_transcript="hello",
                warning=None,
                extraction_call_count=1,
            )
        )


def test_run_ws_smoke_streams_audio_and_collects_stopped_transcript(tmp_path: Path):
    audio_path = tmp_path / "audio.pcm"
    audio_path.write_bytes(b"a" * 6400)

    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Stop", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
            SttEvent(
                tokens=[SttToken(text=" now", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
        ],
        final_transcript_text="Stop now",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )

    with (
        patch(
            "app.stt_smoke.TestClient",
            return_value=TestClient(app),
        ),
        patch(
            "app.ws.get_settings",
            return_value=SimpleNamespace(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
                soniox_api_key="unused",
                record_sessions=False,
                soniox_stop_timeout_seconds=30.0,
            ),
        ),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
    ):
        result = run_ws_smoke(
            provider="mistral",
            fixture="demo",
            audio_path=audio_path,
            api_key="mistral-test-key",
            chunk_bytes=3200,
            chunk_delay_ms=0,
        )

    assert result == SmokeResult(
        provider="mistral",
        fixture="demo",
        transcript_message_count=2,
        stopped_transcript="Stop now",
        warning=None,
        extraction_call_count=1,
    )


class _FakeSttSession:
    def __init__(self, events, *, final_transcript_text, capabilities):
        self._events = list(events)
        self.capabilities = capabilities
        self.final_transcript_text = final_transcript_text
        self.send_audio = AsyncMock()
        self.request_final_transcript = AsyncMock()
        self.end_stream = AsyncMock()
        self.wait_for_final_transcript = AsyncMock(return_value=None)
        self.close = AsyncMock()

    async def _iterate(self):
        for event in self._events:
            yield event

    def __aiter__(self):
        return self._iterate()
