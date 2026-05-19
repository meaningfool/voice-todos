import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.resolution import resolve_entry_config
from evals.run import run_benchmark
from evals.storage import load_benchmark_by_id, load_benchmark_definition

REPLAY_BENCHMARK_DEFINITION = (
    Path(__file__).resolve().parents[2]
    / "evals/benchmarks/todo_replay_bench_v1.yaml"
)


def test_replay_benchmark_entry_resolves_incremental_replay_contract():
    benchmark = load_benchmark_by_id("todo_replay_bench_v1")
    entry = benchmark.entries[0]
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "incremental_extraction_quality"
    assert resolved.dataset_family == "replay"


def test_replay_benchmark_uses_deepinfra_small_model_matrix():
    benchmark = load_benchmark_definition(REPLAY_BENCHMARK_DEFINITION)
    deepinfra_entries = {
        entry.id: entry
        for entry in benchmark.entries
        if entry.config["provider"] == "deepinfra"
    }

    assert set(deepinfra_entries) == {
        "deepinfra_qwen35_0_8b_output_tool",
        "deepinfra_qwen35_2b_output_tool",
        "deepinfra_qwen35_4b_output_tool",
        "deepinfra_qwen35_9b_output_tool",
        "deepinfra_qwen35_0_8b_provider_json_schema",
        "deepinfra_qwen35_2b_provider_json_schema",
        "deepinfra_qwen35_4b_provider_json_schema",
        "deepinfra_qwen35_9b_provider_json_schema",
    }
    assert "deepinfra_qwen35_9b_default" not in deepinfra_entries
    assert "deepinfra_qwen35_4b_structured_tuned" not in deepinfra_entries

    for entry_id, entry in deepinfra_entries.items():
        assert entry.config["prompt_version"] == "v1"
        assert entry.config["model_settings"]["temperature"] == 0
        assert entry.config["model_settings"]["max_tokens"] == 512
        family = entry.config["implementation"]["family"]
        if entry_id.endswith("_provider_json_schema"):
            assert family == "deepinfra-provider-json-schema"
            assert entry.config["model_settings"]["extra_body"] == {
                "chat_template_kwargs": {"enable_thinking": False}
            }
        else:
            assert family == "deepinfra-output-tool"


def test_replay_benchmark_entry_resolves_deepinfra_family_contract():
    benchmark = load_benchmark_by_id("todo_replay_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "deepinfra_qwen35_4b_provider_json_schema"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "incremental_extraction_quality"
    assert resolved.provider == "deepinfra"
    assert resolved.model_name == "Qwen/Qwen3.5-4B"
    assert resolved.prompt_version == "v1"
    assert resolved.implementation_family == "deepinfra-provider-json-schema"
    assert resolved.model_settings == {
        "temperature": 0,
        "max_tokens": 512,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }


def test_default_run_skips_already_populated_entries(monkeypatch):
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids={"gemini3_flash_default"}),
    )
    launched = []

    async def fake_launch(**kwargs):
        launched.append(kwargs["entry"].id)
        return {"entry_id": kwargs["entry"].id}

    monkeypatch.setattr("evals.run.launch_replay_entry", fake_launch)

    asyncio.run(
        run_benchmark(
            benchmark_id="todo_replay_bench_v1",
            all_entries=False,
            dataset_path=Path("dataset.json"),
            allow_untracked=True,
        )
    )

    assert "gemini3_flash_default" not in launched


def test_all_flag_forces_full_replay_rerun(monkeypatch):
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(
            current_entry_ids={entry.id for entry in benchmark.entries}
        ),
    )
    launched = []

    async def fake_launch(**kwargs):
        launched.append(kwargs["entry"].id)
        return {"entry_id": kwargs["entry"].id}

    monkeypatch.setattr("evals.run.launch_replay_entry", fake_launch)

    asyncio.run(
        run_benchmark(
            benchmark_id="todo_replay_bench_v1",
            all_entries=True,
            dataset_path=Path("dataset.json"),
            allow_untracked=True,
        )
    )

    assert launched


@pytest.mark.asyncio
async def test_launch_replay_entry_preserves_implementation_family(
    monkeypatch, tmp_path
):
    from evals.incremental_extraction_quality import run as replay_runner

    benchmark = load_benchmark_by_id("todo_replay_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "deepinfra_qwen35_4b_provider_json_schema"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    captured_definition_kwargs = {}
    launched_experiments = []

    def fake_experiment_definition_from_entry_config(**kwargs):
        captured_definition_kwargs.update(kwargs)
        return SimpleNamespace(name="replay-experiment")

    async def fake_launch_experiments_for_definitions(**kwargs):
        launched_experiments.extend(kwargs["experiments"])
        return SimpleNamespace(batch_id="batch-1")

    monkeypatch.setattr(
        replay_runner,
        "experiment_definition_from_entry_config",
        fake_experiment_definition_from_entry_config,
    )
    monkeypatch.setattr(
        replay_runner,
        "launch_experiments_for_definitions",
        fake_launch_experiments_for_definitions,
    )

    result = await replay_runner.launch_replay_entry(
        entry=entry,
        resolved_config=resolved,
        dataset_path=tmp_path / "dataset.json",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        allow_untracked=True,
    )

    assert captured_definition_kwargs == {
        "experiment_name_hint": "deepinfra_qwen35_4b_provider_json_schema",
        "provider": "deepinfra",
        "model_name": "Qwen/Qwen3.5-4B",
        "prompt_version": "v1",
        "implementation_family": "deepinfra-provider-json-schema",
        "model_settings": {
            "temperature": 0,
            "max_tokens": 512,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        },
    }
    assert launched_experiments == [SimpleNamespace(name="replay-experiment")]
    assert result == {
        "entry_id": "deepinfra_qwen35_4b_provider_json_schema",
        "batch_id": "batch-1",
        "experiment_id": "replay-experiment",
    }
