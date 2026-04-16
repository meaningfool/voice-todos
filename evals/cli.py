# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from evals.storage import list_benchmark_ids, load_benchmark_by_id


def run_benchmark(**kwargs):
    from evals.run import BenchmarkStaleError, run_benchmark as _run_benchmark

    try:
        return asyncio.run(_run_benchmark(**kwargs))
    except BenchmarkStaleError as exc:
        return exc


def report_benchmark(**kwargs):
    from evals.report import report_benchmark as _report_benchmark

    return _report_benchmark(**kwargs)


def report_benchmark_html(**kwargs):
    from evals.report_html import ensure_benchmark_report_html as _report_benchmark_html

    return _report_benchmark_html(**kwargs)


def open_benchmark_report_html(**kwargs):
    from evals.report_html import open_benchmark_report_html as _open_benchmark_report_html

    return _open_benchmark_report_html(**kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark-first eval workflows.")
    root = parser.add_subparsers(dest="resource", required=True)
    benchmark = root.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="command", required=True)
    benchmark_sub.add_parser("list")
    show = benchmark_sub.add_parser("show")
    show.add_argument("benchmark_id")
    run = benchmark_sub.add_parser("run")
    run.add_argument("benchmark_id")
    run.add_argument("--all", action="store_true")
    run.add_argument("--dataset-path")
    run.add_argument("--allow-stale", action="store_true")
    run.add_argument("--rebase", action="store_true")
    run.add_argument("--allow-untracked", action="store_true")
    report = benchmark_sub.add_parser("report")
    report.add_argument("benchmark_id")
    report_mode = report.add_mutually_exclusive_group()
    report_mode.add_argument("--json", action="store_true")
    report_mode.add_argument("--html", action="store_true")
    report_mode.add_argument("--open", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.resource != "benchmark":
        raise SystemExit(f"unsupported resource: {args.resource}")

    if args.command == "list":
        for benchmark_id in list_benchmark_ids():
            print(benchmark_id)
        return 0

    if args.command == "show":
        benchmark = load_benchmark_by_id(args.benchmark_id)
        print(json.dumps(benchmark.model_dump(), indent=2))
        return 0

    if args.command == "run":
        result = run_benchmark(
            benchmark_id=args.benchmark_id,
            all_entries=args.all,
            dataset_path=Path(args.dataset_path) if args.dataset_path else None,
            allow_untracked=args.allow_untracked,
            allow_stale=args.allow_stale,
            rebase=args.rebase,
        )
        if isinstance(result, Exception):
            print(str(result))
            return 1
        if not result.executed_entry_ids:
            print("No entries executed.")
            return 0

        batch_ids = getattr(result, "batch_ids", {})
        unique_batch_ids = sorted({batch_id for batch_id in batch_ids.values() if batch_id})
        if len(unique_batch_ids) == 1:
            print(f"Batch ID: {unique_batch_ids[0]}")
        elif unique_batch_ids:
            print(f"Batch IDs: {', '.join(unique_batch_ids)}")
        print(f"Executed entries: {', '.join(result.executed_entry_ids)}")
        return 0

    if args.command == "report":
        if args.open:
            result = open_benchmark_report_html(benchmark_id=args.benchmark_id)
        elif args.html:
            result = report_benchmark_html(benchmark_id=args.benchmark_id)
        else:
            result = report_benchmark(
                benchmark_id=args.benchmark_id,
                json_output=args.json,
            )
        if result is not None:
            print(result)
        return 0

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
