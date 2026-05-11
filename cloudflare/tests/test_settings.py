from __future__ import annotations

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
