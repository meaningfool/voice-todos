from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import run as benchmark_run
from evals.storage import benchmark_lock_path


def _write_benchmark(tmp_path: Path) -> None:
    (tmp_path / "stale_actions.yaml").write_text(
        "\n".join(
            [
                "benchmark_id: stale_actions",
                "hosted_dataset: ds_stale_actions",
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
                "  - id: mistral_small_4_default",
                "    label: Mistral Small 4 / default",
                "    config:",
                "      provider: mistral",
                "      model: mistral-small-2603",
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
                    "benchmark_id": "stale_actions",
                    "hosted_dataset": "ds_stale_actions",
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
async def test_allow_stale_runs_against_existing_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(
        benchmark_run, "load_current_benchmark_state", lambda benchmark: benchmark_run.CurrentBenchmarkState()
    )

    lock_path = benchmark_lock_path("stale_actions")
    _write_lock(lock_path, dataset_hash="old-hash")
    monkeypatch.setattr(
        benchmark_run, "export_hosted_dataset", lambda dataset_id: _exported_payload(transcript="Changed transcript")
    )

    launched: list[Path] = []

    async def fake_launch_extraction_entry(**kwargs):
        launched.append(kwargs["dataset_path"])
        return {"batch_id": "batch-1"}

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fake_launch_extraction_entry)

    result = await benchmark_run.run_benchmark(
        benchmark_id="stale_actions",
        all_entries=False,
        dataset_path=None,
        allow_untracked=True,
        allow_stale=True,
    )

    assert result.executed_entry_ids == ["gemini3_flash_default", "mistral_small_4_default"]
    assert launched == [lock_path, lock_path]


@pytest.mark.asyncio
async def test_rebase_rewrites_lock_and_executes_all_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(
        benchmark_run,
        "load_current_benchmark_state",
        lambda benchmark: benchmark_run.CurrentBenchmarkState(current_entry_ids={"gemini3_flash_default"}),
    )

    lock_path = benchmark_lock_path("stale_actions")
    _write_lock(lock_path, dataset_hash="old-hash")
    monkeypatch.setattr(
        benchmark_run, "export_hosted_dataset", lambda dataset_id: _exported_payload(transcript="Changed transcript")
    )

    launched_extraction: list[Path] = []
    launched_replay: list[Path] = []

    async def fake_launch_extraction_entry(**kwargs):
        launched_extraction.append(kwargs["dataset_path"])
        return {"batch_id": "batch-1"}

    async def fake_launch_replay_entry(**kwargs):
        launched_replay.append(kwargs["dataset_path"])
        return {"batch_id": "batch-2"}

    monkeypatch.setattr(benchmark_run, "launch_extraction_entry", fake_launch_extraction_entry)
    monkeypatch.setattr(benchmark_run, "launch_replay_entry", fake_launch_replay_entry)

    result = await benchmark_run.run_benchmark(
        benchmark_id="stale_actions",
        all_entries=False,
        dataset_path=None,
        allow_untracked=True,
        rebase=True,
    )

    lock_payload = json.loads(lock_path.read_text())
    assert result.executed_entry_ids == ["gemini3_flash_default", "mistral_small_4_default"]
    assert launched_extraction == [lock_path, lock_path]
    assert launched_replay == []
    assert lock_payload["_benchmark_lock"]["dataset_hash"] != "old-hash"
    assert lock_payload["rows"][0]["input"]["transcript"] == "Changed transcript"
