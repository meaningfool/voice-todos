import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest
from pydantic_evals.reporting import EvaluationReport, ReportCase, ReportCaseFailure

from app.models import Todo
from app.prompts.registry import PromptRef
from evals.extraction_quality import experiment_configs
from evals.extraction_quality.experiment_configs import EXPERIMENTS
from evals.extraction_quality.run import _experiment_metadata, main

EXPECTED_EXPERIMENTS = [
    "gemini3_flash_default",
    "gemini3_flash_minimal_thinking",
    "gemini31_flash_lite_default",
    "gemini31_flash_lite_minimal_thinking",
    "mistral_small_4_default",
]


def test_experiment_registry_contains_expected_names():
    assert list(EXPERIMENTS) == EXPECTED_EXPERIMENTS


def test_main_list_experiments_prints_registry(capsys):
    exit_code = main(["--list-experiments"])
    captured = capsys.readouterr()

    assert exit_code == 0
    for experiment_name in EXPECTED_EXPERIMENTS:
        assert experiment_name in captured.out


def test_main_rejects_negative_task_retries():
    runner = import_module("evals.extraction_quality.run")

    with pytest.raises(SystemExit):
        runner.main(["--all", "--task-retries", "-1"])


def test_mistral_experiment_reports_provider_unavailability(monkeypatch):
    monkeypatch.setattr(
        experiment_configs,
        "_mistral_unavailable_reason",
        lambda: "mistral provider unavailable",
    )

    assert (
        EXPERIMENTS["mistral_small_4_default"].unavailable_reason()
        == "mistral provider unavailable"
    )


def test_experiment_metadata_includes_prompt_identity(monkeypatch):
    prompt_ref = PromptRef(
        family="todo_extraction",
        version="v1",
        path=Path("/tmp/todo_extraction_v1.md"),
        content="prompt body",
        sha256="prompt-sha-123",
    )

    monkeypatch.setattr(
        "evals.extraction_quality.experiment_configs.get_extraction_prompt_ref",
        lambda config: prompt_ref,
    )
    monkeypatch.setattr(
        "evals.extraction_quality.run._get_git_branch",
        lambda: "codex/item6-extraction-model-evals",
        raising=False,
    )
    monkeypatch.setattr(
        "evals.extraction_quality.run._get_git_commit_sha",
        lambda: "65218795562767602eb8d5f9103eebfd9998cbec",
        raising=False,
    )

    metadata = _experiment_metadata(
        EXPERIMENTS["gemini3_flash_default"],
        dataset_name="todo_extraction_v1",
    )

    assert metadata["dataset_name"] == "todo_extraction_v1"
    assert metadata["prompt_family"] == "todo_extraction"
    assert metadata["prompt_version"] == "v1"
    assert metadata["prompt_sha"] == "prompt-sha-123"
    assert metadata["git_branch"] == "codex/item6-extraction-model-evals"
    assert metadata["git_commit_sha"] == "65218795562767602eb8d5f9103eebfd9998cbec"
    assert metadata["task_retries"] == 0


