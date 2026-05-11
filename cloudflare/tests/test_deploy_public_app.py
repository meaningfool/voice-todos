from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "deploy_public_app.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("deploy_public_app", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module spec for {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_required_secrets_reads_only_public_provider_keys(
    tmp_path: Path,
) -> None:
    module = _load_module()
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "SONIOX_API_KEY=s\n"
        "GEMINI_API_KEY=g\n"
        "MISTRAL_API_KEY=m\n"
        "LOGFIRE_TOKEN=ignored\n"
    )

    assert module.collect_required_secrets(env_file) == {
        "SONIOX_API_KEY": "s",
        "GEMINI_API_KEY": "g",
        "MISTRAL_API_KEY": "m",
    }


def test_collect_required_secrets_rejects_missing_required_key(
    tmp_path: Path,
) -> None:
    module = _load_module()
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "SONIOX_API_KEY=s\n"
        "GEMINI_API_KEY=g\n"
    )

    with pytest.raises(ValueError, match="Missing required secrets"):
        module.collect_required_secrets(env_file)


def test_build_deploy_command_uses_public_domain_and_explicit_runtime_vars() -> None:
    module = _load_module()

    command = module.build_deploy_command(
        public_domain="voice-todos.example.com",
        secrets_file=Path("/tmp/public.secrets.env"),
        session_cap_ms="65000",
        stop_timeout_seconds="12",
    )

    assert command[:4] == ["uv", "run", "pywrangler", "deploy"]
    assert "--domain" in command
    assert "voice-todos.example.com" in command
    assert "--secrets-file" in command
    assert "/tmp/public.secrets.env" in command
    assert "--var" in command
    assert "STT_PROVIDER=soniox" in command
    assert "SESSION_CAP_MS=65000" in command
    assert "STOP_TIMEOUT_SECONDS=12" in command


def test_build_deploy_command_omits_optional_runtime_vars_when_absent() -> None:
    module = _load_module()

    command = module.build_deploy_command(
        public_domain="voice-todos.example.com",
        secrets_file=Path("/tmp/public.secrets.env"),
        session_cap_ms=None,
        stop_timeout_seconds=None,
    )

    assert "STT_PROVIDER=soniox" in command
    assert not any(arg.startswith("SESSION_CAP_MS=") for arg in command)
    assert not any(arg.startswith("STOP_TIMEOUT_SECONDS=") for arg in command)
