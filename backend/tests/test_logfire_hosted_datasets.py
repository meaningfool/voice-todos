from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.hosted_datasets import canonical_dataset_hash, serialize_dataset_payload
from evals.models import BenchmarkLockMetadata, LockedDatasetDefinition
from evals.storage import (
    benchmark_lock_path,
    load_benchmark_by_id,
    load_benchmark_lock,
    write_benchmark_lock,
)


def test_benchmark_definition_uses_hosted_dataset_identity():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")

    assert isinstance(benchmark.hosted_dataset, str)
    assert benchmark.hosted_dataset


def test_lock_path_is_under_evals_locks():
    path = benchmark_lock_path("todo_extraction_bench_v1")

    assert path.name == "todo_extraction_bench_v1.json"
    assert path.parent.name == "locks"


def test_storage_allows_benchmark_dir_override(monkeypatch, tmp_path):
    benchmark_path = tmp_path / "sample.yaml"
    benchmark_path.write_text(
        "\n".join(
                [
                    "benchmark_id: sample",
                    "hosted_dataset: ds_sample",
                    "dataset_family: extraction",
                    "focus: model",
                    "headline_metric: score",
                    "repeat: 1",
                    "task_retries: 0",
                "max_concurrency: 1",
                "entries: []",
            ]
        )
    )
    monkeypatch.setenv("EVALS_BENCHMARKS_DIR", str(tmp_path))

    benchmark = load_benchmark_by_id("sample")

    assert benchmark.benchmark_id == "sample"
    assert benchmark.hosted_dataset == "ds_sample"


def test_canonical_hash_is_stable_for_equivalent_payload_order():
    left = {
        "name": "todo_extraction",
        "version": "v1",
        "rows": [{"id": "a", "input": {"x": 1}, "expected_output": []}],
    }
    right = {
        "rows": [{"expected_output": [], "input": {"x": 1}, "id": "a"}],
        "version": "v1",
        "name": "todo_extraction",
    }

    assert canonical_dataset_hash(left) == canonical_dataset_hash(right)


def test_serialize_dataset_payload_is_canonical_json():
    payload = {
        "rows": [{"expected_output": [], "input": {"x": 1}, "id": "a"}],
        "version": "v1",
        "name": "todo_extraction",
    }

    assert serialize_dataset_payload(payload) == json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_write_and_load_benchmark_lock_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lock = LockedDatasetDefinition(
        name="todo_extraction",
        version="v1",
        rows=[{"id": "a", "input": {"x": 1}, "expected_output": []}],
        _benchmark_lock=BenchmarkLockMetadata(
            benchmark_id="todo_extraction_bench_v1",
            hosted_dataset="ds_todo_extraction_placeholder",
            hosted_dataset_name="todo_extraction",
            fetched_at="2026-04-13T00:00:00+00:00",
            dataset_hash="abc123",
            case_count=1,
        ),
    )

    written = write_benchmark_lock(lock)
    loaded = load_benchmark_lock("todo_extraction_bench_v1")

    assert written.name == "todo_extraction_bench_v1.json"
    assert written.parent.name == "locks"
    assert loaded is not None
    assert loaded.benchmark_lock.dataset_hash == "abc123"
    assert loaded.rows[0].id == "a"
