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
