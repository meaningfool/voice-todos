import pytest
from pydantic import ValidationError

import app.config as config_module


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    config_module.get_settings.cache_clear()
    yield
    config_module.get_settings.cache_clear()


def test_settings_loads_from_env(monkeypatch, tmp_path):
    """Settings reads required keys and defaults optional flags."""
    monkeypatch.setenv("SONIOX_API_KEY", "test-key-123")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-456")
    monkeypatch.delenv("RECORD_SESSIONS", raising=False)
    monkeypatch.delenv("SONIOX_STOP_TIMEOUT_SECONDS", raising=False)

    # Point to an empty .env so local developer settings do not affect the test.
    env_file = tmp_path / ".env"
    env_file.write_text("")

    from app.config import Settings

    s = Settings(_env_file=str(env_file))
    assert s.soniox_api_key == "test-key-123"
    assert s.gemini_api_key == "gemini-key-456"
    assert s.record_sessions is False
    assert s.soniox_stop_timeout_seconds == 30.0


def test_settings_requires_api_key(monkeypatch, tmp_path):
    """Settings raises ValidationError when required keys are missing."""
    monkeypatch.delenv("SONIOX_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Point to an empty .env so pydantic-settings can't read the real one
    empty_env = tmp_path / ".env"
    empty_env.write_text("")

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=str(empty_env))


def test_settings_loads_gemini_key(monkeypatch, tmp_path):
    """Settings reads GEMINI_API_KEY from environment."""
    monkeypatch.setenv("SONIOX_API_KEY", "soniox-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("RECORD_SESSIONS", raising=False)
    monkeypatch.delenv("SONIOX_STOP_TIMEOUT_SECONDS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("")

    from app.config import Settings

    s = Settings(_env_file=str(env_file))
    assert s.gemini_api_key == "gemini-test-key"


def test_settings_default_stt_provider_to_soniox(monkeypatch, tmp_path):
    monkeypatch.setenv("SONIOX_API_KEY", "soniox-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    env_file = tmp_path / ".env"
    env_file.write_text("")

    from app.config import Settings

    s = Settings(_env_file=str(env_file))
    assert s.stt_provider == "soniox"


def test_settings_default_optional_future_stt_keys_to_none(monkeypatch, tmp_path):
    monkeypatch.setenv("SONIOX_API_KEY", "soniox-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("")

    from app.config import Settings

    s = Settings(_env_file=str(env_file))
    assert s.google_cloud_project_id is None
    assert s.mistral_api_key is None


def test_settings_ignores_unrelated_env_file_keys(monkeypatch, tmp_path):
    """Settings should ignore extra keys that share the developer .env file."""
    monkeypatch.delenv("SONIOX_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("RECORD_SESSIONS", raising=False)
    monkeypatch.delenv("SONIOX_STOP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LOGFIRE_READ_TOKEN", raising=False)
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SONIOX_API_KEY=test-key-123",
                "GEMINI_API_KEY=gemini-key-456",
                "DEEPINFRA_API_KEY=ignored",
                "LOGFIRE_READ_TOKEN=ignored",
                "MISTRAL_API_KEY=ignored",
            ]
        )
    )

    from app.config import Settings

    s = Settings(_env_file=str(env_file))
    assert s.soniox_api_key == "test-key-123"
    assert s.gemini_api_key == "gemini-key-456"
