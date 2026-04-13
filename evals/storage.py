from __future__ import annotations

import json
from pathlib import Path

import yaml

from evals.models import BenchmarkDefinition, DatasetDefinition

BENCHMARKS_DIR = Path(__file__).resolve().parent / "benchmarks"


def load_dataset_definition(path: Path) -> DatasetDefinition:
    return DatasetDefinition.model_validate(json.loads(path.read_text()))


def load_benchmark_definition(path: Path) -> BenchmarkDefinition:
    return BenchmarkDefinition.model_validate(yaml.safe_load(path.read_text()))


def list_benchmark_ids() -> list[str]:
    return sorted(path.stem for path in BENCHMARKS_DIR.glob("*.yaml"))


def load_benchmark_by_id(benchmark_id: str) -> BenchmarkDefinition:
    return load_benchmark_definition(BENCHMARKS_DIR / f"{benchmark_id}.yaml")
