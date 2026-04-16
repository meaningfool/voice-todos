import asyncio
from pathlib import Path
from types import SimpleNamespace

from evals.resolution import resolve_entry_config
from evals.run import run_benchmark
from evals.storage import load_benchmark_by_id


def test_replay_benchmark_entry_resolves_incremental_replay_contract():
    benchmark = load_benchmark_by_id("todo_replay_bench_v1")
    entry = benchmark.entries[0]
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "incremental_extraction_quality"
    assert resolved.dataset_family == "replay"


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
