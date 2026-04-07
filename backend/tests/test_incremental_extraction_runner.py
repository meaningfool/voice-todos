import json
from datetime import UTC, datetime
from importlib import import_module

import pytest
from pydantic_evals.reporting import EvaluationReport, ReportCase, ReportCaseFailure

from app.extract import ExtractionConfig
from app.models import Todo
from evals.extraction_quality.experiment_configs import (
    ExperimentDefinition,
)
from evals.incremental_extraction_quality.models import (
    ReplayRunResult,
    ReplayStep,
    ReplayStepResult,
)


@pytest.mark.asyncio
async def test_run_case_threads_previous_todos_across_steps(monkeypatch):
    runner = import_module("evals.incremental_extraction_quality.run")

    calls: list[dict[str, object]] = []
    step_outputs = {
        "I need to buy milk.": [Todo(text="Buy milk")],
        "I need to buy milk. Actually, buy oat milk instead.": [
            Todo(text="Buy oat milk")
        ],
    }

    async def fake_extract_todos(
        transcript,
        *,
        reference_dt,
        previous_todos,
        config,
    ):
        calls.append(
            {
                "transcript": transcript,
                "reference_dt": reference_dt,
                "previous_todos": previous_todos,
                "config": config,
            }
        )
        return step_outputs[transcript]

    experiment = ExperimentDefinition(
        name="test-experiment",
        extraction_config=ExtractionConfig(model_name="gemini-3-flash-preview"),
        provider="google-gla",
        thinking_mode="provider_default",
    )
    reference_dt = datetime(2026, 3, 24, 9, 30, tzinfo=UTC)
    replay_steps = [
        ReplayStep(step_index=1, transcript="I need to buy milk."),
        ReplayStep(
            step_index=2,
            transcript="I need to buy milk. Actually, buy oat milk instead.",
        ),
    ]

    monkeypatch.setattr(runner, "extract_todos", fake_extract_todos)

    result = await runner._run_case(
        {
            "reference_dt": reference_dt,
            "replay_steps": replay_steps,
        },
        experiment=experiment,
        metadata={"experiment": experiment.name},
    )

    assert calls == [
        {
            "transcript": "I need to buy milk.",
            "reference_dt": reference_dt,
            "previous_todos": None,
            "config": experiment.extraction_config,
        },
        {
            "transcript": "I need to buy milk. Actually, buy oat milk instead.",
            "reference_dt": reference_dt,
            "previous_todos": [Todo(text="Buy milk")],
            "config": experiment.extraction_config,
        },
    ]
    assert result == ReplayRunResult(
        final_todos=[Todo(text="Buy oat milk")],
        step_results=[
            ReplayStepResult(
                step_index=1,
                transcript="I need to buy milk.",
                todos=[Todo(text="Buy milk")],
            ),
            ReplayStepResult(
                step_index=2,
                transcript="I need to buy milk. Actually, buy oat milk instead.",
                todos=[Todo(text="Buy oat milk")],
            ),
        ],
    )


def test_incremental_registry_reuses_shared_experiment_registry():
    incremental_experiment_configs = import_module(
        "evals.incremental_extraction_quality.experiment_configs"
    )
    shared_experiment_configs = import_module(
        "evals.extraction_quality.experiment_configs"
    )

    assert (
        incremental_experiment_configs.EXPERIMENTS
        is shared_experiment_configs.EXPERIMENTS
    )
    assert (
        incremental_experiment_configs.ExperimentDefinition
        is shared_experiment_configs.ExperimentDefinition
    )


def test_list_experiments_output_uses_shared_registry():
    runner = import_module("evals.incremental_extraction_quality.run")
    incremental_experiment_configs = import_module(
        "evals.incremental_extraction_quality.experiment_configs"
    )
    shared_experiment_configs = import_module(
        "evals.extraction_quality.experiment_configs"
    )

    lines = runner.list_experiments_output().splitlines()
    expected_lines = []
    for experiment in shared_experiment_configs.EXPERIMENTS.values():
        unavailable_reason = experiment.unavailable_reason()
        status = (
            "available"
            if unavailable_reason is None
            else f"unavailable ({unavailable_reason})"
        )
        expected_lines.append(f"{experiment.name}\t{status}")

    assert runner.EXPERIMENTS is incremental_experiment_configs.EXPERIMENTS
    assert runner.EXPERIMENTS is shared_experiment_configs.EXPERIMENTS
    assert lines == expected_lines


