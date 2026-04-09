from __future__ import annotations

from pathlib import Path

from evals.benchmarking.models import (
    AttachedExperimentRef,
    BenchmarkManifest,
)


def load_benchmark_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate_json(path.read_text())


def save_benchmark_manifest(path: Path, manifest: BenchmarkManifest) -> None:
    normalized_manifest = BenchmarkManifest.model_validate(
        {
            "benchmark_id": manifest.benchmark_id,
            "title": manifest.title,
            "description": manifest.description,
            "suite": manifest.suite,
            "dataset_name": manifest.dataset_name,
            "dataset_sha": manifest.dataset_sha,
            "evaluator_contract_sha": manifest.evaluator_contract_sha,
            "fixed_config": manifest.fixed_config,
            "axes": [
                axis.model_dump() if hasattr(axis, "model_dump") else axis
                for axis in manifest.axes
            ],
            "attached_experiment_runs": [
                ref.model_dump() if hasattr(ref, "model_dump") else ref
                for ref in manifest.attached_experiment_runs
            ],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized_manifest.model_dump_json(indent=2) + "\n")


def attach_experiment(
    manifest: BenchmarkManifest,
    *,
    experiment_run_id: str,
    note: str | None = None,
) -> BenchmarkManifest:
    ref = AttachedExperimentRef(
        experiment_run_id=experiment_run_id,
        note=note,
    )
    if ref not in manifest.attached_experiment_runs:
        manifest.attached_experiment_runs.append(ref)
    return manifest
