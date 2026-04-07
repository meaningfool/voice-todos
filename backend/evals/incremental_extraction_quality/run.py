# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic_evals import Dataset, set_eval_attribute
from pydantic_evals.reporting import ReportCase, ReportCaseFailure

from app.extract import extract_todos
from app.logfire_setup import configure_logfire
from app.models import Todo
from evals.common import logfire_enrichment
from evals.common.retry_policy import build_retry_task_config
from evals.extraction_quality.result_artifacts import (
    DEFAULT_RESULTS_DIR,
    reserve_result_dir,
    write_report_artifact,
)
from evals.incremental_extraction_quality.dataset_loader import (
    load_incremental_replay_dataset,
)
from evals.incremental_extraction_quality.evaluators import (
    INCREMENTAL_EXTRACTION_QUALITY_EVALUATORS,
)
from evals.incremental_extraction_quality.experiment_configs import (
    EXPERIMENTS,
    ExperimentDefinition,
    _read_backend_env_var,
)
from evals.incremental_extraction_quality.models import (
    ReplayRunResult,
    ReplayStepResult,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run incremental replay todo extraction eval experiments.",
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
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory where JSON result artifacts are written.",
    )
    parser.add_argument(
        "--skip-logfire-enrichment",
        action="store_true",
        help="Skip the post-run Logfire artifact enrichment pass.",
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


def _ensure_provider_env(experiment: ExperimentDefinition) -> None:
    if experiment.provider != "mistral":
        return

    mistral_api_key = _read_backend_env_var("MISTRAL_API_KEY")
    if mistral_api_key:
        os.environ.setdefault("MISTRAL_API_KEY", mistral_api_key)


def _run_git_command(*args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _get_git_branch() -> str:
    return _run_git_command("branch", "--show-current") or "unknown"


def _get_git_commit_sha() -> str:
    return _run_git_command("rev-parse", "HEAD") or "unknown"


def _experiment_metadata(
    experiment: ExperimentDefinition,
    *,
    dataset_name: str | None = None,
    task_retries: int = 0,
) -> dict[str, Any]:
    return {
        **experiment.identity_metadata,
        "dataset_name": dataset_name or "unknown",
        "task_retries": task_retries,
        "git_branch": _get_git_branch(),
        "git_commit_sha": _get_git_commit_sha(),
    }


def _build_eval_dataset() -> Dataset[dict[str, Any], ReplayRunResult, dict[str, str]]:
    dataset = load_incremental_replay_dataset()
    return Dataset(
        name=dataset.name,
        cases=dataset.cases,
        evaluators=INCREMENTAL_EXTRACTION_QUALITY_EVALUATORS,
    )


async def _run_case(
    inputs: dict[str, Any],
    *,
    experiment: ExperimentDefinition,
    metadata: dict[str, str],
) -> ReplayRunResult:
    for name, value in metadata.items():
        set_eval_attribute(name, value)

    previous_todos: list[Todo] | None = None
    step_results: list[ReplayStepResult] = []

    for step in inputs["replay_steps"]:
        todos = await extract_todos(
            step.transcript,
            reference_dt=inputs["reference_dt"],
            previous_todos=previous_todos,
            config=experiment.extraction_config,
        )
        previous_todos = todos
        step_results.append(
            ReplayStepResult(
                step_index=step.step_index,
                transcript=step.transcript,
                todos=todos,
            )
        )
        set_eval_attribute(
            f"replay_step_{step.step_index}_todos",
            json.dumps(
                [todo.model_dump(mode="json", exclude_none=True) for todo in todos],
                sort_keys=True,
            ),
        )

    return ReplayRunResult(
        final_todos=previous_todos or [],
        step_results=step_results,
    )


def _build_task(
    experiment: ExperimentDefinition,
    *,
    metadata: dict[str, str],
):
    async def run_case(inputs: dict[str, Any]) -> ReplayRunResult:
        return await _run_case(
            inputs,
            experiment=experiment,
            metadata=metadata,
        )

    return run_case


def serialize_replay_case(
    case: ReportCase[Any, ReplayRunResult, Any],
) -> dict[str, Any]:
    return {
        "name": case.name,
        "source_fixture": (case.metadata or {}).get("source_fixture"),
        "expected_final_todo_count": case.metrics.get(
            "expected_final_todo_count",
            len(case.expected_output or []),
        ),
        "predicted_final_todo_count": case.metrics.get(
            "predicted_final_todo_count",
            len(case.output.final_todos),
        ),
        "step_results": [
            {
                "step_index": step_result.step_index,
                "transcript": step_result.transcript,
                "todos": [
                    todo.model_dump(mode="json", exclude_none=True)
                    for todo in step_result.todos
                ],
            }
            for step_result in case.output.step_results
        ],
        "trace_id": case.trace_id,
        "span_id": case.span_id,
    }


def serialize_replay_failure(
    case: ReportCaseFailure[Any, Any, Any],
) -> dict[str, Any]:
    return {
        "name": case.name,
        "source_fixture": (case.metadata or {}).get("source_fixture"),
        "expected_final_todo_count": len(case.expected_output or []),
        "predicted_final_todo_count": None,
        "error_message": case.error_message,
        "trace_id": case.trace_id,
        "span_id": case.span_id,
    }


async def _run_experiment(
    experiment: ExperimentDefinition,
    *,
    repeat: int,
    task_retries: int,
    max_concurrency: int,
    result_dir: Path,
    artifact_timestamp: datetime,
) -> Path:
    _ensure_provider_env(experiment)
    dataset = _build_eval_dataset()
    metadata = _experiment_metadata(
        experiment,
        dataset_name=dataset.name,
        task_retries=task_retries,
    )
    report = await dataset.evaluate(
        _build_task(experiment, metadata=metadata),
        name=experiment.name,
        task_name="extract_todos_replay",
        metadata=metadata,
        repeat=repeat,
        max_concurrency=max_concurrency,
        retry_task=build_retry_task_config(task_retries),
    )
    report.print(include_metadata=True)
    artifact_path = write_report_artifact(
        report,
        result_dir=result_dir,
        repeat=repeat,
        max_concurrency=max_concurrency,
        task_retries=task_retries,
        timestamp=artifact_timestamp,
        serialize_case=serialize_replay_case,
        serialize_failure=serialize_replay_failure,
    )
    print(f"Wrote artifact: {artifact_path}")
    return artifact_path


async def enrich_experiment_artifacts(
    *,
    result_dir: Path,
    artifact_paths: Sequence[Path],
    read_token: str | None = None,
) -> list[dict[str, Any]]:
    return await logfire_enrichment.write_run_summary(
        result_dir=result_dir,
        artifact_paths=artifact_paths,
        read_token=read_token,
    )


async def _run(args: argparse.Namespace) -> int:
    configure_logfire(
        service_name="voice-todos-backend",
        instrument_pydantic_ai=True,
    )
    artifact_timestamp = datetime.now(UTC)
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

    result_dir = reserve_result_dir(
        output_dir=args.output_dir,
        timestamp=artifact_timestamp,
    )

    artifact_paths: list[Path] = []
    for experiment in runnable_experiments:
        artifact_paths.append(
            await _run_experiment(
                experiment,
                repeat=args.repeat,
                task_retries=args.task_retries,
                max_concurrency=args.max_concurrency,
                result_dir=result_dir,
                artifact_timestamp=artifact_timestamp,
            )
        )

    if not args.skip_logfire_enrichment:
        try:
            await enrich_experiment_artifacts(
                result_dir=result_dir,
                artifact_paths=artifact_paths,
            )
        except Exception as exc:
            print(
                f"Best-effort Logfire enrichment failed: {exc}",
                file=sys.stderr,
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
    if args.task_retries < 0:
        parser.error("--task-retries must be >= 0.")
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be >= 1.")

    try:
        return asyncio.run(_run(args))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
