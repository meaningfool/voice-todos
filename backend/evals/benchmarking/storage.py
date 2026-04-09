from __future__ import annotations

from pathlib import Path

from evals.benchmarking.models import (
    AttachedExperimentRef,
    BenchmarkManifest,
)


def load_benchmark_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate_json(path.read_text())


def save_benchmark_manifest(path: Path, manifest: BenchmarkManifest) -> None:
    normalized_manifest = BenchmarkManifest.model_validate(manifest.model_dump())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized_manifest.model_dump_json(indent=2) + "\n")


def attach_experiment(
    manifest: BenchmarkManifest,
    *,
    experiment_run_id: str,
    note: str | None = None,
) -> BenchmarkManifest:
    for existing_ref in manifest.attached_experiment_runs:
        if existing_ref.experiment_run_id == experiment_run_id:
            return manifest

    ref = AttachedExperimentRef(
        experiment_run_id=experiment_run_id,
        note=note,
    )
    manifest.attached_experiment_runs.append(ref)
    return manifest
