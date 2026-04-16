"""Benchmark definition contract tests."""

from pathlib import Path

from evals.resolution import resolve_entry_config
from evals.storage import load_benchmark_definition


BENCHMARK_DEFINITION = (
    Path(__file__).resolve().parents[2]
    / "evals/benchmarks/todo_extraction_bench_v1.yaml"
)


def test_benchmark_definition_parses_required_fields_and_unique_entry_ids():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)

    assert benchmark.benchmark_id == "todo_extraction_bench_v1"
    assert benchmark.dataset_family == "extraction"
    assert benchmark.focus == "model"
    assert benchmark.headline_metric == "todo_count_match"
    assert benchmark.repeat >= 1
    assert benchmark.task_retries >= 0
    assert len({entry.id for entry in benchmark.entries}) == len(benchmark.entries)


def test_extraction_entry_matches_legacy_registry_values():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
    entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "gemini3_flash_default"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.provider == "google-gla"
    assert resolved.model_name == "gemini-3-flash-preview"
    assert resolved.prompt_version == "v1"
