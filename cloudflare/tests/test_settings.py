from __future__ import annotations

import os
from types import SimpleNamespace

from settings import get_settings


def test_hosted_settings_default_stop_timeout_seconds_is_30(
    monkeypatch,
) -> None:
    monkeypatch.delenv("STOP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SESSION_CAP_MS", raising=False)

    settings = get_settings(SimpleNamespace())

    assert settings.stop_timeout_seconds == 30.0
    assert settings.session_cap_ms == 60_000


def test_hosted_settings_reads_stop_timeout_seconds_from_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("STOP_TIMEOUT_SECONDS", "12.5")
    monkeypatch.delenv("SESSION_CAP_MS", raising=False)

    settings = get_settings(SimpleNamespace())

    assert settings.stop_timeout_seconds == 12.5


def test_hosted_settings_only_expose_free_tier_public_bundle_secret_fields(
    monkeypatch,
) -> None:
    for name in (
        "SONIOX_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPINFRA_API_KEY",
        "GOOGLE_CLOUD_PROJECT_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings(
        SimpleNamespace(
            SONIOX_API_KEY="soniox-test-key",
            GEMINI_API_KEY="gemini-test-key",
            MISTRAL_API_KEY="mistral-test-key",
            DEEPINFRA_API_KEY="deepinfra-test-key",
            GOOGLE_CLOUD_PROJECT_ID="gcp-test-project",
        )
    )

    assert settings.soniox_api_key == "soniox-test-key"
    assert settings.gemini_api_key == "gemini-test-key"
    assert not hasattr(settings, "mistral_api_key")
    assert not hasattr(settings, "deepinfra_api_key")
    assert not hasattr(settings, "google_cloud_project_id")


def test_hosted_settings_only_mirror_free_tier_public_bundle_secrets(
    monkeypatch,
) -> None:
    for name in (
        "SONIOX_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPINFRA_API_KEY",
        "GOOGLE_CLOUD_PROJECT_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    get_settings(
        SimpleNamespace(
            SONIOX_API_KEY="soniox-test-key",
            GEMINI_API_KEY="gemini-test-key",
            MISTRAL_API_KEY="mistral-test-key",
            DEEPINFRA_API_KEY="deepinfra-test-key",
            GOOGLE_CLOUD_PROJECT_ID="gcp-test-project",
        )
    )

    assert os.environ["SONIOX_API_KEY"] == "soniox-test-key"
    assert os.environ["GEMINI_API_KEY"] == "gemini-test-key"
    assert os.getenv("MISTRAL_API_KEY") is None
    assert os.getenv("DEEPINFRA_API_KEY") is None
    assert os.getenv("GOOGLE_CLOUD_PROJECT_ID") is None
