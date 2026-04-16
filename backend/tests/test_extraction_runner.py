from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.extraction_quality import experiment_configs
from evals.extraction_quality.experiment_configs import EXPERIMENTS
from evals.extraction_quality.run import main

EXPECTED_EXPERIMENTS = [
    "gemini3_flash_default",
    "gemini3_flash_minimal_thinking",
    "gemini31_flash_lite_default",
    "gemini31_flash_lite_minimal_thinking",
    "mistral_small_4_default",
    "deepinfra_qwen35_9b_default",
    "deepinfra_qwen35_4b_structured_tuned",
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


def test_deepinfra_experiment_reports_provider_unavailability(monkeypatch):
    monkeypatch.setattr(
        experiment_configs,
        "_deepinfra_unavailable_reason",
        lambda: "deepinfra provider unavailable",
    )

    assert (
        EXPERIMENTS["deepinfra_qwen35_9b_default"].unavailable_reason()
        == "deepinfra provider unavailable"
    )


def test_main_fails_fast_when_tracked_mode_has_no_logfire_credentials(monkeypatch):
    import evals.extraction_quality.run as runner

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: False)

    with pytest.raises(SystemExit):
        runner.main(["--experiment", "gemini3_flash_default"])


def test_main_allows_explicit_untracked_mode(monkeypatch):
    import evals.extraction_quality.run as runner

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: False)
    monkeypatch.setattr(runner, "_run", lambda args: 0)

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
    import evals.extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"dataset":"override"}')

    load_calls: list[Path | None] = []
    evaluate_calls: list[dict[str, object]] = []

    experiments = [
        SimpleNamespace(
            name="fake-experiment-a",
            provider="provider-a",
            thinking_mode="default",
            extraction_config=SimpleNamespace(
                model_name="model-a",
                model_settings={"temperature": 0},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-a"},
            unavailable_reason=lambda: None,
        ),
        SimpleNamespace(
            name="fake-experiment-b",
            provider="provider-b",
            thinking_mode="minimal",
            extraction_config=SimpleNamespace(
                model_name="model-b",
                model_settings={"temperature": 1},
                prompt_version="v2",
            ),
            prompt_metadata={"prompt_sha": "prompt-b"},
            unavailable_reason=lambda: None,
        ),
    ]

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    async def fake_evaluate(self, task, **kwargs):
        evaluate_calls.append(kwargs)
        return FakeReport()

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: True)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: experiments,
    )
    monkeypatch.setattr(
        runner,
        "load_extraction_quality_dataset",
        lambda path=None: (
            load_calls.append(path),
            SimpleNamespace(name="override-dataset", cases=[]),
        )[1],
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    exit_code = await runner._run(
        SimpleNamespace(
            all=False,
            experiment=["fake-experiment-a", "fake-experiment-b"],
            repeat=2,
            task_retries=1,
            max_concurrency=3,
            dataset_path=dataset_override,
            allow_untracked=False,
        )
    )

    assert exit_code == 0
    assert load_calls == [dataset_override]
    assert len(evaluate_calls) == 2
    assert {call["name"] for call in evaluate_calls} == {
        "fake-experiment-a",
        "fake-experiment-b",
    }
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
    import evals.extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"dataset":"override"}')

    experiments = [
        SimpleNamespace(
            name="fake-experiment-a",
            provider="provider-a",
            thinking_mode="default",
            extraction_config=SimpleNamespace(
                model_name="model-a",
                model_settings={"temperature": 0},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-a"},
            unavailable_reason=lambda: None,
        ),
        SimpleNamespace(
            name="fake-experiment-b",
            provider="provider-b",
            thinking_mode="minimal",
            extraction_config=SimpleNamespace(
                model_name="model-b",
                model_settings={"temperature": 1},
                prompt_version="v2",
            ),
            prompt_metadata={"prompt_sha": "prompt-b"},
            unavailable_reason=lambda: None,
        ),
    ]

    class FakeReport:
        def print(self, include_metadata: bool) -> None:
            assert include_metadata is True

    async def fake_evaluate(self, task, **kwargs):
        return FakeReport()

    monkeypatch.setattr(runner, "has_logfire_write_credentials", lambda: True)
    monkeypatch.setattr(runner, "configure_logfire", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_selected_experiments",
        lambda **kwargs: experiments,
    )
    monkeypatch.setattr(
        runner,
        "load_extraction_quality_dataset",
        lambda path=None: SimpleNamespace(name="override-dataset", cases=[]),
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    result = await runner.launch_experiments(
        SimpleNamespace(
            all=False,
            experiment=["fake-experiment-a", "fake-experiment-b"],
            repeat=2,
            task_retries=1,
            max_concurrency=3,
            dataset_path=dataset_override,
            allow_untracked=False,
        )
    )

    assert result.batch_id
    assert result.launched_experiments == [
        {
            "batch_id": result.batch_id,
            "experiment_id": "fake-experiment-a",
            "experiment_run_id": f"{result.batch_id}--fake-experiment-a",
        },
        {
            "batch_id": result.batch_id,
            "experiment_id": "fake-experiment-b",
            "experiment_run_id": f"{result.batch_id}--fake-experiment-b",
        },
    ]


@pytest.mark.asyncio
async def test_run_resolves_default_dataset_from_benchmark_lock(
    monkeypatch, tmp_path
):
    import evals.extraction_quality.run as runner

    lock_path = tmp_path / "todo_extraction_bench_v1.json"
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
        SimpleNamespace(
            name="fake-experiment-a",
            provider="provider-a",
            thinking_mode="default",
            extraction_config=SimpleNamespace(
                model_name="model-a",
                model_settings={"temperature": 0},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-a"},
            unavailable_reason=lambda: None,
        )
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
        "load_extraction_quality_dataset",
        lambda path=None: (
            load_calls.append(path),
            SimpleNamespace(name="locked-dataset", cases=[]),
        )[1],
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    exit_code = await runner._run(
        SimpleNamespace(
            all=False,
            experiment=["fake-experiment-a"],
            repeat=1,
            task_retries=0,
            max_concurrency=1,
            dataset_path=None,
            allow_untracked=False,
        )
    )

    assert exit_code == 0
    assert load_calls == [lock_path]
    assert evaluate_calls[0]["metadata"]["dataset_name"] == "locked-dataset"
