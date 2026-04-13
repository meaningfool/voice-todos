from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from evals.models import BenchmarkRunResult
from evals.resolution import resolve_entry_config
from evals.storage import load_benchmark_by_id


@dataclass
class CurrentBenchmarkState:
    current_entry_ids: set[str] = field(default_factory=set)


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
) -> BenchmarkRunResult:
    benchmark = load_benchmark_by_id(benchmark_id)
    resolved_dataset_path = dataset_path or Path(__file__).resolve().parents[1] / benchmark.dataset
    state = load_current_benchmark_state(benchmark)
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
