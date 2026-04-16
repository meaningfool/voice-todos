from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from evals.models import BenchmarkDefinition, DatasetDefinition, LockedDatasetDefinition
from evals.models import BenchmarkLockMetadata
from evals.hosted_datasets import canonical_dataset_hash


def benchmarks_dir() -> Path:
    override = os.getenv("EVALS_BENCHMARKS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "benchmarks"


LOCKS_DIR = Path(__file__).resolve().parent / "locks"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def load_dataset_definition(path: Path) -> DatasetDefinition:
    return DatasetDefinition.model_validate(json.loads(path.read_text()))


def load_benchmark_definition(path: Path) -> BenchmarkDefinition:
    return BenchmarkDefinition.model_validate(yaml.safe_load(path.read_text()))


def list_benchmark_ids() -> list[str]:
    return sorted(path.stem for path in benchmarks_dir().glob("*.yaml"))


def load_benchmark_by_id(benchmark_id: str) -> BenchmarkDefinition:
    return load_benchmark_definition(benchmarks_dir() / f"{benchmark_id}.yaml")


def benchmark_lock_path(benchmark_id: str) -> Path:
    return LOCKS_DIR / f"{benchmark_id}.json"


def benchmark_report_path(benchmark_id: str) -> Path:
    return REPORTS_DIR / f"{benchmark_id}.json"


def benchmark_html_report_path(benchmark_id: str) -> Path:
    return REPORTS_DIR / f"{benchmark_id}.html"


def load_benchmark_lock(benchmark_id: str) -> LockedDatasetDefinition | None:
    path = benchmark_lock_path(benchmark_id)
    if not path.exists():
        return None
    return LockedDatasetDefinition.model_validate(json.loads(path.read_text()))


def write_benchmark_lock(lock: LockedDatasetDefinition) -> Path:
    path = benchmark_lock_path(lock.benchmark_lock.benchmark_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lock.model_dump_json(by_alias=True, indent=2))
    return path


def lock_from_exported_dataset(
    *,
    benchmark: BenchmarkDefinition,
    exported: dict,
    fetched_at: str,
) -> LockedDatasetDefinition:
    dataset_name, dataset_version = _dataset_name_and_version(exported["name"])
    cases = exported.get("cases", [])

    return LockedDatasetDefinition(
        name=dataset_name,
        version=dataset_version,
        rows=[
            {
                "id": case["name"],
                "input": case["inputs"],
                "expected_output": case.get("expected_output", {}).get("todos", []),
                "metadata": case.get("metadata", {}),
            }
            for case in cases
        ],
        _benchmark_lock=BenchmarkLockMetadata(
            benchmark_id=benchmark.benchmark_id,
            hosted_dataset=benchmark.hosted_dataset,
            hosted_dataset_name=exported.get("name"),
            fetched_at=fetched_at,
            dataset_hash=canonical_dataset_hash(exported),
            case_count=len(cases),
        ),
    )


def _dataset_name_and_version(hosted_name: str) -> tuple[str, str]:
    stem, separator, version = hosted_name.rpartition("_")
    if separator and version.startswith("v"):
        return stem, version
    return hosted_name, "hosted"
