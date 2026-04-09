from evals.benchmarking.coverage import build_benchmark_coverage
from evals.benchmarking.models import (
    AttachedExperimentRef,
    AxisDefinition,
    BenchmarkManifest,
)


def test_build_benchmark_coverage_distinguishes_missing_and_incompatible():
    manifest = BenchmarkManifest(
        benchmark_id="todo_model_smoke_v1",
        title="todo model smoke",
        suite="extraction_quality",
        dataset_name="todo_extraction_smoke_v1",
        dataset_sha="dataset-sha",
        evaluator_contract_sha="eval-sha",
        fixed_config={"prompt_sha": "prompt-a"},
        axes=[AxisDefinition(name="model", field="model_name", values=["model-a", "model-b"])],
        attached_experiment_runs=[
            AttachedExperimentRef(experiment_run_id="run-a"),
            AttachedExperimentRef(experiment_run_id="run-b"),
        ],
    )

    fetched = [
        {
            "experiment_run_id": "run-a",
            "experiment_id": "exp-a",
            "batch_id": "batch-a",
            "suite": "extraction_quality",
            "dataset_sha": "dataset-sha",
            "evaluator_contract_sha": "eval-sha",
            "model_name": "model-a",
            "prompt_sha": "prompt-a",
        },
        {
            "experiment_run_id": "run-b",
            "experiment_id": "exp-b",
            "batch_id": "batch-b",
            "suite": "extraction_quality",
            "dataset_sha": "dataset-sha",
            "evaluator_contract_sha": "eval-sha",
            "model_name": "model-b",
            "prompt_sha": "wrong-prompt",
        },
    ]

    coverage = build_benchmark_coverage(manifest, fetched)

    assert coverage.compatible_count == 1
    assert coverage.incompatible_count == 1
    assert coverage.missing_coordinates == [{"model_name": "model-b"}]


def test_build_benchmark_coverage_tracks_missing_and_unmappable_attachments():
    manifest = BenchmarkManifest(
        benchmark_id="todo_model_smoke_v1",
        title="todo model smoke",
        suite="extraction_quality",
        dataset_name="todo_extraction_smoke_v1",
        dataset_sha="dataset-sha",
        evaluator_contract_sha="eval-sha",
        fixed_config={"prompt_sha": "prompt-a"},
        axes=[AxisDefinition(name="model", field="model_name", values=["model-a", "model-b"])],
        attached_experiment_runs=[
            AttachedExperimentRef(experiment_run_id="run-a"),
            AttachedExperimentRef(experiment_run_id="run-c"),
            AttachedExperimentRef(experiment_run_id="run-d"),
        ],
    )

    fetched = [
        {
            "experiment_run_id": "run-a",
            "experiment_id": "exp-a",
            "batch_id": "batch-a",
            "suite": "extraction_quality",
            "dataset_sha": "dataset-sha",
            "evaluator_contract_sha": "eval-sha",
            "model_name": "model-a",
            "prompt_sha": "prompt-a",
        },
        {
            "experiment_run_id": "run-c",
            "experiment_id": "exp-c",
            "batch_id": "batch-c",
            "suite": "extraction_quality",
            "dataset_sha": "dataset-sha",
            "evaluator_contract_sha": "eval-sha",
            "model_name": "model-c",
            "prompt_sha": "prompt-a",
        },
    ]

    coverage = build_benchmark_coverage(manifest, fetched)

    assert coverage.compatible_experiment_run_ids == ["run-a"]
    assert coverage.incompatible_experiment_run_ids == []
    assert coverage.unmappable_experiment_run_ids == ["run-c"]
    assert coverage.missing_attached_experiment_run_ids == ["run-d"]
    assert coverage.missing_coordinates == [{"model_name": "model-b"}]
