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

from pydantic_evals import Dataset

from app.extract import extract_todos
from app.logfire_setup import configure_logfire, has_logfire_write_credentials
from app.models import Todo
from evals.common.experiment_metadata import (
    build_batch_id,
    build_experiment_metadata,
)
from evals.common.retry_policy import build_retry_task_config
from evals.extraction_quality import (
    dataset_loader as extraction_dataset_loader,
    evaluators as extraction_evaluators,
)
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
        "--task-retries",
        type=int,
        default=0,
        help="Extra retries for transient task failures before marking a case failed.",
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
    parser.add_argument(
        "--dataset-path",
        type=Path,
        help="Optional dataset override, mainly for smoke runs.",
    )
    parser.add_argument(
        "--allow-untracked",
        action="store_true",
        help="Allow a local smoke run without Logfire write credentials.",
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


def _build_eval_dataset(
    *,
    path: Path | None = None,
) -> Dataset[dict[str, Any], list[Todo], dict[str, str]]:
    dataset = load_extraction_quality_dataset(path=path)
    return Dataset(
        name=dataset.name,
        cases=dataset.cases,
        evaluators=EXTRACTION_QUALITY_EVALUATORS,
    )


def _ensure_provider_env(experiment: ExperimentDefinition) -> None:
    provider_env_var = {
        "deepinfra": "DEEPINFRA_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }.get(experiment.provider)
    if provider_env_var is None:
        return

    api_key = _read_backend_env_var(provider_env_var)
    if api_key:
        os.environ.setdefault(provider_env_var, api_key)


def _build_task(experiment: ExperimentDefinition):
    async def run_case(inputs: dict[str, Any]) -> list[Todo]:
        return await extract_todos(
            inputs["transcript"],
            reference_dt=inputs["reference_dt"],
            previous_todos=inputs["previous_todos"],
            config=experiment.extraction_config,
        )

    return run_case


async def _run(args: argparse.Namespace) -> int:
    if not args.allow_untracked and not has_logfire_write_credentials():
        raise ValueError(
            "Tracked runs require Logfire write credentials. "
            "Pass --allow-untracked for a local smoke run."
        )

    configure_logfire(
        service_name="voice-todos-backend",
        instrument_pydantic_ai=True,
    )
    batch_id = build_batch_id()
    dataset_path = args.dataset_path or extraction_dataset_loader.DATASET_PATH
    dataset = _build_eval_dataset(path=args.dataset_path)
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
        _ensure_provider_env(experiment)
        experiment_id = experiment.name
        metadata = build_experiment_metadata(
            suite="extraction_quality",
            dataset_name=dataset.name,
            dataset_path=dataset_path,
            evaluators_path=Path(extraction_evaluators.__file__),
            experiment_id=experiment_id,
            model_name=experiment.extraction_config.model_name,
            prompt_sha=experiment.prompt_metadata["prompt_sha"],
            repeat=args.repeat,
            task_retries=args.task_retries,
            batch_id=batch_id,
            full_config={
                "provider": experiment.provider,
                "thinking_mode": experiment.thinking_mode,
                "model_settings": experiment.extraction_config.model_settings,
                "prompt_version": experiment.extraction_config.prompt_version,
                "repeat": args.repeat,
                "task_retries": args.task_retries,
                "max_concurrency": args.max_concurrency,
            },
        )
        report = await dataset.evaluate(
            _build_task(experiment),
            name=experiment_id,
            task_name="extract_todos",
            metadata=metadata,
            repeat=args.repeat,
            max_concurrency=args.max_concurrency,
            retry_task=build_retry_task_config(args.task_retries),
        )
        report.print(include_metadata=True)

    print(f"Batch ID: {batch_id}")
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
    if args.task_retries < 0:
        parser.error("--task-retries must be >= 0.")
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be >= 1.")

    try:
        result = _run(args)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