def test_main_rejects_negative_task_retries():
    runner = import_module("evals.incremental_extraction_quality.run")

    with pytest.raises(SystemExit):
        runner.main(["--all", "--task-retries", "-1"])


def test_write_replay_report_artifact_preserves_step_results(tmp_path):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[
            ReportCase(
                name="refine-todo",
                inputs={
                    "reference_dt": datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
                    "replay_steps": [
                        ReplayStep(step_index=1, transcript="I need to buy milk."),
                        ReplayStep(
                            step_index=2,
                            transcript=(
                                "I need to buy milk. Actually, buy oat milk instead."
                            ),
                        ),
                    ],
                },
                metadata={
                    "dataset": "todo_extraction_replay_v1",
                    "case_type": "incremental_replay",
                    "source_fixture": "refine-todo",
                },
                expected_output=[Todo(text="Buy oat milk")],
                output=ReplayRunResult(
                    final_todos=[Todo(text="Buy oat milk")],
                    step_results=[
                        ReplayStepResult(
                            step_index=1,
                            transcript="I need to buy milk.",
                            todos=[Todo(text="Buy milk")],
                        ),
                        ReplayStepResult(
                            step_index=2,
                            transcript=(
                                "I need to buy milk. Actually, buy oat milk instead."
                            ),
                            todos=[Todo(text="Buy oat milk")],
                        ),
                    ],
                ),
                metrics={
                    "final_todo_count_match": True,
                    "expected_final_todo_count": 1,
                    "predicted_final_todo_count": 1,
                },
                attributes={},
                scores={},
                labels={},
                assertions={},
                task_duration=0.1,
                total_duration=0.2,
                trace_id="case-trace-id",
                span_id="case-span-id",
            )
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_replay_v1",
            "model_name": "gemini-3-flash-preview",
            "provider": "google-gla",
            "thinking_mode": "provider_default",
            "prompt_family": "todo_extraction",
            "prompt_version": "v1",
            "prompt_sha": "prompt-sha-123",
            "git_branch": "codex/item6-5-replay-evals",
            "git_commit_sha": "b18d507",
        },
        trace_id="report-trace-id",
        span_id="report-span-id",
    )

    artifact_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=2,
        max_concurrency=3,
        task_retries=4,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
        serialize_case=import_module(
            "evals.incremental_extraction_quality.run"
        ).serialize_replay_case,
    )

    payload = json.loads(artifact_path.read_text())

    assert payload["timestamp"] == "2026-04-01T16:20:00Z"
    assert payload["dataset_name"] == "todo_extraction_replay_v1"
    assert payload["experiment_id"] == "gemini3_flash_default"
    assert payload["model"] == {
        "name": "gemini-3-flash-preview",
        "provider": "google-gla",
        "thinking_mode": "provider_default",
    }
    assert payload["prompt"] == {
        "family": "todo_extraction",
        "version": "v1",
        "sha": "prompt-sha-123",
    }
    assert payload["git"] == {
        "branch": "codex/item6-5-replay-evals",
        "commit_sha": "b18d507",
    }
    assert payload["repeat"] == 2
    assert payload["max_concurrency"] == 3
    assert payload["task_retries"] == 4
    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 0
    assert payload["overall_case_success_rate"] == 1.0
    assert payload["failure_counts_by_category"] == {}
    assert payload["aggregate_metrics"] == {
        "final_todo_count_match": 1.0,
        "expected_final_todo_count": 1.0,
        "predicted_final_todo_count": 1.0,
    }
    assert payload["cases"] == [
        {
            "name": "refine-todo",
            "source_fixture": "refine-todo",
            "expected_final_todo_count": 1,
            "predicted_final_todo_count": 1,
            "step_results": [
                {
                    "step_index": 1,
                    "transcript": "I need to buy milk.",
                    "todos": [{"text": "Buy milk"}],
                },
                {
                    "step_index": 2,
                    "transcript": "I need to buy milk. Actually, buy oat milk instead.",
                    "todos": [{"text": "Buy oat milk"}],
                },
            ],
            "trace_id": "case-trace-id",
            "span_id": "case-span-id",
        }
    ]
    assert payload["failures"] == []


