from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.benchmarking.models import AxisDefinition, BenchmarkManifest
from evals.benchmarking.storage import (
    attach_experiment,
    load_benchmark_manifest,
    save_benchmark_manifest,
)


def test_load_benchmark_manifest_reads_empty_membership(tmp_path):
    manifest_path = tmp_path / "model_benchmark.json"
    manifest_path.write_text(
        """
{
  "benchmark_id": "todo_model_smoke_v1",
  "title": "Todo extraction smoke model benchmark",
  "suite": "extraction_quality",
  "dataset_name": "todo_extraction_smoke_v1",
  "dataset_sha": "dataset-sha",
  "evaluator_contract_sha": "eval-sha",
  "fixed_config": {"prompt_sha": "prompt-sha"},
  "axes": [
    {"name": "model", "field": "model_name", "values": ["model-a", "model-b"]}
  ],
  "attached_experiment_runs": []
}
""".strip()
    )

    manifest = load_benchmark_manifest(manifest_path)

    assert manifest.benchmark_id == "todo_model_smoke_v1"
    assert manifest.attached_experiment_runs == []


def test_save_benchmark_manifest_round_trips_attachment_refs(tmp_path):
    manifest_path = tmp_path / "model_benchmark.json"
    manifest = load_benchmark_manifest(
        Path("tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json")
    )
    attach_experiment(
        manifest,
        experiment_run_id="batch-123--gemini3_flash_default",
        note="baseline",
    )

    save_benchmark_manifest(manifest_path, manifest)
    reloaded = load_benchmark_manifest(manifest_path)

    assert reloaded.attached_experiment_runs[0].experiment_run_id == (
        "batch-123--gemini3_flash_default"
    )
    assert reloaded.attached_experiment_runs[0].note == "baseline"


def test_attach_experiment_is_idempotent_by_experiment_run_id():
    manifest = load_benchmark_manifest(
        Path("tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json")
    )

    attach_experiment(
        manifest,
        experiment_run_id="batch-123--gemini3_flash_default",
        note="baseline",
    )
    attach_experiment(
        manifest,
        experiment_run_id="batch-123--gemini3_flash_default",
        note="candidate",
    )

    assert len(manifest.attached_experiment_runs) == 1
    assert manifest.attached_experiment_runs[0].experiment_run_id == (
        "batch-123--gemini3_flash_default"
    )
    assert manifest.attached_experiment_runs[0].note == "baseline"


def test_benchmark_manifest_rejects_duplicate_axis_fields():
    with pytest.raises(ValidationError, match="axis.field values must be unique"):
        BenchmarkManifest(
            benchmark_id="todo_model_smoke_v1",
            title="todo model smoke",
            suite="extraction_quality",
            dataset_name="todo_extraction_smoke_v1",
            dataset_sha="dataset-sha",
            evaluator_contract_sha="eval-sha",
            fixed_config={"prompt_sha": "prompt-a"},
            axes=[
                AxisDefinition(
                    name="model",
                    field="model_name",
                    values=["model-a", "model-b"],
                ),
                AxisDefinition(
                    name="baseline",
                    field="model_name",
                    values=["baseline-a", "baseline-b"],
                ),
            ],
        )