def test_main_configures_logfire_before_running_experiments(monkeypatch, tmp_path):
    import evals.extraction_quality.run as runner

    events: list[tuple[str, object]] = []
    result_dir = tmp_path / "results"
    artifact_paths = {
        "fake-experiment-a": result_dir / "artifact-a.json",
        "fake-experiment-b": result_dir / "artifact-b.json",
    }

    class FakeExperiment:
        def __init__(self, name: str):
            self.name = name

        def unavailable_reason(self) -> None:
            return None

    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: [
            FakeExperiment("fake-experiment-a"),
            FakeExperiment("fake-experiment-b"),
        ],
    )
    monkeypatch.setattr(
        runner,
        "reserve_result_dir",
        lambda **kwargs: result_dir,
    )
    monkeypatch.setattr(
        runner,
        "configure_logfire",
        lambda **kwargs: events.append(("configure", kwargs)),
    )
    monkeypatch.setattr(
        runner,
        "enrich_experiment_artifacts",
        lambda **kwargs: pytest.fail("enrichment should be skipped"),
    )

    async def fake_run_experiment(
        experiment,
        *,
        repeat,
        task_retries,
        max_concurrency,
        result_dir,
        artifact_timestamp,
    ) -> Path:
        events.append(("run", experiment.name))
        return artifact_paths[experiment.name]

    monkeypatch.setattr(runner, "_run_experiment", fake_run_experiment)

    exit_code = runner.main(
        [
            "--experiment",
            "fake-experiment",
            "--output-dir",
            str(tmp_path),
            "--skip-logfire-enrichment",
        ]
    )

    assert exit_code == 0
    assert events == [
        (
            "configure",
            {
                "service_name": "voice-todos-backend",
                "instrument_pydantic_ai": True,
            },
        ),
        ("run", "fake-experiment-a"),
        ("run", "fake-experiment-b"),
    ]


@pytest.mark.asyncio
async def test_enrich_experiment_artifacts_forwards_read_token(
    monkeypatch, tmp_path
):
    runner = import_module("evals.extraction_quality.run")

    calls: list[tuple[Path, str | None]] = []

    async def fake_enrich_experiment_artifact(
        artifact_path,
        *,
        read_token=None,
    ):
        calls.append((artifact_path, read_token))
        return {"artifact_path": artifact_path.name, "read_token": read_token}

    monkeypatch.setattr(
        runner.logfire_enrichment,
        "enrich_experiment_artifact",
        fake_enrich_experiment_artifact,
    )

    artifact_paths = [
        tmp_path / "artifact-a.json",
        tmp_path / "artifact-b.json",
    ]

    results = await runner.enrich_experiment_artifacts(
        artifact_paths=artifact_paths,
        read_token="read-token",
    )

    assert calls == [
        (artifact_paths[0], "read-token"),
        (artifact_paths[1], "read-token"),
    ]
    assert results == [
        {"artifact_path": "artifact-a.json", "read_token": "read-token"},
        {"artifact_path": "artifact-b.json", "read_token": "read-token"},
    ]


