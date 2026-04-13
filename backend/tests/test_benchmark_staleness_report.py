from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.report import build_benchmark_report
from evals.storage import benchmark_lock_path


def _write_benchmark(tmp_path: Path) -> None:
    (tmp_path / "report_stale.yaml").write_text(
        "\n".join(
            [
                "benchmark_id: report_stale",
                "hosted_dataset: ds_report",
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
                    "benchmark_id": "report_stale",
                    "hosted_dataset": "ds_report",
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


def test_report_marks_benchmark_stale_when_hosted_hash_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_benchmark(tmp_path)
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))
    monkeypatch.setattr("evals.storage.LOCKS_DIR", tmp_path / "locks")

    lock_path = benchmark_lock_path("report_stale")
    _write_lock(lock_path, dataset_hash="old-hash")
    monkeypatch.setattr(
        "evals.report.export_hosted_dataset",
        lambda dataset_id: _exported_payload(transcript="Call Mom tonight"),
    )

    class FakeQueryClient:
        def fetch_candidate_runs(self, selectors):
            return []

    report = build_benchmark_report(
        benchmark_id="report_stale",
        query_client=FakeQueryClient(),
    )

    assert report.stale is True
    assert report.active_lock_path == str(lock_path)
    assert report.locked_dataset_hash == "old-hash"
    assert report.current_hosted_dataset_hash
