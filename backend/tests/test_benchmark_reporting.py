import pytest

from evals.benchmarking.models import (
    AttachedExperimentRef,
    AxisDefinition,
    BenchmarkManifest,
)
from evals.benchmarking.reporting import (
    build_benchmark_report,
    build_benchmark_report_async,
)


def _build_manifest(*, attached_run_ids: list[str]) -> BenchmarkManifest:
    return BenchmarkManifest(
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
            )
        ],
        attached_experiment_runs=[
            AttachedExperimentRef(experiment_run_id=run_id)
            for run_id in attached_run_ids
        ],
    )


class FakeQueryClient:
    def __init__(self, records):
        self.records = records
        self.seen_attachments: list[str] = []

    def fetch_attached_experiments(self, attachments):
        self.seen_attachments = [
            attachment.experiment_run_id
            for attachment in attachments
        ]
        return self.records


class AsyncFakeQueryClient(FakeQueryClient):
    async def fetch_attached_experiments(self, attachments):
        return super().fetch_attached_experiments(attachments)


def test_report_uses_only_attached_experiments():
    manifest = _build_manifest(attached_run_ids=["run-a"])
    query_client = FakeQueryClient(
        [
            {
                "experiment_run_id": "run-a",
                "experiment_id": "exp-a",
                "batch_id": "batch-a",
                "suite": "extraction_quality",
                "dataset_sha": "dataset-sha",
                "evaluator_contract_sha": "eval-sha",
                "model_name": "model-a",
                "prompt_sha": "prompt-a",
            }
        ]
    )

    report = build_benchmark_report(
        manifest=manifest,
        query_client=query_client,
    )

    assert query_client.seen_attachments == ["run-a"]
    assert report.compatible_experiments == ["run-a"]
    assert report.unattached_candidates == []


def test_report_surfaces_incompatible_and_missing_attached_experiments():
    manifest = _build_manifest(attached_run_ids=["run-a", "run-b", "run-c"])
    query_client = FakeQueryClient(
        [
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
    )

    report = build_benchmark_report(
        manifest=manifest,
        query_client=query_client,
    )

    assert report.compatible_experiments == ["run-a"]
    assert report.incompatible_experiments == ["run-b"]
    assert report.missing_attached_experiments == ["run-c"]
    assert report.missing_coordinates == [{"model_name": "model-b"}]


def test_report_deduplicates_duplicate_rows_by_experiment_run_id():
    manifest = _build_manifest(attached_run_ids=["run-a"])
    query_client = FakeQueryClient(
        [
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
                "experiment_run_id": "run-a",
                "experiment_id": "exp-a",
                "batch_id": "batch-a",
                "suite": "extraction_quality",
                "dataset_sha": "dataset-sha",
                "evaluator_contract_sha": "eval-sha",
                "model_name": "model-a",
                "prompt_sha": "wrong-prompt",
            },
        ]
    )

    report = build_benchmark_report(
        manifest=manifest,
        query_client=query_client,
    )

    assert report.compatible_experiments == ["run-a"]
    assert report.incompatible_experiments == []


@pytest.mark.asyncio
async def test_async_report_supports_async_query_clients():
    manifest = _build_manifest(attached_run_ids=["run-a"])
    query_client = AsyncFakeQueryClient(
        [
            {
                "experiment_run_id": "run-a",
                "experiment_id": "exp-a",
                "batch_id": "batch-a",
                "suite": "extraction_quality",
                "dataset_sha": "dataset-sha",
                "evaluator_contract_sha": "eval-sha",
                "model_name": "model-a",
                "prompt_sha": "prompt-a",
            }
        ]
    )

    report = await build_benchmark_report_async(
        manifest=manifest,
        query_client=query_client,
    )

    assert report.compatible_experiments == ["run-a"]