def test_main_attempts_enrichment_after_experiments_and_ignores_failures(
    monkeypatch, tmp_path, capsys
):
    import evals.extraction_quality.run as runner

    events: list[tuple[str, object]] = []
    result_dir = tmp_path / "results"
    artifact_paths = {
        "fake-experiment-a": result_dir / "artifact-a.json",
        "fake-experiment-b": result_dir / "artifact-b.json",
    }

    class FakeExperiment:
        def __init__(self, name: str):
            self.name = name

        def unavailable_reason(self) -> None:
            return None

    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: [
            FakeExperiment("fake-experiment-a"),
            FakeExperiment("fake-experiment-b"),
        ],
    )
    monkeypatch.setattr(
        runner,
        "reserve_result_dir",
        lambda **kwargs: result_dir,
    )
    monkeypatch.setattr(
        runner,
        "configure_logfire",
        lambda **kwargs: events.append(("configure", kwargs)),
    )

    async def fake_run_experiment(
        experiment,
        *,
        repeat,
        task_retries,
        max_concurrency,
        result_dir,
        artifact_timestamp,
    ) -> Path:
        events.append(("run", experiment.name))
        return artifact_paths[experiment.name]

    async def fake_enrich_run_artifacts(
        *,
        artifact_paths,
        read_token=None,
    ):
        events.append(
            (
                "enrichment",
                {
                    "artifact_paths": list(artifact_paths),
                    "read_token": read_token,
                },
            )
        )
        raise RuntimeError("enrichment failed")

    monkeypatch.setattr(runner, "_run_experiment", fake_run_experiment)
    monkeypatch.setattr(
        runner, "enrich_experiment_artifacts", fake_enrich_run_artifacts
    )

    exit_code = runner.main(
        ["--experiment", "fake-experiment-a", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert events == [
        (
            "configure",
            {
                "service_name": "voice-todos-backend",
                "instrument_pydantic_ai": True,
            },
        ),
        ("run", "fake-experiment-a"),
        ("run", "fake-experiment-b"),
        (
            "enrichment",
            {
                "artifact_paths": [
                    artifact_paths["fake-experiment-a"],
                    artifact_paths["fake-experiment-b"],
                ],
                "read_token": None,
            },
        ),
    ]
    assert "Best-effort Logfire enrichment failed: enrichment failed" in captured.err


def test_main_skip_logfire_enrichment_disables_enrichment_pass(
    monkeypatch, tmp_path
):
    import evals.extraction_quality.run as runner

    events: list[tuple[str, object]] = []
    result_dir = tmp_path / "results"
    artifact_paths = {
        "fake-experiment-a": result_dir / "artifact-a.json",
        "fake-experiment-b": result_dir / "artifact-b.json",
    }

    class FakeExperiment:
        def __init__(self, name: str):
            self.name = name

        def unavailable_reason(self) -> None:
            return None

    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: [
            FakeExperiment("fake-experiment-a"),
            FakeExperiment("fake-experiment-b"),
        ],
    )
    monkeypatch.setattr(
        runner,
        "reserve_result_dir",
        lambda **kwargs: result_dir,
    )
    monkeypatch.setattr(
        runner,
        "configure_logfire",
        lambda **kwargs: events.append(("configure", kwargs)),
    )

    async def fake_run_experiment(
        experiment,
        *,
        repeat,
        task_retries,
        max_concurrency,
        result_dir,
        artifact_timestamp,
    ) -> Path:
        events.append(("run", experiment.name))
        return artifact_paths[experiment.name]

    async def fake_enrich_run_artifacts(**kwargs):
        raise AssertionError("enrichment should not be called")

    monkeypatch.setattr(runner, "_run_experiment", fake_run_experiment)
    monkeypatch.setattr(
        runner, "enrich_experiment_artifacts", fake_enrich_run_artifacts
    )

    exit_code = runner.main(
        [
            "--experiment",
            "fake-experiment",
            "--output-dir",
            str(tmp_path),
            "--skip-logfire-enrichment",
        ]
    )

    assert exit_code == 0
    assert events == [
        (
            "configure",
            {
                "service_name": "voice-todos-backend",
                "instrument_pydantic_ai": True,
            },
        ),
        ("run", "fake-experiment-a"),
        ("run", "fake-experiment-b"),
    ]


def test_write_report_artifact_creates_timestamped_json(tmp_path, monkeypatch):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")
    timestamps = iter(
        [
            datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
            datetime(2026, 4, 1, 16, 20, 1, tzinfo=UTC),
        ]
    )

    monkeypatch.setattr(
        result_artifacts,
        "_utc_now",
        lambda: next(timestamps),
    )

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[
            ReportCase(
                name="case-1",
                inputs={"transcript": "Pick up milk"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-1.json",
                },
                expected_output=[Todo(text="Pick up milk")],
                output=[Todo(text="Pick up milk"), Todo(text="Bring eggs")],
                metrics={"expected_todo_count": 1, "predicted_todo_count": 2},
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
            "dataset_name": "todo_extraction_v1",
            "model_name": "gemini-3-flash-preview",
            "provider": "google-gla",
            "thinking_mode": "provider_default",
            "prompt_family": "todo_extraction",
            "prompt_version": "v1",
            "prompt_sha": "prompt-sha-123",
            "git_branch": "codex/item6-extraction-model-evals",
            "git_commit_sha": "65218795562767602eb8d5f9103eebfd9998cbec",
        },
        trace_id="report-trace-id",
        span_id="report-span-id",
    )

    first_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=2,
        max_concurrency=3,
    )
    second_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=2,
        max_concurrency=3,
    )

    assert first_path.name == "gemini3_flash_default.json"
    assert second_path.name == "gemini3_flash_default.json"
    assert first_path.parent.name == "2026-04-01T16-20-00Z"
    assert second_path.parent.name == "2026-04-01T16-20-01Z"
    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()

    payload = json.loads(first_path.read_text())
    assert payload["timestamp"] == "2026-04-01T16:20:00Z"
    assert payload["dataset_name"] == "todo_extraction_v1"
    assert payload["experiment_id"] == "gemini3_flash_default"
    assert payload["model"]["name"] == "gemini-3-flash-preview"
    assert payload["model"]["provider"] == "google-gla"
    assert payload["prompt"]["family"] == "todo_extraction"
    assert payload["prompt"]["version"] == "v1"
    assert payload["prompt"]["sha"] == "prompt-sha-123"
    assert payload["git"]["branch"] == "codex/item6-extraction-model-evals"
    assert (
        payload["git"]["commit_sha"] == "65218795562767602eb8d5f9103eebfd9998cbec"
    )
    assert payload["repeat"] == 2
    assert payload["max_concurrency"] == 3
    assert payload["task_retries"] == 0
    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 0
    assert payload["overall_case_success_rate"] == 1.0
    assert payload["failure_counts_by_category"] == {}
    assert payload["aggregate_metrics"] == {
        "expected_todo_count": 1.0,
        "predicted_todo_count": 2.0,
    }
    assert payload["cases"] == [
        {
            "name": "case-1",
            "source_fixture": "fixture-1.json",
            "expected_todo_count": 1,
            "predicted_todo_count": 2,
            "trace_id": "case-trace-id",
            "span_id": "case-span-id",
        }
    ]
    assert payload["trace_id"] == "report-trace-id"


