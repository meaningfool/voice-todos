from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from logfire.query_client import AsyncLogfireQueryClient

from app.logfire_setup import _read_backend_env_var
from evals.common.failure_classification import classify_failure_category

SUMMARY_FILENAME = "summary.json"
SUMMARY_STATUS_OK = "ok"
SUMMARY_STATUS_PARTIAL = "partial"
SUMMARY_STATUS_SKIPPED = "skipped"
SummaryStatus = Literal["ok", "partial", "skipped"]

_QUERY_LIMIT = 10_000


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_run_timestamp(result_dir: Path) -> str:
    try:
        return _format_timestamp(
            datetime.strptime(result_dir.name, "%Y-%m-%dT%H-%M-%SZ").replace(
                tzinfo=UTC
            )
        )
    except ValueError:
        return _format_timestamp(_utc_now())


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed.is_integer():
            return int(parsed)
    return None


def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_artifact_payloads(result_dir: Path) -> list[dict[str, Any]]:
    artifact_paths = sorted(
        path
        for path in result_dir.glob("*.json")
        if path.name != SUMMARY_FILENAME and path.is_file()
    )
    return [_load_json_file(path) for path in artifact_paths]


def _build_case_row(
    *,
    case_payload: Mapping[str, Any],
    failure_payload: Mapping[str, Any] | None,
    rows_by_span_id: dict[str, dict[str, Any]],
    child_rows_by_parent_span_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    span_id = case_payload.get("span_id")
    case_name = case_payload.get("name")
    matching_row = rows_by_span_id.get(span_id) if isinstance(span_id, str) else None
    candidate_rows: list[dict[str, Any]] = []
    if matching_row is not None:
        candidate_rows.append(matching_row)
        candidate_rows.extend(
            _collect_descendant_rows(matching_row, child_rows_by_parent_span_id)
        )

    duration_row = matching_row
    if duration_row is None and candidate_rows:
        duration_row = candidate_rows[0]

    duration_s = _first_numeric(
        [duration_row, *candidate_rows],
        "duration",
    )
    token_metrics = _collect_token_metrics(candidate_rows)
    exception_summary = _first_non_empty(
        _extract_text_value(matching_row, "exception_message"),
        _extract_text_value(matching_row, "message"),
        (failure_payload or {}).get("error_message"),
    )

    row_status = "failure" if failure_payload is not None else "success"
    failure_category = (
        classify_failure_category(failure_payload.get("error_message"))
        if failure_payload is not None
        else None
    )
    if row_status == "success" and duration_row is not None:
        exception_summary = _first_non_empty(
            exception_summary,
            _extract_text_value(duration_row, "exception_message"),
        )

    return {
        "name": case_name,
        "status": row_status,
        "duration_s": duration_s,
        "failure_category": failure_category,
        "exception_summary": exception_summary,
        "token_metrics": token_metrics,
    }


def _collect_descendant_rows(
    row: Mapping[str, Any],
    child_rows_by_parent_span_id: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    span_id = row.get("span_id")
    if not isinstance(span_id, str):
        return []

    descendants: list[dict[str, Any]] = []
    stack = list(child_rows_by_parent_span_id.get(span_id, []))
    while stack:
        child_row = stack.pop(0)
        descendants.append(child_row)
        child_span_id = child_row.get("span_id")
        if isinstance(child_span_id, str):
            stack.extend(child_rows_by_parent_span_id.get(child_span_id, []))
    return descendants


def _extract_attributes(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}

    raw_attributes = row.get("attributes")
    if isinstance(raw_attributes, dict):
        return dict(raw_attributes)
    if isinstance(raw_attributes, str):
        try:
            decoded = json.loads(raw_attributes)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _extract_text_value(row: Mapping[str, Any] | None, key: str) -> str | None:
    if row is None:
        return None

    value = row.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_numeric(
    rows: Sequence[Mapping[str, Any] | None],
    key: str,
) -> float | None:
    for row in rows:
        if row is None:
            continue
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def _collect_token_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    collected: dict[str, Any] = {}
    metric_names = (
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "requests",
        "cost",
        "cost_usd",
        "total_cost",
    )
    for row in rows:
        row_values = {**row, **_extract_attributes(row)}
        for metric_name in metric_names:
            if metric_name in row_values:
                raw_value = row_values[metric_name]
                normalized = _as_int(raw_value)
                if normalized is None:
                    normalized = _as_float(raw_value)
                if normalized is not None:
                    collected[metric_name] = normalized
    return {key: collected[key] for key in sorted(collected)}


def _query_sql(trace_id: str) -> str:
    escaped_trace_id = trace_id.replace("'", "''")
    return (
        "SELECT trace_id, span_id, parent_span_id, span_name, kind, message, "
        "duration, attributes, exception_type, exception_message, "
        "http_response_status_code, otel_status_code "
        "FROM records "
        f"WHERE trace_id = '{escaped_trace_id}' "
        "ORDER BY start_timestamp ASC"
    )


def _build_local_experiment_summary(
    artifact_payload: Mapping[str, Any],
    *,
    status: SummaryStatus,
    reason: str | None,
    rows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = list(artifact_payload.get("cases", []) or [])
    failures = list(artifact_payload.get("failures", []) or [])

    rows_by_span_id: dict[str, dict[str, Any]] = {}
    child_rows_by_parent_span_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        span_id = row.get("span_id")
        if isinstance(span_id, str):
            rows_by_span_id[span_id] = row
        parent_span_id = row.get("parent_span_id")
        if isinstance(parent_span_id, str):
            child_rows_by_parent_span_id[parent_span_id].append(row)

    case_rows: list[dict[str, Any]] = []
    for case_payload in cases:
        case_rows.append(
            _build_case_row(
                case_payload=case_payload,
                failure_payload=None,
                rows_by_span_id=rows_by_span_id,
                child_rows_by_parent_span_id=child_rows_by_parent_span_id,
            )
        )

    for failure_payload in failures:
        case_rows.append(
            _build_case_row(
                case_payload=failure_payload,
                failure_payload=failure_payload,
                rows_by_span_id=rows_by_span_id,
                child_rows_by_parent_span_id=child_rows_by_parent_span_id,
            )
        )

    if status == SUMMARY_STATUS_SKIPPED:
        case_rows = [
            {
                **row,
                "duration_s": None,
                "token_metrics": {},
            }
            for row in case_rows
        ]

    completed_cases = len(cases)
    failure_count = len(failures)
    total_cases = completed_cases + failure_count
    success_rate = completed_cases / total_cases if total_cases else 0.0
    durations = [
        row["duration_s"]
        for row in case_rows
        if row.get("duration_s") is not None
    ]
    task_duration_avg = sum(durations) / len(durations) if durations else None
    task_duration_min = min(durations) if durations else None
    task_duration_max = max(durations) if durations else None
    failure_counts_by_category: dict[str, int] = {}
    for failure_payload in failures:
        category = classify_failure_category(failure_payload.get("error_message"))
        failure_counts_by_category[category] = (
            failure_counts_by_category.get(category, 0) + 1
        )

    return {
        "experiment_id": artifact_payload.get("experiment_id"),
        "trace_id": artifact_payload.get("trace_id"),
        "status": status,
        "reason": reason,
        "completed_cases": completed_cases,
        "failure_count": failure_count,
        "overall_case_success_rate": success_rate,
        "failure_counts_by_category": failure_counts_by_category,
        "avg_task_duration_s": task_duration_avg,
        "min_task_duration_s": task_duration_min,
        "max_task_duration_s": task_duration_max,
        "cases": case_rows,
    }


async def _query_trace_rows(
    *,
    read_token: str,
    trace_id: str,
) -> list[dict[str, Any]]:
    async with AsyncLogfireQueryClient(read_token=read_token) as client:
        result = await client.query_json_rows(_query_sql(trace_id), limit=_QUERY_LIMIT)
    rows = result.get("rows", [])
    return [row for row in rows if isinstance(row, dict)]


async def build_run_summary(
    *,
    result_dir: Path,
    read_token: str | None = None,
    artifact_paths: Sequence[Path] | None = None,
    artifact_payloads: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_read_token = read_token or _read_backend_env_var("LOGFIRE_READ_TOKEN")
    payloads = _resolve_artifact_payloads(
        result_dir=result_dir,
        artifact_paths=artifact_paths,
        artifact_payloads=artifact_payloads,
    )
    run_timestamp = _parse_run_timestamp(result_dir)

    if not payloads:
        return {
            "status": SUMMARY_STATUS_SKIPPED,
            "reason": "no_result_artifacts",
            "run_timestamp": run_timestamp,
            "experiments": [],
            "completed_cases": 0,
            "failure_count": 0,
            "overall_case_success_rate": 0.0,
            "failure_counts_by_category": {},
            "avg_task_duration_s": None,
            "min_task_duration_s": None,
            "max_task_duration_s": None,
        }

    if not resolved_read_token:
        experiments = [
            _build_local_experiment_summary(
                payload,
                status=SUMMARY_STATUS_SKIPPED,
                reason="missing_logfire_read_token",
            )
            for payload in payloads
        ]
        return _build_run_summary(
            run_timestamp=run_timestamp,
            experiments=experiments,
            status=SUMMARY_STATUS_SKIPPED,
            reason="missing_logfire_read_token",
        )

    experiments: list[dict[str, Any]] = []
    top_level_status: SummaryStatus = SUMMARY_STATUS_OK
    top_level_reason: str | None = None

    for payload in payloads:
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            top_level_status = SUMMARY_STATUS_PARTIAL
            top_level_reason = top_level_reason or "missing_trace_id"
            experiments.append(
                _build_local_experiment_summary(
                    payload,
                    status=SUMMARY_STATUS_PARTIAL,
                    reason="missing_trace_id",
                )
            )
            continue

        try:
            rows = await _query_trace_rows(
                read_token=resolved_read_token,
                trace_id=trace_id,
            )
        except Exception:
            top_level_status = SUMMARY_STATUS_PARTIAL
            top_level_reason = top_level_reason or "logfire_query_failed"
            experiments.append(
                _build_local_experiment_summary(
                    payload,
                    status=SUMMARY_STATUS_PARTIAL,
                    reason="logfire_query_failed",
                )
            )
            continue

        experiments.append(
            _build_local_experiment_summary(
                payload,
                status=SUMMARY_STATUS_OK,
                reason=None,
                rows=rows,
            )
        )

    summary = _build_run_summary(
        run_timestamp=run_timestamp,
        experiments=experiments,
        status=top_level_status,
        reason=top_level_reason,
    )
    return summary


def _resolve_artifact_payloads(
    *,
    result_dir: Path,
    artifact_paths: Sequence[Path] | None,
    artifact_payloads: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if artifact_payloads is not None:
        return [dict(payload) for payload in artifact_payloads]
    if artifact_paths is not None:
        resolved_paths = [Path(path) for path in artifact_paths]
        return [_load_json_file(path) for path in resolved_paths]
    return _load_artifact_payloads(result_dir)


def _build_run_summary(
    *,
    run_timestamp: str,
    experiments: Sequence[Mapping[str, Any]],
    status: SummaryStatus,
    reason: str | None,
) -> dict[str, Any]:
    completed_cases = sum(
        int(experiment.get("completed_cases", 0)) for experiment in experiments
    )
    failure_count = sum(
        int(experiment.get("failure_count", 0)) for experiment in experiments
    )
    total_cases = completed_cases + failure_count
    success_rate = completed_cases / total_cases if total_cases else 0.0

    failure_counts_by_category: dict[str, int] = {}
    durations: list[float] = []
    for experiment in experiments:
        for category, count in dict(
            experiment.get("failure_counts_by_category", {})
        ).items():
            failure_counts_by_category[category] = (
                failure_counts_by_category.get(category, 0) + int(count)
            )
        for case in experiment.get("cases", []):
            duration_s = _as_float(case.get("duration_s"))
            if duration_s is not None:
                durations.append(duration_s)

    avg_duration = sum(durations) / len(durations) if durations else None
    min_duration = min(durations) if durations else None
    max_duration = max(durations) if durations else None

    return {
        "status": status,
        "reason": reason,
        "run_timestamp": run_timestamp,
        "experiments": list(experiments),
        "completed_cases": completed_cases,
        "failure_count": failure_count,
        "overall_case_success_rate": success_rate,
        "failure_counts_by_category": failure_counts_by_category,
        "avg_task_duration_s": avg_duration,
        "min_task_duration_s": min_duration,
        "max_task_duration_s": max_duration,
    }


async def write_run_summary(
    *,
    result_dir: Path,
    read_token: str | None = None,
    artifact_paths: Sequence[Path] | None = None,
    artifact_payloads: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = await build_run_summary(
        result_dir=result_dir,
        read_token=read_token,
        artifact_paths=artifact_paths,
        artifact_payloads=artifact_payloads,
    )
    summary_path = result_dir / SUMMARY_FILENAME
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
