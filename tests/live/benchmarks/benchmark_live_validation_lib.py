from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.backend_env import read_backend_env_var
from evals.hosted_datasets import build_logfire_api_client
from evals.storage import benchmark_lock_path


def available_entry_definition() -> dict:
    if read_backend_env_var("GEMINI_API_KEY"):
        return {
            "id": "gemini31_flash_lite_default",
            "label": "Gemini 3.1 Flash-Lite / default",
            "config": {
                "provider": "google-gla",
                "model": "gemini-3.1-flash-lite-preview",
                "prompt_version": "v1",
                "model_settings": {},
            },
        }
    if read_backend_env_var("MISTRAL_API_KEY"):
        return {
            "id": "mistral_small_4_default",
            "label": "Mistral Small 4 / default",
            "config": {
                "provider": "mistral",
                "model": "mistral-small-2603",
                "prompt_version": "v1",
                "model_settings": {},
            },
        }
    if read_backend_env_var("DEEPINFRA_API_KEY"):
        return {
            "id": "deepinfra_qwen35_4b_structured_tuned",
            "label": "Qwen 3.5 4B / structured tuned",
            "config": {
                "provider": "deepinfra",
                "model": "Qwen/Qwen3.5-4B",
                "prompt_version": "v1",
                "model_settings": {
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            },
        }
    raise RuntimeError("No supported provider credential available")


def create_temp_hosted_dataset(*, transcript: str) -> tuple[object, str, str]:
    client = build_logfire_api_client()
    suffix = uuid.uuid4().hex[:8]
    dataset_name = f"benchmark_live_validation_{suffix}"
    dataset = client.create_dataset(
        dataset_name,
        description=f"Temporary benchmark live validation dataset {suffix}",
    )
    dataset_id = dataset["id"]
    client.add_cases(
        dataset_id,
        [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": transcript,
                    "reference_dt": "2026-03-24T09:30:00+00:00",
                    "previous_todos": None,
                },
                "expected_output": {"todos": [{"text": "Call Mom"}]},
                "metadata": {"source_fixture": "benchmark-live-validation"},
            }
        ],
        on_conflict="update",
    )
    return client, dataset_id, dataset_name


def mutate_temp_hosted_dataset(*, client, dataset_id: str, transcript: str) -> None:
    client.add_cases(
        dataset_id,
        [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": transcript,
                    "reference_dt": "2026-03-24T09:30:00+00:00",
                    "previous_todos": None,
                },
                "expected_output": {"todos": [{"text": "Call Mom"}]},
                "metadata": {"source_fixture": "benchmark-live-validation"},
            }
        ],
        on_conflict="update",
    )


def write_temp_benchmark(
    *,
    benchmark_id: str,
    hosted_dataset: str,
    entry: dict,
) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tempdir = tempfile.TemporaryDirectory(prefix="benchmark-live-")
    benchmark_dir = Path(tempdir.name)
    payload = {
        "benchmark_id": benchmark_id,
        "hosted_dataset": hosted_dataset,
        "dataset_family": "extraction",
        "focus": "model",
        "headline_metric": "todo_count_match",
        "repeat": 1,
        "task_retries": 1,
        "max_concurrency": 1,
        "entries": [entry],
    }
    benchmark_path = benchmark_dir / f"{benchmark_id}.yaml"
    benchmark_path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return tempdir, benchmark_path


def run_benchmark_run_cli(
    *, benchmark_id: str, args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return _run_benchmark_cli(command="run", benchmark_id=benchmark_id, args=args)


def run_benchmark_report_cli(
    *,
    benchmark_id: str,
    json_output: bool = False,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_args = list(args or [])
    if json_output:
        command_args.append("--json")
    return _run_benchmark_cli(
        command="report",
        benchmark_id=benchmark_id,
        args=command_args,
    )


def remove_lock_if_present(benchmark_id: str) -> None:
    path = benchmark_lock_path(benchmark_id)
    if path.exists():
        path.unlink()


def cleanup_dataset(client, dataset_id: str, benchmark_id: str, tempdir: tempfile.TemporaryDirectory[str]) -> None:
    try:
        client.delete_dataset(dataset_id)
    except Exception:
        pass
    remove_lock_if_present(benchmark_id)
    tempdir.cleanup()


def load_lock_payload(benchmark_id: str) -> dict:
    return json.loads(benchmark_lock_path(benchmark_id).read_text())


def _run_benchmark_cli(
    *,
    command: str,
    benchmark_id: str,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    cli_command = [sys.executable, "../evals/cli.py", "benchmark", command, benchmark_id]
    if args:
        cli_command.extend(args)
    return subprocess.run(
        cli_command,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
