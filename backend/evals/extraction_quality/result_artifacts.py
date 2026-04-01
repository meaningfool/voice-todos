from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_evals.reporting import EvaluationReport, ReportCase, ReportCaseFailure

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


def build_report_artifact(
    report: EvaluationReport[Any, Any, Any],
    *,
    repeat: int,
    max_concurrency: int,
    timestamp: datetime,
) -> dict[str, Any]:
    metadata = report.experiment_metadata or {}
    averages = report.averages()

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
        "aggregate_metrics": averages.metrics if averages else {},
        "cases": [_serialize_case(case) for case in report.cases],
        "failures": [_serialize_failure(case) for case in report.failures],
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
    )
    with artifact_path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return artifact_path
