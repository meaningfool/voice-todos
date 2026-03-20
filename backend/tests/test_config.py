import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(monkeypatch):
    """Settings reads SONIOX_API_KEY from environment."""
    monkeypatch.setenv("SONIOX_API_KEY", "test-key-123")

    # Import fresh to pick up the env var
    from app.config import Settings

    s = Settings()  # type: ignore[missing-argument]
    assert s.soniox_api_key == "test-key-123"


def test_settings_requires_api_key(monkeypatch, tmp_path):
    """Settings raises ValidationError when SONIOX_API_KEY is missing."""
    monkeypatch.delenv("SONIOX_API_KEY", raising=False)
    # Point to an empty .env so pydantic-settings can't read the real one
    empty_env = tmp_path / ".env"
    empty_env.write_text("")

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=str(empty_env))  # type: ignore[missing-argument]
