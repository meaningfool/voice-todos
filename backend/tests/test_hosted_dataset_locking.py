from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import run as benchmark_run
from evals.hosted_datasets import canonical_dataset_hash
from evals.storage import benchmark_lock_path


def _write_benchmark(tmp_path: Path) -> Path:
    benchmark_path = tmp_path / "first_run_locking.yaml"
    benchmark_path.write_text(
        "\n".join(
            [
                "benchmark_id: first_run_locking",
                "hosted_dataset: ds_first_run",
                "dataset_family: extraction",
                "focus: model",
                "headline_metric: todo_count_match",
                "repeat: 1",
                "task_retries: 1",
                "max_concurrency: 1",
                "entries:",
                "  - id: gemini3_flash_default",
                "    label: Gemini 3 Flash / default",
                "    config:",
                "      provider: google-gla",
                "      model: gemini-3-flash-preview",
                "      prompt_version: v1",
                "      model_settings: {}",
            ]
        )
    )
    return benchmark_path


@pytest.mark.asyncio
async def test_run_benchmark_creates_lock_on_first_run_and_uses_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(benchmark_run, "load_current_benchmark_state", lambda benchmark: benchmark_run.CurrentBenchmarkState())

    exported_payload = {
        "name": "todo_extraction_v1",
        "cases": [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": "Call Mom",
                    "reference_dt": "2026-03-24T09:30:00+00:00",
                    "previous_todos": None,
                },
                "expected_output": {"todos": [{"text": "Call Mom"}]},
                "metadata": {"source_fixture": "fixture-a"},
                "evaluators": [],
            }
        ],
        "evaluators": [],
    }
    export_calls: list[str] = []
    launched: list[Path] = []

    monkeypatch.setattr(
        benchmark_run,
        "export_hosted_dataset",
        lambda dataset_id: export_calls.append(dataset_id) or exported_payload,
    )

    async def fake_launch_extraction_entry(**kwargs):
        launched.append(kwargs["dataset_path"])
        return {"batch_id": "batch-1"}

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fake_launch_extraction_entry)

    result = await benchmark_run.run_benchmark(
        benchmark_id="first_run_locking",
        all_entries=False,
        dataset_path=None,
        allow_untracked=True,
    )

    lock_path = benchmark_lock_path("first_run_locking")
    assert result.executed_entry_ids == ["gemini3_flash_default"]
    assert export_calls == ["ds_first_run"]
    assert launched == [lock_path]
    lock_payload = json.loads(lock_path.read_text())
    assert lock_payload["name"] == "todo_extraction"
    assert lock_payload["version"] == "v1"
    assert lock_payload["rows"][0]["expected_output"] == [{"text": "Call Mom"}]
    assert lock_payload["_benchmark_lock"]["hosted_dataset"] == "ds_first_run"


@pytest.mark.asyncio
async def test_run_benchmark_reuses_existing_lock_when_hosted_hash_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(benchmark_run, "load_current_benchmark_state", lambda benchmark: benchmark_run.CurrentBenchmarkState())

    exported_payload = {
        "name": "todo_extraction_v1",
        "cases": [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": "Call Mom",
                    "reference_dt": "2026-03-24T09:30:00+00:00",
                    "previous_todos": None,
                },
                "expected_output": {"todos": [{"text": "Call Mom"}]},
                "metadata": {"source_fixture": "fixture-a"},
                "evaluators": [],
            }
        ],
        "evaluators": [],
    }

    lock_path = benchmark_lock_path("first_run_locking")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "name": "todo_extraction",
                "version": "v1",
                "rows": [
                    {
                        "id": "case-a",
                        "input": {
                            "transcript": "Call Mom",
                            "reference_dt": "2026-03-24T09:30:00+00:00",
                            "previous_todos": None,
                        },
                        "expected_output": [{"text": "Call Mom"}],
                        "metadata": {"source_fixture": "fixture-a"},
                    }
                ],
                "_benchmark_lock": {
                    "benchmark_id": "first_run_locking",
                    "hosted_dataset": "ds_first_run",
                    "hosted_dataset_name": "todo_extraction_v1",
                    "fetched_at": "2026-04-13T16:50:00Z",
                    "dataset_hash": canonical_dataset_hash(exported_payload),
                    "hash_algorithm": "sha256",
                    "case_count": 1,
                },
            }
        )
    )

    export_calls: list[str] = []
    monkeypatch.setattr(
        benchmark_run,
        "export_hosted_dataset",
        lambda dataset_id: export_calls.append(dataset_id) or exported_payload,
    )

    launched: list[Path] = []

    async def fake_launch_extraction_entry(**kwargs):
        launched.append(kwargs["dataset_path"])
        return {"batch_id": "batch-1"}

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fake_launch_extraction_entry)

    result = await benchmark_run.run_benchmark(
        benchmark_id="first_run_locking",
        all_entries=False,
        dataset_path=None,
        allow_untracked=True,
    )

    assert result.executed_entry_ids == ["gemini3_flash_default"]
    assert export_calls == ["ds_first_run"]
    assert launched == [lock_path]


@pytest.mark.asyncio
async def test_run_benchmark_reuses_existing_lock_when_export_wrapper_hash_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(
        benchmark_run,
        "load_current_benchmark_state",
        lambda benchmark: benchmark_run.CurrentBenchmarkState(),
    )

    exported_payload = {
        "name": "todo_extraction_v1",
        "cases": [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": "Call Mom",
                    "reference_dt": "2026-03-24T09:30:00+00:00",
                    "previous_todos": None,
                },
                "expected_output": {"todos": [{"text": "Call Mom"}]},
                "metadata": {"source_fixture": "fixture-a"},
                "evaluators": [],
            }
        ],
        "evaluators": [],
        "report_evaluators": [],
    }

    lock_path = benchmark_lock_path("first_run_locking")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "name": "todo_extraction",
                "version": "v1",
                "rows": [
                    {
                        "id": "case-a",
                        "input": {
                            "transcript": "Call Mom",
                            "reference_dt": "2026-03-24T09:30:00+00:00",
                            "previous_todos": None,
                        },
                        "expected_output": [{"text": "Call Mom"}],
                        "metadata": {"source_fixture": "fixture-a"},
                    }
                ],
                "_benchmark_lock": {
                    "benchmark_id": "first_run_locking",
                    "hosted_dataset": "ds_first_run",
                    "hosted_dataset_name": "todo_extraction_v1",
                    "fetched_at": "2026-04-13T16:50:00Z",
                    "dataset_hash": "older-raw-export-hash",
                    "hash_algorithm": "sha256",
                    "case_count": 1,
                },
            }
        )
    )

    export_calls: list[str] = []
    monkeypatch.setattr(
        benchmark_run,
        "export_hosted_dataset",
        lambda dataset_id: export_calls.append(dataset_id) or exported_payload,
    )

    launched: list[Path] = []

    async def fake_launch_extraction_entry(**kwargs):
        launched.append(kwargs["dataset_path"])
        return {"batch_id": "batch-1"}

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fake_launch_extraction_entry)

    result = await benchmark_run.run_benchmark(
        benchmark_id="first_run_locking",
        all_entries=False,
        dataset_path=None,
        allow_untracked=True,
    )

    assert result.executed_entry_ids == ["gemini3_flash_default"]
    assert export_calls == ["ds_first_run"]
    assert launched == [lock_path]
