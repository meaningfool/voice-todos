from __future__ import annotations

import asyncio
import inspect

from pydantic import BaseModel, Field

from evals.benchmarking.coverage import build_benchmark_coverage
from evals.benchmarking.models import AttachedExperimentRef, BenchmarkManifest


class BenchmarkReport(BaseModel):
    benchmark_id: str
    compatible_experiments: list[str] = Field(default_factory=list)
    incompatible_experiments: list[str] = Field(default_factory=list)
    missing_attached_experiments: list[str] = Field(default_factory=list)
    unmappable_experiments: list[str] = Field(default_factory=list)
    missing_coordinates: list[dict[str, str]] = Field(default_factory=list)
    unattached_candidates: list[str] = Field(default_factory=list)


def _fetch_attached_experiments(
    query_client: object,
    attachments: list[AttachedExperimentRef],
) -> list[dict[str, str]]:
    result = query_client.fetch_attached_experiments(attachments)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def build_benchmark_report(
    *,
    manifest: BenchmarkManifest,
    query_client: object,
) -> BenchmarkReport:
    fetched_records = _fetch_attached_experiments(
        query_client,
        manifest.attached_experiment_runs,
    )
    coverage = build_benchmark_coverage(manifest, fetched_records)

    return BenchmarkReport(
        benchmark_id=manifest.benchmark_id,
        compatible_experiments=coverage.compatible_experiment_run_ids,
        incompatible_experiments=coverage.incompatible_experiment_run_ids,
        missing_attached_experiments=coverage.missing_attached_experiment_run_ids,
        unmappable_experiments=coverage.unmappable_experiment_run_ids,
        missing_coordinates=coverage.missing_coordinates,
        unattached_candidates=[],
    )
