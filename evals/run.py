from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass, field
from pathlib import Path

from evals.hosted_datasets import canonical_dataset_hash, export_hosted_dataset
from evals.models import BenchmarkRunResult
from evals.resolution import resolve_entry_config
from evals.storage import (
    benchmark_lock_path,
    lock_from_exported_dataset,
    load_benchmark_by_id,
    load_benchmark_lock,
    write_benchmark_lock,
)
from evals.models import LockedDatasetDefinition


@dataclass
class CurrentBenchmarkState:
    current_entry_ids: set[str] = field(default_factory=set)


@dataclass
class BenchmarkLockState:
    active_lock_exists: bool
    stale: bool
    lock_path: Path
    locked_dataset_hash: str | None = None
    current_hosted_dataset_hash: str | None = None
    exported_payload: dict | None = None


class BenchmarkStaleError(RuntimeError):
    def __init__(self, *, benchmark_id: str, lock_path: Path):
        self.benchmark_id = benchmark_id
        self.lock_path = lock_path
        super().__init__(
            f"Benchmark '{benchmark_id}' is stale. Re-run with --allow-stale to keep using "
            f"the locked snapshot at {lock_path}, or --rebase to adopt the current hosted dataset."
        )


def load_current_benchmark_state(benchmark) -> CurrentBenchmarkState:
    try:
        from evals.report import build_benchmark_report

        report = build_benchmark_report(benchmark_id=benchmark.benchmark_id)
    except Exception:
        return CurrentBenchmarkState()

    return CurrentBenchmarkState(
        current_entry_ids={
            entry.entry_id for entry in report.entries if entry.status == "current"
        }
    )


async def launch_extraction_entry(**kwargs):
    from evals.extraction_quality.run import (
        launch_extraction_entry as _launch_extraction_entry,
    )

    return await _launch_extraction_entry(**kwargs)


async def launch_replay_entry(**kwargs):
    from evals.incremental_extraction_quality.run import (
        launch_replay_entry as _launch_replay_entry,
    )

    return await _launch_replay_entry(**kwargs)


async def run_benchmark(
    *,
    benchmark_id: str,
    all_entries: bool,
    dataset_path: Path | None = None,
    allow_untracked: bool,
    allow_stale: bool = False,
    rebase: bool = False,
) -> BenchmarkRunResult:
    benchmark = load_benchmark_by_id(benchmark_id)
    resolved_dataset_path = dataset_path
    force_all_entries = False
    if resolved_dataset_path is None:
        lock_state = inspect_benchmark_lock_state(benchmark)
        if not lock_state.active_lock_exists:
            resolved_dataset_path = _write_lock_from_export(benchmark, lock_state.exported_payload)
        elif lock_state.stale:
            if rebase:
                resolved_dataset_path = _write_lock_from_export(
                    benchmark,
                    lock_state.exported_payload,
                )
                force_all_entries = True
            elif allow_stale:
                resolved_dataset_path = lock_state.lock_path
            else:
                raise BenchmarkStaleError(
                    benchmark_id=benchmark.benchmark_id,
                    lock_path=lock_state.lock_path,
                )
        else:
            resolved_dataset_path = lock_state.lock_path

    state = CurrentBenchmarkState() if force_all_entries else load_current_benchmark_state(benchmark)
    entries = [
        entry
        for entry in benchmark.entries
        if all_entries or entry.id not in state.current_entry_ids
    ]

    batch_ids: dict[str, str] = {}
    for entry in entries:
        resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
        if resolved.suite == "extraction_quality":
            result = await launch_extraction_entry(
                entry=entry,
                resolved_config=resolved,
                dataset_path=resolved_dataset_path,
                repeat=benchmark.repeat,
                task_retries=benchmark.task_retries,
                max_concurrency=benchmark.max_concurrency,
                allow_untracked=allow_untracked,
            )
        elif resolved.suite == "incremental_extraction_quality":
            result = await launch_replay_entry(
                entry=entry,
                resolved_config=resolved,
                dataset_path=resolved_dataset_path,
                repeat=benchmark.repeat,
                task_retries=benchmark.task_retries,
                max_concurrency=benchmark.max_concurrency,
                allow_untracked=allow_untracked,
            )
        else:
            continue
        batch_id = result.get("batch_id")
        if batch_id:
            batch_ids[entry.id] = batch_id

    return BenchmarkRunResult(
        benchmark_id=benchmark.benchmark_id,
        executed_entry_ids=[entry.id for entry in entries],
        batch_ids=batch_ids,
    )


def inspect_benchmark_lock_state(benchmark) -> BenchmarkLockState:
    lock_path = benchmark_lock_path(benchmark.benchmark_id)
    existing_lock = load_benchmark_lock(benchmark.benchmark_id)
    exported = export_hosted_dataset(benchmark.hosted_dataset)
    current_hash = canonical_dataset_hash(exported)
    if existing_lock is None:
        return BenchmarkLockState(
            active_lock_exists=False,
            stale=False,
            lock_path=lock_path,
            current_hosted_dataset_hash=current_hash,
            exported_payload=exported,
        )

    locked_hash = existing_lock.benchmark_lock.dataset_hash
    return BenchmarkLockState(
        active_lock_exists=True,
        stale=current_hash != locked_hash,
        lock_path=lock_path,
        locked_dataset_hash=locked_hash,
        current_hosted_dataset_hash=current_hash,
        exported_payload=exported,
    )


def _write_lock_from_export(benchmark, exported: dict | None) -> Path:
    if exported is None:
        exported = export_hosted_dataset(benchmark.hosted_dataset)
    lock = lock_from_exported_dataset(
        benchmark=benchmark,
        exported=exported,
        fetched_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    return write_benchmark_lock(lock)
