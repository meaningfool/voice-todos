import json

from app import backend_env, live_eval_env, repo_env


def test_benchmark_report_skip_reason_reads_shared_files(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOGFIRE_READ_TOKEN=logfire-read-token\n")
    credentials_dir = tmp_path / ".logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text(
        json.dumps({"project_name": "meaningfool/voice-todos"})
    )

    monkeypatch.setattr(backend_env, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.delenv("LOGFIRE_READ_TOKEN", raising=False)
    monkeypatch.delenv("LOGFIRE_PROJECT_NAME", raising=False)
    monkeypatch.delenv("LOGFIRE_PROJECT", raising=False)

    assert live_eval_env.benchmark_report_skip_reason() is None


def test_benchmark_run_skip_reason_requires_explicit_opt_in(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOGFIRE_READ_TOKEN=logfire-read-token\nGEMINI_API_KEY=gemini-key\n"
    )
    credentials_dir = tmp_path / ".logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text(
        json.dumps(
            {
                "project_name": "meaningfool/voice-todos",
                "token": "logfire-write-token",
            }
        )
    )

    monkeypatch.setattr(backend_env, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setattr(repo_env, "REPO_ENV_DEV_PATH", tmp_path / ".env.dev")
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.delenv("ITEM7_ENABLE_LIVE_SMOKE", raising=False)

    assert (
        live_eval_env.benchmark_run_skip_reason()
        == "requires ITEM7_ENABLE_LIVE_SMOKE=1"
    )


def test_benchmark_run_skip_reason_accepts_shared_env_and_logfire_credentials(
    monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOGFIRE_READ_TOKEN=logfire-read-token\nGEMINI_API_KEY=gemini-key\n"
    )
    credentials_dir = tmp_path / ".logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text(
        json.dumps(
            {
                "project_name": "meaningfool/voice-todos",
                "token": "logfire-write-token",
            }
        )
    )

    monkeypatch.setattr(backend_env, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.setenv("ITEM7_ENABLE_LIVE_SMOKE", "1")

    assert live_eval_env.benchmark_run_skip_reason() is None


def test_benchmark_run_skip_reason_falls_back_to_repo_env_dev(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOGFIRE_READ_TOKEN=logfire-read-token\nGEMINI_API_KEY=gemini-key\n"
    )
    credentials_dir = tmp_path / ".logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text(
        json.dumps(
            {
                "project_name": "meaningfool/voice-todos",
                "token": "logfire-write-token",
            }
        )
    )
    env_dev = tmp_path / ".env.dev"
    env_dev.write_text("export ITEM7_ENABLE_LIVE_SMOKE=1\n")

    monkeypatch.setattr(backend_env, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setattr(repo_env, "REPO_ENV_DEV_PATH", env_dev)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.delenv("ITEM7_ENABLE_LIVE_SMOKE", raising=False)

    assert live_eval_env.benchmark_run_skip_reason() is None


def test_exported_live_smoke_flag_overrides_repo_env_dev(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOGFIRE_READ_TOKEN=logfire-read-token\nGEMINI_API_KEY=gemini-key\n"
    )
    credentials_dir = tmp_path / ".logfire"
    credentials_dir.mkdir()
    (credentials_dir / "logfire_credentials.json").write_text(
        json.dumps(
            {
                "project_name": "meaningfool/voice-todos",
                "token": "logfire-write-token",
            }
        )
    )
    env_dev = tmp_path / ".env.dev"
    env_dev.write_text("export ITEM7_ENABLE_LIVE_SMOKE=1\n")

    monkeypatch.setattr(backend_env, "BACKEND_ENV_PATH", env_file)
    monkeypatch.setattr(repo_env, "REPO_ENV_DEV_PATH", env_dev)
    monkeypatch.setenv("LOGFIRE_CREDENTIALS_DIR", str(credentials_dir))
    monkeypatch.setenv("ITEM7_ENABLE_LIVE_SMOKE", "0")

    assert (
        live_eval_env.benchmark_run_skip_reason()
        == "requires ITEM7_ENABLE_LIVE_SMOKE=1"
    )
