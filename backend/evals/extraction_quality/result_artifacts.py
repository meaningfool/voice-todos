from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_evals.reporting import EvaluationReport, ReportCase, ReportCaseFailure

from evals.common.failure_classification import classify_failure_category

DEFAULT_RESULTS_DIR = Path(__file__).with_name("results")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_result_dir(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _result_dir_name(timestamp: datetime, *, suffix: int = 0) -> str:
    base_name = _format_result_dir(timestamp)
    if suffix == 0:
        return base_name
    return f"{base_name}-{suffix:02d}"


def _serialize_case(case: ReportCase[Any, Any, Any]) -> dict[str, Any]:
    return {
        "name": case.name,
        "source_fixture": (case.metadata or {}).get("source_fixture"),
        "expected_todo_count": case.metrics.get(
            "expected_todo_count",
            len(case.expected_output or []),
        ),
        "predicted_todo_count": case.metrics.get(
            "predicted_todo_count",
            len(case.output or []),
        ),
        "trace_id": case.trace_id,
        "span_id": case.span_id,
    }


def _serialize_failure(case: ReportCaseFailure[Any, Any, Any]) -> dict[str, Any]:
    return {
        "name": case.name,
        "source_fixture": (case.metadata or {}).get("source_fixture"),
        "expected_todo_count": len(case.expected_output or []),
        "predicted_todo_count": None,
        "error_message": case.error_message,
        "trace_id": case.trace_id,
        "span_id": case.span_id,
    }


def _count_failure_categories(
    failures: list[ReportCaseFailure[Any, Any, Any]],
) -> dict[str, int]:
    failure_counts: dict[str, int] = {}
    for failure in failures:
        category = classify_failure_category(failure.error_message)
        failure_counts[category] = failure_counts.get(category, 0) + 1
    return failure_counts


def build_report_artifact(
    report: EvaluationReport[Any, Any, Any],
    *,
    repeat: int,
    max_concurrency: int,
    timestamp: datetime,
    serialize_case: Callable[[ReportCase[Any, Any, Any]], dict[str, Any]] | None = None,
    serialize_failure: (
        Callable[[ReportCaseFailure[Any, Any, Any]], dict[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    metadata = report.experiment_metadata or {}
    averages = report.averages()
    case_serializer = serialize_case or _serialize_case
    failure_serializer = serialize_failure or _serialize_failure
    completed_cases = len(report.cases)
    failure_count = len(report.failures)
    total_cases = completed_cases + failure_count
    overall_case_success_rate = (
        completed_cases / total_cases if total_cases else 0.0
    )

    return {
        "timestamp": _format_timestamp(timestamp),
        "dataset_name": metadata.get("dataset_name"),
        "experiment_id": metadata.get("experiment", report.name),
        "model": {
            "name": metadata.get("model_name"),
            "provider": metadata.get("provider"),
            "thinking_mode": metadata.get("thinking_mode"),
        },
        "prompt": {
            "family": metadata.get("prompt_family"),
            "version": metadata.get("prompt_version"),
            "sha": metadata.get("prompt_sha"),
        },
        "git": {
            "branch": metadata.get("git_branch"),
            "commit_sha": metadata.get("git_commit_sha"),
        },
        "repeat": repeat,
        "max_concurrency": max_concurrency,
        "completed_cases": completed_cases,
        "failure_count": failure_count,
        "overall_case_success_rate": overall_case_success_rate,
        "failure_counts_by_category": _count_failure_categories(report.failures),
        "aggregate_metrics": averages.metrics if averages else {},
        "cases": [case_serializer(case) for case in report.cases],
        "failures": [
            {
                **failure_serializer(case),
                "failure_category": classify_failure_category(case.error_message),
            }
            for case in report.failures
        ],
        "trace_id": report.trace_id,
        "span_id": report.span_id,
    }


def reserve_result_dir(
    *,
    output_dir: Path = DEFAULT_RESULTS_DIR,
    timestamp: datetime | None = None,
) -> Path:
    artifact_timestamp = timestamp or _utc_now()
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = 0
    while True:
        result_dir = output_dir / _result_dir_name(artifact_timestamp, suffix=suffix)
        try:
            result_dir.mkdir()
        except FileExistsError:
            suffix += 1
            continue
        return result_dir


def write_report_artifact(
    report: EvaluationReport[Any, Any, Any],
    *,
    output_dir: Path = DEFAULT_RESULTS_DIR,
    result_dir: Path | None = None,
    repeat: int,
    max_concurrency: int,
    timestamp: datetime | None = None,
    serialize_case: Callable[[ReportCase[Any, Any, Any]], dict[str, Any]] | None = None,
    serialize_failure: (
        Callable[[ReportCaseFailure[Any, Any, Any]], dict[str, Any]] | None
    ) = None,
) -> Path:
    artifact_timestamp = timestamp or _utc_now()
    resolved_result_dir = result_dir or reserve_result_dir(
        output_dir=output_dir,
        timestamp=artifact_timestamp,
    )
    resolved_result_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = resolved_result_dir / f"{report.name}.json"

    payload = build_report_artifact(
        report,
        repeat=repeat,
        max_concurrency=max_concurrency,
        timestamp=artifact_timestamp,
        serialize_case=serialize_case,
        serialize_failure=serialize_failure,
    )
    with artifact_path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return artifact_path
