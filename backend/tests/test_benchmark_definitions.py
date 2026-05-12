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
        entry for entry in benchmark.entries if entry.id == "gemini3_flash_default"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.provider == "google-gla"
    assert resolved.model_name == "gemini-3-flash-preview"
    assert resolved.prompt_version == "v1"


def test_deepinfra_entries_use_explicit_families_and_shared_baseline():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
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


def test_resolve_entry_config_surfaces_implementation_family():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
    entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_provider_json_schema"
    )

    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == "deepinfra"
    assert resolved.model_name == "Qwen/Qwen3.5-4B"
    assert resolved.prompt_version == "v1"
    assert resolved.implementation_family == "deepinfra-provider-json-schema"
    assert resolved.model_settings == {
        "temperature": 0,
        "max_tokens": 512,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }


def test_extraction_benchmark_defines_modal_outlines_family_for_all_qwen_sizes():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
    modal_entries = {
        entry.id: entry
        for entry in benchmark.entries
        if entry.config["provider"] == "managed-openai"
    }

    assert set(modal_entries) == {
        "modal_outlines_qwen35_0_8b",
        "modal_outlines_qwen35_2b",
        "modal_outlines_qwen35_4b",
        "modal_outlines_qwen35_9b",
    }

    for entry in modal_entries.values():
        assert entry.config["prompt_version"] == "v1"
        assert entry.config["implementation"]["family"] == "modal-outlines"
        assert entry.config["model_settings"] == {
            "temperature": 0,
            "max_tokens": 1024,
        }
        assert entry.config["session"] == {
            "stack": "sglang-outlines",
            "host": "modal",
            "gpu": "L40S",
            "context_window": 4096,
        }
