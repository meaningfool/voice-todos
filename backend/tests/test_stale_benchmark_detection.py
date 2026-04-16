from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import run as benchmark_run
from evals.storage import benchmark_lock_path


def _write_benchmark(tmp_path: Path) -> None:
    (tmp_path / "stale_detection.yaml").write_text(
        "\n".join(
            [
                "benchmark_id: stale_detection",
                "hosted_dataset: ds_stale_detection",
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


def _write_lock(lock_path: Path, *, dataset_hash: str) -> None:
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
                    "benchmark_id": "stale_detection",
                    "hosted_dataset": "ds_stale_detection",
                    "hosted_dataset_name": "todo_extraction_v1",
                    "fetched_at": "2026-04-13T16:50:00Z",
                    "dataset_hash": dataset_hash,
                    "hash_algorithm": "sha256",
                    "case_count": 1,
                },
            }
        )
    )


def _exported_payload(*, transcript: str) -> dict:
    return {
        "name": "todo_extraction_v1",
        "cases": [
            {
                "name": "case-a",
                "inputs": {
                    "transcript": transcript,
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


@pytest.mark.asyncio
async def test_stale_run_stops_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(
        benchmark_run, "load_current_benchmark_state", lambda benchmark: benchmark_run.CurrentBenchmarkState()
    )

    lock_path = benchmark_lock_path("stale_detection")
    _write_lock(lock_path, dataset_hash="old-hash")
    monkeypatch.setattr(
        benchmark_run, "export_hosted_dataset", lambda dataset_id: _exported_payload(transcript="Call Mom tonight")
    )

    async def fail_launch(**kwargs):
        pytest.fail("stale benchmark should stop before launching entries")

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fail_launch)

    with pytest.raises(benchmark_run.BenchmarkStaleError):
        await benchmark_run.run_benchmark(
            benchmark_id="stale_detection",
            all_entries=False,
            dataset_path=None,
            allow_untracked=True,
        )
