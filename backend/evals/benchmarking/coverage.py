from __future__ import annotations

from itertools import product
from typing import Any

from evals.benchmarking.models import BenchmarkCoverage, BenchmarkManifest


def expected_coordinates(manifest: BenchmarkManifest) -> list[dict[str, str]]:
    fields = [axis.field for axis in manifest.axes]
    values = [axis.values for axis in manifest.axes]
    return [dict(zip(fields, combo, strict=True)) for combo in product(*values)]


def is_compatible(manifest: BenchmarkManifest, record: dict[str, Any]) -> bool:
    return (
        record.get("suite") == manifest.suite
        and record.get("dataset_sha") == manifest.dataset_sha
        and record.get("evaluator_contract_sha") == manifest.evaluator_contract_sha
        and all(
            record.get(key) == value
            for key, value in manifest.fixed_config.items()
        )
    )


def _record_to_coordinate(
    manifest: BenchmarkManifest,
    record: dict[str, Any],
) -> dict[str, str] | None:
    coordinate: dict[str, str] = {}

    for axis in manifest.axes:
        value = record.get(axis.field)
        if value is None or value not in axis.values:
            return None
        coordinate[axis.field] = value

    return coordinate


def _coordinate_key(coordinate: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(coordinate.items()))


def build_benchmark_coverage(
    manifest: BenchmarkManifest,
    fetched: list[dict[str, Any]],
) -> BenchmarkCoverage:
    fetched_by_run = {
        record["experiment_run_id"]: record
        for record in fetched
        if "experiment_run_id" in record
    }

    compatible_coordinates: list[dict[str, str]] = []
    compatible_experiment_run_ids: list[str] = []
    incompatible_experiment_run_ids: list[str] = []
    missing_attached_experiment_run_ids: list[str] = []
    unmappable_experiment_run_ids: list[str] = []

    for attached_ref in manifest.attached_experiment_runs:
        record = fetched_by_run.get(attached_ref.experiment_run_id)
        if record is None:
            missing_attached_experiment_run_ids.append(attached_ref.experiment_run_id)
            continue

        if not is_compatible(manifest, record):
            incompatible_experiment_run_ids.append(attached_ref.experiment_run_id)
            continue

        coordinate = _record_to_coordinate(manifest, record)
        if coordinate is None:
            unmappable_experiment_run_ids.append(attached_ref.experiment_run_id)
            continue

        compatible_experiment_run_ids.append(attached_ref.experiment_run_id)
        compatible_coordinates.append(coordinate)

    covered_keys = {
        _coordinate_key(coordinate)
        for coordinate in compatible_coordinates
    }
    missing_coordinates = [
        coordinate
        for coordinate in expected_coordinates(manifest)
        if _coordinate_key(coordinate) not in covered_keys
    ]

    return BenchmarkCoverage(
        compatible_count=len(compatible_experiment_run_ids),
        incompatible_count=len(incompatible_experiment_run_ids),
        compatible_coordinates=compatible_coordinates,
        missing_coordinates=missing_coordinates,
        compatible_experiment_run_ids=compatible_experiment_run_ids,
        incompatible_experiment_run_ids=incompatible_experiment_run_ids,
        missing_attached_experiment_run_ids=missing_attached_experiment_run_ids,
        unmappable_experiment_run_ids=unmappable_experiment_run_ids,
    )
