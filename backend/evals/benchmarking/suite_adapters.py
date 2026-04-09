from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from evals.extraction_quality import run as extraction_quality_run
from evals.incremental_extraction_quality import (
    run as incremental_extraction_quality_run,
)


@dataclass(frozen=True)
class SuiteAdapter:
    experiments: dict[str, Any]
    launch_helper: Callable[[argparse.Namespace], Awaitable[Any]]


SUPPORTED_SUITES: dict[str, SuiteAdapter] = {
    "extraction_quality": SuiteAdapter(
        experiments=extraction_quality_run.EXPERIMENTS,
        launch_helper=extraction_quality_run.launch_experiments,
    ),
    "incremental_extraction_quality": SuiteAdapter(
        experiments=incremental_extraction_quality_run.EXPERIMENTS,
        launch_helper=incremental_extraction_quality_run.launch_experiments,
    ),
}


def _require_suite_adapter(suite: str) -> SuiteAdapter:
    try:
        return SUPPORTED_SUITES[suite]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_SUITES))
        raise ValueError(
            f"Unsupported benchmark suite '{suite}'. Supported suites: {supported}"
        ) from exc


def resolve_coordinate_experiments(
    *,
    suite: str,
    coordinate: dict[str, str],
    fixed_config: dict[str, str],
) -> list[str]:
    adapter = _require_suite_adapter(suite)
    requested_metadata = {
        **fixed_config,
        **coordinate,
    }

    matches: list[str] = []
    for experiment in adapter.experiments.values():
        identity_metadata = experiment.identity_metadata
        if all(
            identity_metadata.get(key) == value
            for key, value in requested_metadata.items()
        ):
            matches.append(experiment.name)
    return matches


def launch_benchmark_experiments(
    *,
    suite: str,
    experiment_names: Sequence[str],
    repeat: int = 1,
    task_retries: int = 0,
    max_concurrency: int = 1,
    dataset_path: Path | None = None,
    allow_untracked: bool = False,
) -> list[dict[str, str]]:
    if not experiment_names:
        return []

    adapter = _require_suite_adapter(suite)
    args = argparse.Namespace(
        experiment=list(dict.fromkeys(experiment_names)),
        all=False,
        repeat=repeat,
        task_retries=task_retries,
        max_concurrency=max_concurrency,
        list_experiments=False,
        dataset_path=dataset_path,
        allow_untracked=allow_untracked,
    )
    result = asyncio.run(adapter.launch_helper(args))
    return list(result.launched_experiments)
