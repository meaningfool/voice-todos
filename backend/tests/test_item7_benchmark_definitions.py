from pathlib import Path

from evals.resolution import resolve_entry_config
from evals.storage import load_benchmark_definition


def test_extraction_benchmark_definition_parses_required_fields():
    benchmark = load_benchmark_definition(
        Path("../evals/benchmarks/extraction_llm_matrix_v1.yaml")
    )

    assert benchmark.benchmark_id == "extraction_llm_matrix_v1"
    assert benchmark.focus == "model"
    assert benchmark.headline_metric == "todo_count_match"
    assert benchmark.repeat >= 1
    assert benchmark.task_retries >= 0
    assert len({entry.id for entry in benchmark.entries}) == len(benchmark.entries)


def test_extraction_entry_matches_legacy_registry_values():
    benchmark = load_benchmark_definition(
        Path("../evals/benchmarks/extraction_llm_matrix_v1.yaml")
    )
    entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "gemini3_flash_default"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.provider == "google-gla"
    assert resolved.model_name == "gemini-3-flash-preview"
    assert resolved.prompt_version == "v1"
