# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.benchmarking import suite_adapters
from evals.benchmarking.coverage import (
    build_benchmark_coverage,
    expected_coordinates,
)
from evals.benchmarking.logfire_query import LogfireBenchmarkQueryClient
from evals.benchmarking.reporting import build_benchmark_report
from evals.benchmarking.storage import (
    attach_experiment,
    load_benchmark_manifest,
    save_benchmark_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark workflows for eval experiments."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    attach = subparsers.add_parser("attach")
    attach.add_argument("manifest_path", type=Path)
    attach.add_argument("--experiment-run-id", required=True)
    attach.add_argument("--note")

    launch = subparsers.add_parser("launch")
    launch.add_argument("manifest_path", type=Path)
    launch.add_argument(
        "--coordinate",
        action="append",
        default=[],
        help="Coordinate selector as axis=value[,axis=value...]",
    )
    launch.add_argument(
        "--missing-only",
        action="store_true",
        help="Launch only coordinates that are still missing from the benchmark.",
    )
    launch.add_argument("--repeat", type=int, default=1)
    launch.add_argument("--task-retries", type=int, default=0)
    launch.add_argument("--max-concurrency", type=int, default=1)
    launch.add_argument("--dataset-path", type=Path)
    launch.add_argument("--allow-untracked", action="store_true")

    coverage = subparsers.add_parser("coverage")
    coverage.add_argument("manifest_path", type=Path)

    report = subparsers.add_parser("report")
    report.add_argument("manifest_path", type=Path)

    return parser


def _attach_command(args: argparse.Namespace) -> int:
    manifest = load_benchmark_manifest(args.manifest_path)
    attach_experiment(
        manifest,
        experiment_run_id=args.experiment_run_id,
        note=args.note,
    )
    save_benchmark_manifest(args.manifest_path, manifest)
    return 0


def _parse_coordinate_selector(raw_selector: str) -> dict[str, str]:
    selector: dict[str, str] = {}

    for part in raw_selector.split(","):
        key, separator, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise ValueError(
                f"Invalid coordinate selector '{raw_selector}'. "
                "Expected axis=value[,axis=value...]"
            )
        selector[key] = value

    return selector


def _coordinate_key(coordinate: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(coordinate.items()))


def _matches_selector(
    coordinate: dict[str, str],
    selector: dict[str, str],
) -> bool:
    return all(coordinate.get(key) == value for key, value in selector.items())


def _selected_coordinates(
    manifest,
    raw_selectors: list[str],
) -> list[dict[str, str]]:
    coordinates = expected_coordinates(manifest)
    if not raw_selectors:
        return coordinates

    axis_fields = {axis.field for axis in manifest.axes}
    selectors = [
        _parse_coordinate_selector(raw_selector) for raw_selector in raw_selectors
    ]
    for selector in selectors:
        unknown_fields = sorted(set(selector) - axis_fields)
        if unknown_fields:
            raise ValueError(
                f"Unknown benchmark axis field(s): {', '.join(unknown_fields)}"
            )

    selected = [
        coordinate
        for coordinate in coordinates
        if any(_matches_selector(coordinate, selector) for selector in selectors)
    ]
    return selected


def _missing_coordinates(manifest) -> list[dict[str, str]]:
    if not manifest.attached_experiment_runs:
        return expected_coordinates(manifest)

    report = build_benchmark_report(
        manifest=manifest,
        query_client=LogfireBenchmarkQueryClient(),
    )
    return report.missing_coordinates


def _fetch_attached_records(manifest) -> list[dict[str, str]]:
    query_client = LogfireBenchmarkQueryClient()
    return asyncio.run(
        query_client.fetch_attached_experiments(manifest.attached_experiment_runs)
    )


def _resolve_experiment_names(
    *,
    suite: str,
    coordinates: list[dict[str, str]],
    fixed_config: dict[str, str],
) -> list[str]:
    experiment_names: list[str] = []

    for coordinate in coordinates:
        matches = suite_adapters.resolve_coordinate_experiments(
            suite=suite,
            coordinate=coordinate,
            fixed_config=fixed_config,
        )
        if not matches:
            raise ValueError(
                "No experiments match benchmark coordinate "
                f"{coordinate} for suite '{suite}'."
            )
        if len(matches) > 1:
            raise ValueError(
                f"Benchmark coordinate {coordinate} is ambiguous for suite '{suite}': "
                f"{', '.join(matches)}"
            )
        experiment_name = matches[0]
        if experiment_name not in experiment_names:
            experiment_names.append(experiment_name)

    return experiment_names


def _launch_command(args: argparse.Namespace) -> int:
    manifest = load_benchmark_manifest(args.manifest_path)
    selected_coordinates = _selected_coordinates(manifest, args.coordinate)

    if args.missing_only:
        missing_coordinate_keys = {
            _coordinate_key(coordinate) for coordinate in _missing_coordinates(manifest)
        }
        selected_coordinates = [
            coordinate
            for coordinate in selected_coordinates
            if _coordinate_key(coordinate) in missing_coordinate_keys
        ]

    experiment_names = _resolve_experiment_names(
        suite=manifest.suite,
        coordinates=selected_coordinates,
        fixed_config=manifest.fixed_config,
    )
    launched_refs = suite_adapters.launch_benchmark_experiments(
        suite=manifest.suite,
        experiment_names=experiment_names,
        repeat=args.repeat,
        task_retries=args.task_retries,
        max_concurrency=args.max_concurrency,
        dataset_path=args.dataset_path,
        allow_untracked=args.allow_untracked,
    )

    for launched_ref in launched_refs:
        attach_experiment(
            manifest,
            experiment_run_id=launched_ref["experiment_run_id"],
        )

    save_benchmark_manifest(args.manifest_path, manifest)
    return 0


def _coverage_command(args: argparse.Namespace) -> int:
    manifest = load_benchmark_manifest(args.manifest_path)
    coverage = build_benchmark_coverage(
        manifest,
        _fetch_attached_records(manifest),
    )
    print(coverage.model_dump_json(indent=2))
    return 0


def _report_command(args: argparse.Namespace) -> int:
    manifest = load_benchmark_manifest(args.manifest_path)
    report = build_benchmark_report(
        manifest=manifest,
        query_client=LogfireBenchmarkQueryClient(),
    )
    print(report.model_dump_json(indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "attach":
            return _attach_command(args)
        if args.command == "launch":
            if args.repeat < 1:
                parser.error("--repeat must be >= 1.")
            if args.task_retries < 0:
                parser.error("--task-retries must be >= 0.")
            if args.max_concurrency < 1:
                parser.error("--max-concurrency must be >= 1.")
            return _launch_command(args)
        if args.command == "coverage":
            return _coverage_command(args)
        if args.command == "report":
            return _report_command(args)
    except ValueError as exc:
        parser.error(str(exc))

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