@pytest.mark.asyncio
async def test_run_experiment_disables_task_retry_by_default(
    monkeypatch, tmp_path
):
    runner = import_module("evals.extraction_quality.run")

    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    class FakeDataset:
        name = "todo_extraction_v1"

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
        EXPERIMENTS["gemini3_flash_default"],
        repeat=3,
        max_concurrency=2,
        task_retries=0,
        result_dir=tmp_path,
        artifact_timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert evaluate_calls == [
        {
            "name": "gemini3_flash_default",
            "task_name": "extract_todos",
            "metadata": {
                "experiment": "gemini3_flash_default",
                "dataset_name": "todo_extraction_v1",
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
    runner = import_module("evals.extraction_quality.run")

    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    class FakeDataset:
        name = "todo_extraction_v1"

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
        EXPERIMENTS["gemini3_flash_default"],
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
            "task_name": "extract_todos",
            "metadata": {
                "experiment": "gemini3_flash_default",
                "dataset_name": "todo_extraction_v1",
                "task_retries": 2,
            },
            "repeat": 3,
            "max_concurrency": 2,
            "retry_task": retry_task,
        }
    ]


def test_write_report_artifact_uses_unique_result_dir_on_timestamp_collision(
    tmp_path,
):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")
    timestamp = datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC)

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_v1",
        },
    )

    first_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=1,
        max_concurrency=1,
        timestamp=timestamp,
    )
    second_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=1,
        max_concurrency=1,
        timestamp=timestamp,
    )

    assert first_path.parent.name == "2026-04-01T16-20-00Z"
    assert second_path.parent.name == "2026-04-01T16-20-00Z-01"
    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()


