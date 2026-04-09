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


def _dedupe_fetched_records(
    records: list[dict[str, str]],
) -> list[dict[str, str]]:
    seen_run_ids: set[str] = set()
    deduped_records: list[dict[str, str]] = []

    for record in records:
        experiment_run_id = record.get("experiment_run_id")
        if not experiment_run_id or experiment_run_id in seen_run_ids:
            continue

        seen_run_ids.add(experiment_run_id)
        deduped_records.append(record)

    return deduped_records


async def _fetch_attached_experiments_async(
    query_client: object,
    attachments: list[AttachedExperimentRef],
) -> list[dict[str, str]]:
    result = query_client.fetch_attached_experiments(attachments)
    if inspect.isawaitable(result):
        result = await result
    return _dedupe_fetched_records(result)


async def build_benchmark_report_async(
    *,
    manifest: BenchmarkManifest,
    query_client: object,
) -> BenchmarkReport:
    fetched_records = await _fetch_attached_experiments_async(
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


def build_benchmark_report(
    *,
    manifest: BenchmarkManifest,
    query_client: object,
) -> BenchmarkReport:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            build_benchmark_report_async(
                manifest=manifest,
                query_client=query_client,
            )
        )

    raise RuntimeError(
        "build_benchmark_report cannot run inside an active event loop; "
        "use build_benchmark_report_async instead."
    )
