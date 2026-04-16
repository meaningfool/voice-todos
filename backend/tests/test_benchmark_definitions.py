"""Benchmark definition contract tests."""

from pathlib import Path

from evals.storage import load_benchmark_definition


BENCHMARK_DEFINITION = (
    Path(__file__).resolve().parents[2]
    / "evals/benchmarks/extraction_llm_matrix_v1.yaml"
)


def test_benchmark_definition_parses_required_fields_and_unique_entry_ids():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)

    assert benchmark.benchmark_id == "extraction_llm_matrix_v1"
    assert benchmark.dataset_family == "extraction"
    assert benchmark.focus == "model"
    assert benchmark.headline_metric == "todo_count_match"
    assert benchmark.repeat >= 1
    assert benchmark.task_retries >= 0
    assert len({entry.id for entry in benchmark.entries}) == len(benchmark.entries)
