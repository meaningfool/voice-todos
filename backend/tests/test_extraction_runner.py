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
            implementation_family=None,
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
            implementation_family=None,
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
            implementation_family=None,
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
            implementation_family=None,
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
async def test_run_resolves_default_dataset_from_benchmark_lock(monkeypatch, tmp_path):
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
            implementation_family=None,
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


@pytest.mark.asyncio
async def test_launch_experiments_separates_same_model_by_implementation_family(
    monkeypatch, tmp_path
):
    import evals.extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"dataset":"override"}')

    evaluate_calls: list[dict[str, object]] = []

    experiments = [
        SimpleNamespace(
            name="same-model-output-tool",
            provider="deepinfra",
            thinking_mode="default",
            implementation_family="deepinfra-output-tool",
            extraction_config=SimpleNamespace(
                model_name="Qwen/Qwen3.5-4B",
                model_settings={"temperature": 0, "max_tokens": 512},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-sha"},
            unavailable_reason=lambda: None,
        ),
        SimpleNamespace(
            name="same-model-provider-json",
            provider="deepinfra",
            thinking_mode="default",
            implementation_family="deepinfra-provider-json-schema",
            extraction_config=SimpleNamespace(
                model_name="Qwen/Qwen3.5-4B",
                model_settings={"temperature": 0, "max_tokens": 512},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-sha"},
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
        "load_extraction_quality_dataset",
        lambda path=None: SimpleNamespace(name="override-dataset", cases=[]),
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    await runner.launch_experiments_for_definitions(
        experiments=experiments,
        dataset_path=dataset_override,
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        allow_untracked=False,
    )

    fingerprints = [call["metadata"]["config_fingerprint"] for call in evaluate_calls]
    assert len(fingerprints) == 2
    assert fingerprints[0] != fingerprints[1]


@pytest.mark.asyncio
async def test_managed_session_changes_config_fingerprint(monkeypatch, tmp_path):
    import evals.extraction_quality.run as runner

    dataset_override = tmp_path / "dataset.json"
    dataset_override.write_text('{"cases": []}\n')
    evaluate_calls = []

    experiments = [
        SimpleNamespace(
            name="modal-outlines-4b-l40s",
            provider="managed-openai",
            thinking_mode="custom",
            implementation_family="modal-outlines",
            managed_session={
                "stack": "sglang-outlines",
                "host": "modal",
                "gpu": "L40S",
                "context_window": 4096,
            },
            extraction_config=SimpleNamespace(
                model_name="Qwen/Qwen3.5-4B",
                model_settings={"temperature": 0, "max_tokens": 1024},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-sha"},
            unavailable_reason=lambda: None,
        ),
        SimpleNamespace(
            name="modal-outlines-4b-a100",
            provider="managed-openai",
            thinking_mode="custom",
            implementation_family="modal-outlines",
            managed_session={
                "stack": "sglang-outlines",
                "host": "modal",
                "gpu": "A100",
                "context_window": 4096,
            },
            extraction_config=SimpleNamespace(
                model_name="Qwen/Qwen3.5-4B",
                model_settings={"temperature": 0, "max_tokens": 1024},
                prompt_version="v1",
            ),
            prompt_metadata={"prompt_sha": "prompt-sha"},
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
        "load_extraction_quality_dataset",
        lambda path=None: SimpleNamespace(name="override-dataset", cases=[]),
    )
    monkeypatch.setattr(runner.Dataset, "evaluate", fake_evaluate)

    await runner.launch_experiments_for_definitions(
        experiments=experiments,
        dataset_path=dataset_override,
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        allow_untracked=False,
    )

    fingerprints = [call["metadata"]["config_fingerprint"] for call in evaluate_calls]
    assert len(fingerprints) == 2
    assert fingerprints[0] != fingerprints[1]


@pytest.mark.asyncio
async def test_launch_extraction_entry_preserves_entry_identity_with_managed_lease(
    monkeypatch, tmp_path
):
    import evals.extraction_quality.run as runner

    captured: dict[str, object] = {}

    async def fake_launch_experiments_for_definitions(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(batch_id="managed-batch")

    monkeypatch.setattr(
        runner,
        "launch_experiments_for_definitions",
        fake_launch_experiments_for_definitions,
    )

    result = await runner.launch_extraction_entry(
        entry=SimpleNamespace(id="modal_outlines_qwen35_4b"),
        resolved_config=SimpleNamespace(
            provider="managed-openai",
            model_name="Qwen/Qwen3.5-4B",
            prompt_version="v1",
            implementation_family="modal-outlines",
            model_settings={"temperature": 0, "max_tokens": 1024},
            managed_session=SimpleNamespace(
                stack="sglang-outlines",
                host="modal",
                gpu="L40S",
                context_window=4096,
            ),
        ),
        dataset_path=tmp_path / "dataset.json",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        allow_untracked=True,
        managed_lease=SimpleNamespace(
            base_url="https://managed.example/v1",
            api_key="managed-test-key",
            headers={"Modal-Session-ID": "session-123"},
        ),
    )

    experiment = captured["experiments"][0]
    assert experiment.name == "modal_outlines_qwen35_4b"
    assert experiment.provider == "managed-openai"
    assert experiment.implementation_family == "modal-outlines"
    assert experiment.managed_session == {
        "stack": "sglang-outlines",
        "host": "modal",
        "gpu": "L40S",
        "context_window": 4096,
    }
    assert experiment.extraction_config.openai_base_url == "https://managed.example/v1"
    assert experiment.extraction_config.openai_api_key == "managed-test-key"
    assert experiment.extraction_config.transport_headers == {
        "Modal-Session-ID": "session-123"
    }
    assert result == {
        "entry_id": "modal_outlines_qwen35_4b",
        "batch_id": "managed-batch",
        "experiment_id": "modal_outlines_qwen35_4b",
    }
