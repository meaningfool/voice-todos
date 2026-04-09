from __future__ import annotations

import argparse
from pathlib import Path

from evals.benchmarking.storage import (
    attach_experiment,
    load_benchmark_manifest,
    save_benchmark_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark workflows for eval experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    attach = subparsers.add_parser("attach")
    attach.add_argument("manifest_path", type=Path)
    attach.add_argument("--experiment-run-id", required=True)
    attach.add_argument("--note")

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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "attach":
        return _attach_command(args)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