def test_write_replay_report_artifact_serializes_failures(tmp_path):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")
    runner = import_module("evals.incremental_extraction_quality.run")
    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[],
        failures=[
            ReportCaseFailure(
                name="refine-todo",
                inputs={
                    "reference_dt": datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
                    "replay_steps": [
                        ReplayStep(step_index=1, transcript="I need to buy milk."),
                    ],
                },
                metadata={
                    "dataset": "todo_extraction_replay_v1",
                    "case_type": "incremental_replay",
                    "source_fixture": "refine-todo",
                },
                expected_output=[Todo(text="Buy oat milk")],
                error_message="provider timeout",
                error_stacktrace="Traceback...",
                trace_id="failure-trace-id",
                span_id="failure-span-id",
            )
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_replay_v1",
        },
    )

    artifact_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=1,
        max_concurrency=1,
        task_retries=1,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
        serialize_case=runner.serialize_replay_case,
        serialize_failure=runner.serialize_replay_failure,
    )

    payload = json.loads(artifact_path.read_text())

    assert payload["completed_cases"] == 0
    assert payload["failure_count"] == 1
    assert payload["overall_case_success_rate"] == 0.0
    assert payload["failure_counts_by_category"] == {
        "provider_transport_failure": 1
    }
    assert payload["task_retries"] == 1
    assert payload["failures"] == [
        {
            "name": "refine-todo",
            "source_fixture": "refine-todo",
            "expected_final_todo_count": 1,
            "predicted_final_todo_count": None,
            "error_message": "provider timeout",
            "failure_category": "provider_transport_failure",
            "trace_id": "failure-trace-id",
            "span_id": "failure-span-id",
        }
    ]


@pytest.mark.asyncio
async def test_run_experiment_disables_task_retry_by_default(
    monkeypatch, tmp_path
):
    runner = import_module("evals.incremental_extraction_quality.run")

    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    class FakeDataset:
        name = "todo_extraction_replay_v1"

        async def evaluate(self, task, **kwargs):
            evaluate_calls.append(kwargs)
            return FakeReport()

    monkeypatch.setattr(runner, "_build_eval_dataset", lambda: FakeDataset())
    monkeypatch.setattr(
        runner,
        "_experiment_metadata",
        lambda experiment, dataset_name=None, task_retries=0: {
            "experiment": experiment.name,
            "dataset_name": dataset_name or "unknown",
            "task_retries": task_retries,
        },
    )
    monkeypatch.setattr(
        runner,
        "write_report_artifact",
        lambda report, **kwargs: tmp_path / "artifact.json",
    )

    await runner._run_experiment(
        runner.EXPERIMENTS["gemini3_flash_default"],
        repeat=3,
        max_concurrency=2,
        task_retries=0,
        result_dir=tmp_path,
        artifact_timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert evaluate_calls == [
        {
            "name": "gemini3_flash_default",
            "task_name": "extract_todos_replay",
            "metadata": {
                "experiment": "gemini3_flash_default",
                "dataset_name": "todo_extraction_replay_v1",
                "task_retries": 0,
            },
            "repeat": 3,
            "max_concurrency": 2,
            "retry_task": None,
        }
    ]


@pytest.mark.asyncio
async def test_run_experiment_enables_task_retry_without_changing_repeat(
    monkeypatch, tmp_path
):
    runner = import_module("evals.incremental_extraction_quality.run")

    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    class FakeDataset:
        name = "todo_extraction_replay_v1"

        async def evaluate(self, task, **kwargs):
            evaluate_calls.append(kwargs)
            return FakeReport()

    monkeypatch.setattr(runner, "_build_eval_dataset", lambda: FakeDataset())
    monkeypatch.setattr(
        runner,
        "_experiment_metadata",
        lambda experiment, dataset_name=None, task_retries=0: {
            "experiment": experiment.name,
            "dataset_name": dataset_name or "unknown",
            "task_retries": task_retries,
        },
    )
    monkeypatch.setattr(
        runner,
        "write_report_artifact",
        lambda report, **kwargs: tmp_path / "artifact.json",
    )

    await runner._run_experiment(
        runner.EXPERIMENTS["gemini3_flash_default"],
        repeat=3,
        max_concurrency=2,
        task_retries=2,
        result_dir=tmp_path,
        artifact_timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    retry_task = evaluate_calls[0]["retry_task"]
    assert retry_task is not None
    assert evaluate_calls == [
        {
            "name": "gemini3_flash_default",
            "task_name": "extract_todos_replay",
            "metadata": {
                "experiment": "gemini3_flash_default",
                "dataset_name": "todo_extraction_replay_v1",
                "task_retries": 2,
            },
            "repeat": 3,
            "max_concurrency": 2,
            "retry_task": retry_task,
        }
    ]
