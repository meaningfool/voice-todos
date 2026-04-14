from __future__ import annotations

import hashlib
from pathlib import Path

from app.extract import get_extraction_prompt_ref
from evals.common.experiment_metadata import config_fingerprint
from evals.extraction_quality.experiment_configs import (
    experiment_definition_from_entry_config,
)
from evals.hosted_datasets import export_hosted_dataset
from evals.models import (
    BenchmarkDefinition,
    BenchmarkEntry,
    EntryQuerySelector,
    ResolvedEntryConfig,
)
from evals.storage import (
    load_benchmark_lock,
    lock_from_exported_dataset,
)


def resolve_entry_config(
    *,
    benchmark: BenchmarkDefinition,
    entry: BenchmarkEntry,
) -> ResolvedEntryConfig:
    dataset_family = benchmark.dataset_family

    return ResolvedEntryConfig(
        suite=(
            "incremental_extraction_quality"
            if dataset_family == "replay"
            else "extraction_quality"
        ),
        dataset_family=dataset_family,
        provider=entry.config["provider"],
        model_name=entry.config["model"],
        prompt_version=entry.config["prompt_version"],
        model_settings=entry.config.get("model_settings", {}),
    )


def build_entry_query_selector(
    *,
    benchmark: BenchmarkDefinition,
    entry: BenchmarkEntry,
) -> EntryQuerySelector:
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
    dataset_bytes = _selector_dataset_bytes(benchmark)
    evaluator_path = _evaluator_path_for_suite(resolved.suite)
    experiment = experiment_definition_from_entry_config(
        experiment_name_hint=entry.id,
        provider=resolved.provider,
        model_name=resolved.model_name,
        prompt_version=resolved.prompt_version,
        model_settings=resolved.model_settings,
    )
    prompt_sha = get_extraction_prompt_ref(experiment.extraction_config).sha256

    return EntryQuerySelector(
        entry_id=entry.id,
        label=entry.label,
        suite=resolved.suite,
        dataset_sha=_sha256_bytes(dataset_bytes),
        evaluator_contract_sha=_sha256_bytes(evaluator_path.read_bytes()),
        model_name=resolved.model_name,
        prompt_sha=prompt_sha,
        config_fingerprint=config_fingerprint(
            {
                "provider": experiment.provider,
                "thinking_mode": experiment.thinking_mode,
                "model_settings": experiment.extraction_config.model_settings,
                "prompt_version": experiment.extraction_config.prompt_version,
                "repeat": benchmark.repeat,
                "task_retries": benchmark.task_retries,
                "max_concurrency": benchmark.max_concurrency,
            }
        ),
        repeat=benchmark.repeat,
        task_retries=benchmark.task_retries,
    )


def _evaluator_path_for_suite(suite: str) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    if suite == "incremental_extraction_quality":
        return repo_root / "backend/evals/incremental_extraction_quality/evaluators.py"
    return repo_root / "backend/evals/extraction_quality/evaluators.py"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _selector_dataset_bytes(benchmark: BenchmarkDefinition) -> bytes:
    lock = load_benchmark_lock(benchmark.benchmark_id)
    if lock is not None:
        return lock.model_dump_json(by_alias=True, indent=2).encode()

    exported = export_hosted_dataset(benchmark.hosted_dataset)
    temporary_lock = lock_from_exported_dataset(
        benchmark=benchmark,
        exported=exported,
        fetched_at="selector-preview",
    )
    return temporary_lock.model_dump_json(by_alias=True, indent=2).encode()
