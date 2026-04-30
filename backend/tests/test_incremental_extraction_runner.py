from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest

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
    attr_calls: list[tuple[str, str]] = []
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
    monkeypatch.setattr(
        runner,
        "set_eval_attribute",
        lambda n, v: attr_calls.append((n, v)),
    )

    result = await runner._run_case(
        {
            "reference_dt": reference_dt,
            "replay_steps": replay_steps,
        },
        experiment=experiment,
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
    # Only per-step attributes should be set; experiment-wide metadata is not mirrored.
    assert [name for name, _ in attr_calls] == [
        "replay_step_1_todos",
        "replay_step_2_todos",
    ]


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


def test_main_fails_fast_when_tracked_mode_has_no_logfire_credentials(monkeypatch):
    import evals.incremental_extraction_quality.run as runner

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: False)

    with pytest.raises(SystemExit):
        runner.main(["--experiment", "gemini3_flash_default"])


def test_main_allows_explicit_untracked_mode(monkeypatch):
    import evals.incremental_extraction_quality.run as runner

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: False)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_build_eval_dataset",
        lambda path=None: type("DS", (), {"name": "unused", "cases": []})(),
    )
    monkeypatch.setattr(runner, "_selected_experiments", lambda **kwargs: [])
    monkeypatch.setattr(runner, "_resolve_dataset_path", lambda path: path)

    assert (
        runner.main(
            [
                "--experiment",
                "gemini3_flash_default",
                "--allow-untracked",
            ]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_run_uses_batch_metadata_and_dataset_override(monkeypatch, tmp_path):
    import evals.incremental_extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"dataset":"override-incremental"}')

    load_calls: list[Path | None] = []
    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    async def fake_evaluate(self, task, **kwargs):
        evaluate_calls.append(kwargs)
        return FakeReport()

    experiments = [
        type(
            "FakeExperiment",
            (),
            {
                "name": "fake-replay-experiment-a",
                "provider": "provider-a",
                "thinking_mode": "default",
                "extraction_config": type(
                    "Cfg",
                    (),
                    {
                        "model_name": "model-a",
                        "model_settings": {"temperature": 0},
                        "prompt_version": "v1",
                    },
                )(),
                "prompt_metadata": {"prompt_sha": "prompt-a"},
                "unavailable_reason": staticmethod(lambda: None),
            },
        )(),
        type(
            "FakeExperiment",
            (),
            {
                "name": "fake-replay-experiment-b",
                "provider": "provider-b",
                "thinking_mode": "minimal",
                "extraction_config": type(
                    "Cfg",
                    (),
                    {
                        "model_name": "model-b",
                        "model_settings": {"temperature": 1},
                        "prompt_version": "v2",
                    },
                )(),
                "prompt_metadata": {"prompt_sha": "prompt-b"},
                "unavailable_reason": staticmethod(lambda: None),
            },
        )(),
    ]

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: True)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: experiments,
    )
    monkeypatch.setattr(
        runner,
        "load_incremental_replay_dataset",
        lambda path=None: (
            load_calls.append(path),
            type("DS", (), {"name": "override-incremental", "cases": []})(),
        )[1],
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    exit_code = await runner._run(
        type(
            "Args",
            (),
            {
                "all": False,
                "experiment": [
                    "fake-replay-experiment-a",
                    "fake-replay-experiment-b",
                ],
                "repeat": 2,
                "task_retries": 1,
                "max_concurrency": 3,
                "dataset_path": dataset_override,
                "allow_untracked": False,
            },
        )()
    )

    assert exit_code == 0
    assert load_calls == [dataset_override]
    assert len(evaluate_calls) == 2
    assert {call["name"] for call in evaluate_calls} == {
        "fake-replay-experiment-a",
        "fake-replay-experiment-b",
    }
    assert all(
        call["metadata"]["suite"] == "incremental_extraction_quality"
        for call in evaluate_calls
    )
    assert all(
        call["metadata"]["dataset_name"] == "override-incremental"
        for call in evaluate_calls
    )
    batch_ids = {call["metadata"]["batch_id"] for call in evaluate_calls}
    assert len(batch_ids) == 1
    batch_id = next(iter(batch_ids))
    assert batch_id
    for call in evaluate_calls:
        assert call["metadata"]["experiment_id"] == call["name"]
        assert (
            call["metadata"]["experiment_run_id"]
            == f"{call['metadata']['batch_id']}--{call['name']}"
        )


@pytest.mark.asyncio
async def test_launch_experiments_returns_batch_and_attached_refs(
    monkeypatch, tmp_path
):
    import evals.incremental_extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"dataset":"override-incremental"}')

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    async def fake_evaluate(self, task, **kwargs):
        return FakeReport()

    experiments = [
        type(
            "FakeExperiment",
            (),
            {
                "name": "fake-replay-experiment-a",
                "provider": "provider-a",
                "thinking_mode": "default",
                "extraction_config": type(
                    "Cfg",
                    (),
                    {
                        "model_name": "model-a",
                        "model_settings": {"temperature": 0},
                        "prompt_version": "v1",
                    },
                )(),
                "prompt_metadata": {"prompt_sha": "prompt-a"},
                "unavailable_reason": staticmethod(lambda: None),
            },
        )(),
        type(
            "FakeExperiment",
            (),
            {
                "name": "fake-replay-experiment-b",
                "provider": "provider-b",
                "thinking_mode": "minimal",
                "extraction_config": type(
                    "Cfg",
                    (),
                    {
                        "model_name": "model-b",
                        "model_settings": {"temperature": 1},
                        "prompt_version": "v2",
                    },
                )(),
                "prompt_metadata": {"prompt_sha": "prompt-b"},
                "unavailable_reason": staticmethod(lambda: None),
            },
        )(),
    ]

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: True)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: experiments,
    )
    monkeypatch.setattr(
        runner,
        "load_incremental_replay_dataset",
        lambda path=None: type(
            "DS",
            (),
            {"name": "override-incremental", "cases": []},
        )(),
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    result = await runner.launch_experiments(
        type(
            "Args",
            (),
            {
                "all": False,
                "experiment": [
                    "fake-replay-experiment-a",
                    "fake-replay-experiment-b",
                ],
                "repeat": 2,
                "task_retries": 1,
                "max_concurrency": 3,
                "dataset_path": dataset_override,
                "allow_untracked": False,
            },
        )()
    )

    assert result.batch_id
    assert result.launched_experiments == [
        {
            "batch_id": result.batch_id,
            "experiment_id": "fake-replay-experiment-a",
            "experiment_run_id": f"{result.batch_id}--fake-replay-experiment-a",
        },
        {
            "batch_id": result.batch_id,
            "experiment_id": "fake-replay-experiment-b",
            "experiment_run_id": f"{result.batch_id}--fake-replay-experiment-b",
        },
    ]


@pytest.mark.asyncio
async def test_run_resolves_default_replay_dataset_from_benchmark_lock(
    monkeypatch, tmp_path
):
    import evals.incremental_extraction_quality.run as runner

    lock_path = tmp_path / "todo_replay_bench_v1.json"
    lock_path.write_text('{"name":"lock","version":"v1","rows":[]}')
    load_calls: list[Path] = []
    evaluate_calls: list[dict[str, object]] = []

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    async def fake_evaluate(self, task, **kwargs):
        evaluate_calls.append(kwargs)
        return FakeReport()

    experiments = [
        type(
            "FakeExperiment",
            (),
            {
                "name": "fake-replay-experiment-a",
                "provider": "provider-a",
                "thinking_mode": "default",
                "extraction_config": type(
                    "Cfg",
                    (),
                    {
                        "model_name": "model-a",
                        "model_settings": {"temperature": 0},
                        "prompt_version": "v1",
                    },
                )(),
                "prompt_metadata": {"prompt_sha": "prompt-a"},
                "unavailable_reason": staticmethod(lambda: None),
            },
        )()
    ]

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: True)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_selected_experiments", lambda **kwargs: experiments)
    monkeypatch.setattr(
        runner,
        "ensure_benchmark_dataset_path",
        lambda benchmark_id: lock_path,
    )
    monkeypatch.setattr(
        runner,
        "load_incremental_replay_dataset",
        lambda path=None: (
            load_calls.append(path),
            type("DS", (), {"name": "locked-replay", "cases": []})(),
        )[1],
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    exit_code = await runner._run(
        type(
            "Args",
            (),
            {
                "all": False,
                "experiment": ["fake-replay-experiment-a"],
                "repeat": 1,
                "task_retries": 0,
                "max_concurrency": 1,
                "dataset_path": None,
                "allow_untracked": False,
            },
        )()
    )

    assert exit_code == 0
    assert load_calls == [lock_path]
    assert evaluate_calls[0]["metadata"]["dataset_name"] == "locked-replay"
