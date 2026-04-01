# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic_evals import Dataset, set_eval_attribute

from app.extract import extract_todos
from app.models import Todo
from evals.extraction_quality.dataset_loader import load_extraction_quality_dataset
from evals.extraction_quality.evaluators import EXTRACTION_QUALITY_EVALUATORS
from evals.extraction_quality.experiment_configs import (
    EXPERIMENTS,
    ExperimentDefinition,
    _read_backend_env_var,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run transcript-to-todo extraction eval experiments.",
    )
    parser.add_argument(
        "--experiment",
        action="append",
        default=[],
        help="Experiment name to run. May be passed multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all configured experiments.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="How many times to run each case per experiment.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum number of concurrent case evaluations within an experiment.",
    )
    parser.add_argument(
        "--list-experiments",
        action="store_true",
        help="Print configured experiment names and availability.",
    )
    return parser


def list_experiments_output() -> str:
    lines: list[str] = []
    for experiment in EXPERIMENTS.values():
        unavailable_reason = experiment.unavailable_reason()
        status = (
            "available"
            if unavailable_reason is None
            else f"unavailable ({unavailable_reason})"
        )
        lines.append(f"{experiment.name}\t{status}")
    return "\n".join(lines)


def _selected_experiments(
    *,
    all_experiments: bool,
    requested_names: Sequence[str],
) -> list[ExperimentDefinition]:
    names = list(EXPERIMENTS) if all_experiments else list(requested_names)
    deduped_names: list[str] = []
    for name in names:
        if name not in deduped_names:
            deduped_names.append(name)

    unknown_names = [name for name in deduped_names if name not in EXPERIMENTS]
    if unknown_names:
        raise ValueError(
            f"Unknown experiment name(s): {', '.join(sorted(unknown_names))}"
        )

    return [EXPERIMENTS[name] for name in deduped_names]


def _build_eval_dataset() -> Dataset[dict[str, Any], list[Todo], dict[str, str]]:
    dataset = load_extraction_quality_dataset()
    return Dataset(
        name=dataset.name,
        cases=dataset.cases,
        evaluators=EXTRACTION_QUALITY_EVALUATORS,
    )


def _ensure_provider_env(experiment: ExperimentDefinition) -> None:
    if experiment.provider != "mistral":
        return

    mistral_api_key = _read_backend_env_var("MISTRAL_API_KEY")
    if mistral_api_key:
        os.environ.setdefault("MISTRAL_API_KEY", mistral_api_key)


def _experiment_metadata(experiment: ExperimentDefinition) -> dict[str, str]:
    return {
        "experiment": experiment.name,
        "model_name": experiment.extraction_config.model_name,
        "prompt_version": experiment.extraction_config.prompt_version,
        "provider": experiment.provider,
        "thinking_mode": experiment.thinking_mode,
    }


def _build_task(experiment: ExperimentDefinition):
    async def run_case(inputs: dict[str, Any]) -> list[Todo]:
        for name, value in _experiment_metadata(experiment).items():
            set_eval_attribute(name, value)

        return await extract_todos(
            inputs["transcript"],
            reference_dt=inputs["reference_dt"],
            previous_todos=inputs["previous_todos"],
            config=experiment.extraction_config,
        )

    return run_case


async def _run_experiment(
    experiment: ExperimentDefinition,
    *,
    repeat: int,
    max_concurrency: int,
) -> None:
    _ensure_provider_env(experiment)
    dataset = _build_eval_dataset()
    metadata = _experiment_metadata(experiment)
    report = await dataset.evaluate(
        _build_task(experiment),
        name=experiment.name,
        task_name="extract_todos",
        metadata=metadata,
        repeat=repeat,
        max_concurrency=max_concurrency,
    )
    report.print(include_metadata=True)


async def _run(args: argparse.Namespace) -> int:
    selected_experiments = _selected_experiments(
        all_experiments=args.all,
        requested_names=args.experiment,
    )

    runnable_experiments: list[ExperimentDefinition] = []
    for experiment in selected_experiments:
        unavailable_reason = experiment.unavailable_reason()
        if unavailable_reason is not None:
            print(f"Skipping {experiment.name}: {unavailable_reason}")
            continue
        runnable_experiments.append(experiment)

    if not runnable_experiments:
        print("No runnable experiments selected.")
        return 0

    for experiment in runnable_experiments:
        await _run_experiment(
            experiment,
            repeat=args.repeat,
            max_concurrency=args.max_concurrency,
        )

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_experiments:
        print(list_experiments_output())
        return 0

    if not args.all and not args.experiment:
        parser.error("Specify --all or at least one --experiment.")
    if args.repeat < 1:
        parser.error("--repeat must be >= 1.")
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be >= 1.")

    try:
        return asyncio.run(_run(args))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
