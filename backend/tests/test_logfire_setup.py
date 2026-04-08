from pathlib import Path

from app import logfire_setup


def test_configure_logfire_uses_backend_dotlogfire_dir(monkeypatch):
    monkeypatch.delenv("LOGFIRE_CREDENTIALS_DIR", raising=False)
    captured: dict[str, object] = {}
    instrument_calls: list[str] = []

    monkeypatch.setattr(
        logfire_setup.logfire,
        "configure",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        logfire_setup.logfire,
        "instrument_pydantic_ai",
        lambda: instrument_calls.append("called"),
    )

    logfire_setup.configure_logfire(instrument_pydantic_ai=True)

    assert captured["service_name"] == "voice-todos-backend"
    assert captured["send_to_logfire"] == "if-token-present"
    assert captured["data_dir"] == logfire_setup.BACKEND_ROOT / ".logfire"
    assert instrument_calls == ["called"]


def test_configure_logfire_respects_credentials_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(tmp_path / "shared-logfire"))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        logfire_setup.logfire,
        "configure",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        logfire_setup.logfire,
        "instrument_pydantic_ai",
        lambda: None,
    )

    logfire_setup.configure_logfire()

    assert captured["data_dir"] == Path(tmp_path / "shared-logfire")


def test_configure_logfire_reads_token_from_backend_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOGFIRE_TOKEN=logfire-token-from-env-file\n")
    captured: dict[str, object] = {}

    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.setattr(logfire_setup, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setattr(
        logfire_setup.logfire,
        "configure",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        logfire_setup.logfire,
        "instrument_pydantic_ai",
        lambda: None,
    )

    logfire_setup.configure_logfire()

    assert captured["token"] == "logfire-token-from-env-file"


def test_has_logfire_write_credentials_reads_token_from_backend_env(
    monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    env_file.write_text("LOGFIRE_TOKEN=logfire-token-from-env-file\n")

    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.delenv("LOGFIRE_CREDENTIALS_DIR", raising=False)
    monkeypatch.setattr(logfire_setup, "BACKEND_ENV_PATH", env_file)

    assert logfire_setup.has_logfire_write_credentials() is True


def test_has_logfire_write_credentials_respects_credentials_dir_override(
    monkeypatch, tmp_path
):
    credentials_dir = tmp_path / "shared-logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text("{}\n")

    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))

    assert logfire_setup.has_logfire_write_credentials() is True


def test_has_logfire_write_credentials_returns_false_without_token_or_file(
    monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    credentials_dir = tmp_path / "shared-logfire"

    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.setattr(logfire_setup, "BACKEND_ENV_PATH", env_file)

    assert logfire_setup.has_logfire_write_credentials() is False