def test_write_report_artifact_serializes_failures(tmp_path):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[],
        failures=[
            ReportCaseFailure(
                name="case-2",
                inputs={"transcript": "Schedule dentist"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-2.json",
                },
                expected_output=[Todo(text="Schedule dentist")],
                error_message="provider timeout",
                error_stacktrace="Traceback...",
                trace_id="failure-trace-id",
                span_id="failure-span-id",
            )
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_v1",
        },
    )

    artifact_path = result_artifacts.write_report_artifact(
        report,
        output_dir=tmp_path,
        repeat=1,
        max_concurrency=1,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    payload = json.loads(artifact_path.read_text())

    assert payload["completed_cases"] == 0
    assert payload["failure_count"] == 1
    assert payload["overall_case_success_rate"] == 0.0
    assert payload["failure_counts_by_category"] == {
        "provider_transport_failure": 1
    }
    assert payload["failures"] == [
        {
            "name": "case-2",
            "source_fixture": "fixture-2.json",
            "expected_todo_count": 1,
            "predicted_todo_count": None,
            "error_message": "provider timeout",
            "failure_category": "provider_transport_failure",
            "trace_id": "failure-trace-id",
            "span_id": "failure-span-id",
        }
    ]


def test_build_report_artifact_keeps_transcript_only_case_shape(tmp_path):
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[
            ReportCase(
                name="case-1",
                inputs={"transcript": "Pick up milk"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-1.json",
                },
                expected_output=[Todo(text="Pick up milk")],
                output=[Todo(text="Pick up milk")],
                metrics={"expected_todo_count": 1, "predicted_todo_count": 1},
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
            "dataset_name": "todo_extraction_v1",
        },
    )

    payload = result_artifacts.build_report_artifact(
        report,
        repeat=1,
        max_concurrency=1,
        task_retries=2,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert payload["cases"] == [
        {
            "name": "case-1",
            "source_fixture": "fixture-1.json",
            "expected_todo_count": 1,
            "predicted_todo_count": 1,
            "trace_id": "case-trace-id",
            "span_id": "case-span-id",
        }
    ]
    assert payload["task_retries"] == 2


def test_build_report_artifact_tracks_mixed_case_and_failure_categories():
    result_artifacts = import_module("evals.extraction_quality.result_artifacts")

    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[
            ReportCase(
                name="case-1",
                inputs={"transcript": "Pick up milk"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-1.json",
                },
                expected_output=[Todo(text="Pick up milk")],
                output=[Todo(text="Pick up milk")],
                metrics={"expected_todo_count": 1, "predicted_todo_count": 1},
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
        failures=[
            ReportCaseFailure(
                name="case-2",
                inputs={"transcript": "Schedule dentist"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-2.json",
                },
                expected_output=[Todo(text="Schedule dentist")],
                error_message=(
                    "ConnectError: [Errno 8] nodename nor servname provided, "
                    "or not known"
                ),
                error_stacktrace="Traceback...",
                trace_id="failure-trace-id-1",
                span_id="failure-span-id-1",
            ),
            ReportCaseFailure(
                name="case-3",
                inputs={"transcript": "Book flight"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-3.json",
                },
                expected_output=[Todo(text="Book flight")],
                error_message="UnexpectedModelBehavior: output validation failed",
                error_stacktrace="Traceback...",
                trace_id="failure-trace-id-2",
                span_id="failure-span-id-2",
            ),
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_v1",
        },
    )

    payload = result_artifacts.build_report_artifact(
        report,
        repeat=1,
        max_concurrency=1,
        task_retries=1,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 2
    assert payload["overall_case_success_rate"] == 1 / 3
    assert payload["failure_counts_by_category"] == {
        "provider_transport_failure": 1,
        "output_validation_failure": 1,
    }
    assert payload["task_retries"] == 1
    assert payload["failures"] == [
        {
            "name": "case-2",
            "source_fixture": "fixture-2.json",
            "expected_todo_count": 1,
            "predicted_todo_count": None,
            "error_message": (
                "ConnectError: [Errno 8] nodename nor servname provided, "
                "or not known"
            ),
            "failure_category": "provider_transport_failure",
            "trace_id": "failure-trace-id-1",
            "span_id": "failure-span-id-1",
        },
        {
            "name": "case-3",
            "source_fixture": "fixture-3.json",
            "expected_todo_count": 1,
            "predicted_todo_count": None,
            "error_message": "UnexpectedModelBehavior: output validation failed",
            "failure_category": "output_validation_failure",
            "trace_id": "failure-trace-id-2",
            "span_id": "failure-span-id-2",
        },
    ]
