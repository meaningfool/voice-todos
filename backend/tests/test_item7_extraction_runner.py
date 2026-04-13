import asyncio
from types import SimpleNamespace

from evals.resolution import resolve_entry_config
from evals.run import run_benchmark
from evals.storage import load_benchmark_by_id

from evals.extraction_quality.experiment_configs import EXPERIMENTS


def test_extraction_entry_resolves_to_legacy_equivalent():
    benchmark = load_benchmark_by_id("extraction_llm_matrix_v1")
    entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "gemini3_flash_default"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
    legacy = EXPERIMENTS["gemini3_flash_default"]

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == legacy.provider
    assert resolved.model_name == legacy.extraction_config.model_name
    assert resolved.prompt_version == legacy.extraction_config.prompt_version


def test_extraction_runner_passes_entry_context_without_benchmark_leakage(
    monkeypatch, tmp_path
):
    calls = []

    async def fake_launch(**kwargs):
        calls.append(kwargs)
        return {"entry_id": kwargs["entry"].id}

    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr("evals.run.launch_extraction_entry", fake_launch)

    result = asyncio.run(
        run_benchmark(
            benchmark_id="extraction_llm_matrix_v1",
            all_entries=True,
            dataset_path=tmp_path / "dataset.json",
            allow_untracked=True,
        )
    )

    assert result.executed_entry_ids
    assert calls[0]["entry"].id == "gemini3_flash_default"
    assert "benchmark" not in calls[0]
