from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from logfire.query_client import AsyncLogfireQueryClient

from app.logfire_setup import _read_backend_env_var
from evals.common.failure_classification import classify_failure_category

SUMMARY_FILENAME = "summary.json"
ENRICHMENT_STATUS_OK = "ok"
ENRICHMENT_STATUS_PARTIAL = "partial"
ENRICHMENT_STATUS_SKIPPED = "skipped"
EnrichmentStatus = Literal["ok", "partial", "skipped"]
_INVALID_JSON = object()

_QUERY_LIMIT = 10_000
_TOKEN_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "input_tokens": (
        "input_tokens",
        "prompt_tokens",
        "gen_ai.usage.input_tokens",
    ),
    "output_tokens": (
        "output_tokens",
        "completion_tokens",
        "gen_ai.usage.output_tokens",
    ),
    "thoughts_tokens": (
        "thoughts_tokens",
        "gen_ai.usage.details.thoughts_tokens",
    ),
    "cost_usd": (
        "cost_usd",
        "cost",
        "total_cost",
        "operation.cost",
    ),
    "total_tokens": ("total_tokens",),
    "requests": ("requests",),
}


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


def _load_json_file(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_json_file_safely(path: Path) -> Any:
    try:
        return _load_json_file(path)
    except (OSError, json.JSONDecodeError):
        return _INVALID_JSON


def _atomic_write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            json.dump(payload, temp_file, indent=2, sort_keys=True)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _load_artifact_paths(result_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in result_dir.glob("*.json")
        if path.is_file() and path.name != SUMMARY_FILENAME
    )


def _artifact_validation_reason(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return "invalid_experiment_artifact"
    if not isinstance(payload.get("experiment_id"), str):
        return "invalid_experiment_artifact"
    if not isinstance(payload.get("cases"), list):
        return "invalid_experiment_artifact"
    if not isinstance(payload.get("failures"), list):
        return "invalid_experiment_artifact"
    return None


def _is_experiment_artifact_payload(payload: Mapping[str, Any]) -> bool:
    return (
        _artifact_validation_reason(payload) is None
        and isinstance(payload.get("trace_id"), str)
    )


def _merge_artifact_payloads(
    *,
    disk_payload: Any,
    override_payload: Mapping[str, Any] | None,
) -> Any:
    if override_payload is None:
        return disk_payload
    if not isinstance(override_payload, Mapping):
        return disk_payload
    if not isinstance(disk_payload, Mapping):
        return dict(override_payload)
    return {
        **dict(override_payload),
        **dict(disk_payload),
    }


def _build_case_row(
    *,
    case_payload: Mapping[str, Any],
    failure_payload: Mapping[str, Any] | None,
    rows_by_span_id: dict[str, dict[str, Any]],
    child_rows_by_parent_span_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    span_id = case_payload.get("span_id")
    matching_row = rows_by_span_id.get(span_id) if isinstance(span_id, str) else None
    candidate_rows: list[dict[str, Any]] = []
    if matching_row is not None:
        candidate_rows.append(matching_row)
        candidate_rows.extend(
            _collect_descendant_rows(matching_row, child_rows_by_parent_span_id)
        )

    duration_row = matching_row or (candidate_rows[0] if candidate_rows else None)
    duration_s = _first_numeric([duration_row, *candidate_rows], "duration")
    token_metrics = _collect_token_metrics(candidate_rows)
    exception_summary = _first_non_empty(
        _extract_text_value(matching_row, "exception_message"),
        _extract_text_value(matching_row, "message"),
        (failure_payload or {}).get("error_message"),
    )
    failure_category = (
        classify_failure_category(failure_payload.get("error_message"))
        if failure_payload is not None
        else None
    )

    return {
        **case_payload,
        "status": "failure" if failure_payload is not None else "success",
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
    collected: dict[str, float] = defaultdict(float)
    for row in rows:
        row_values = _flatten_row_values(row)
        for canonical_name, aliases in _TOKEN_METRIC_ALIASES.items():
            value = _first_numeric_from_flattened(row_values, aliases)
            if value is not None:
                collected[canonical_name] += value
    return {
        key: _normalize_number(value)
        for key, value in sorted(collected.items())
    }


def _flatten_row_values(row: Mapping[str, Any]) -> dict[str, Any]:
    sources: dict[str, Any] = dict(row)
    sources.pop("attributes", None)
    sources.update(_extract_attributes(row))

    flattened: dict[str, Any] = {}
    _flatten_mapping(sources, prefix="", flattened=flattened)
    return flattened


def _flatten_mapping(
    mapping: Mapping[str, Any],
    *,
    prefix: str,
    flattened: dict[str, Any],
) -> None:
    for key, value in mapping.items():
        key_path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            _flatten_mapping(value, prefix=key_path, flattened=flattened)
        else:
            flattened[key_path] = value


def _first_numeric_from_flattened(
    row_values: Mapping[str, Any],
    aliases: Sequence[str],
) -> float | None:
    for alias in aliases:
        value = _as_float(row_values.get(alias))
        if value is not None:
            return value
    return None


def _normalize_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


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


def _rows_by_span(
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows_by_span_id: dict[str, dict[str, Any]] = {}
    child_rows_by_parent_span_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        span_id = row.get("span_id")
        if isinstance(span_id, str):
            rows_by_span_id[span_id] = row
        parent_span_id = row.get("parent_span_id")
        if isinstance(parent_span_id, str):
            child_rows_by_parent_span_id[parent_span_id].append(row)
    return rows_by_span_id, child_rows_by_parent_span_id


def _blank_enrichment_row(
    case_payload: Mapping[str, Any],
    *,
    failure_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    existing_status = case_payload.get("status")
    if existing_status not in {"success", "failure"}:
        existing_status = "failure" if failure_payload is not None else "success"

    existing_token_metrics = case_payload.get("token_metrics")
    if not isinstance(existing_token_metrics, Mapping):
        existing_token_metrics = {}

    return {
        **case_payload,
        "status": existing_status,
        "duration_s": case_payload.get("duration_s"),
        "failure_category": (
            case_payload.get("failure_category")
            if case_payload.get("failure_category") is not None
            else (
                classify_failure_category(failure_payload.get("error_message"))
                if failure_payload is not None
                else None
            )
        ),
        "exception_summary": (
            case_payload.get("exception_summary")
            if case_payload.get("exception_summary") is not None
            else (
                failure_payload.get("error_message")
                if failure_payload is not None
                else None
            )
        ),
        "token_metrics": dict(existing_token_metrics),
    }


def _duration_stats(
    *,
    cases: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, float | None]:
    durations = [
        duration_s
        for payload in [*cases, *failures]
        if (duration_s := _as_float(payload.get("duration_s"))) is not None
    ]
    return {
        "avg_task_duration_s": (sum(durations) / len(durations)) if durations else None,
        "min_task_duration_s": min(durations) if durations else None,
        "max_task_duration_s": max(durations) if durations else None,
    }


def _failure_counts_by_category(
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for failure in failures:
        category = failure.get("failure_category")
        if not isinstance(category, str) or not category:
            category = classify_failure_category(failure.get("error_message"))
        counts[category] = counts.get(category, 0) + 1
    return counts


def _build_enriched_artifact(
    artifact_payload: Mapping[str, Any],
    *,
    status: EnrichmentStatus,
    reason: str | None,
    rows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = list(artifact_payload.get("cases", []) or [])
    failures = list(artifact_payload.get("failures", []) or [])
    rows_by_span_id, child_rows_by_parent_span_id = _rows_by_span(list(rows or []))

    if rows:
        enriched_cases = [
            _build_case_row(
                case_payload=case_payload,
                failure_payload=None,
                rows_by_span_id=rows_by_span_id,
                child_rows_by_parent_span_id=child_rows_by_parent_span_id,
            )
            for case_payload in cases
        ]
        enriched_failures = [
            _build_case_row(
                case_payload=failure_payload,
                failure_payload=failure_payload,
                rows_by_span_id=rows_by_span_id,
                child_rows_by_parent_span_id=child_rows_by_parent_span_id,
            )
            for failure_payload in failures
        ]
    else:
        enriched_cases = [
            _blank_enrichment_row(case_payload, failure_payload=None)
            for case_payload in cases
        ]
        enriched_failures = [
            _blank_enrichment_row(failure_payload, failure_payload=failure_payload)
            for failure_payload in failures
        ]

    return {
        **artifact_payload,
        "enrichment_status": status,
        "enrichment_reason": reason,
        "failure_counts_by_category": _failure_counts_by_category(enriched_failures),
        **_duration_stats(cases=enriched_cases, failures=enriched_failures),
        "cases": enriched_cases,
        "failures": enriched_failures,
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


async def enrich_experiment_artifact(
    artifact_path: Path,
    *,
    read_token: str | None = None,
    artifact_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    disk_payload = _load_json_file_safely(artifact_path)
    payload = _merge_artifact_payloads(
        disk_payload=disk_payload,
        override_payload=artifact_payload,
    )
    validation_reason = _artifact_validation_reason(payload)
    if validation_reason is not None:
        return {
            "artifact_path": artifact_path,
            "enrichment_status": ENRICHMENT_STATUS_SKIPPED,
            "enrichment_reason": validation_reason,
        }

    resolved_read_token = read_token or _read_backend_env_var("LOGFIRE_READ_TOKEN")
    if not resolved_read_token:
        enriched_payload = _build_enriched_artifact(
            payload,
            status=ENRICHMENT_STATUS_SKIPPED,
            reason="missing_logfire_read_token",
        )
        _atomic_write_json_file(artifact_path, enriched_payload)
        return {
            "artifact_path": artifact_path,
            "enrichment_status": ENRICHMENT_STATUS_SKIPPED,
            "enrichment_reason": "missing_logfire_read_token",
        }

    trace_id = payload.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        enriched_payload = _build_enriched_artifact(
            payload,
            status=ENRICHMENT_STATUS_PARTIAL,
            reason="missing_trace_id",
        )
        _atomic_write_json_file(artifact_path, enriched_payload)
        return {
            "artifact_path": artifact_path,
            "enrichment_status": ENRICHMENT_STATUS_PARTIAL,
            "enrichment_reason": "missing_trace_id",
        }

    try:
        rows = await _query_trace_rows(
            read_token=resolved_read_token,
            trace_id=trace_id,
        )
    except Exception:
        enriched_payload = _build_enriched_artifact(
            payload,
            status=ENRICHMENT_STATUS_PARTIAL,
            reason="logfire_query_failed",
        )
        _atomic_write_json_file(artifact_path, enriched_payload)
        return {
            "artifact_path": artifact_path,
            "enrichment_status": ENRICHMENT_STATUS_PARTIAL,
            "enrichment_reason": "logfire_query_failed",
        }

    if not rows:
        enriched_payload = _build_enriched_artifact(
            payload,
            status=ENRICHMENT_STATUS_PARTIAL,
            reason="logfire_query_returned_no_rows",
        )
        _atomic_write_json_file(artifact_path, enriched_payload)
        return {
            "artifact_path": artifact_path,
            "enrichment_status": ENRICHMENT_STATUS_PARTIAL,
            "enrichment_reason": "logfire_query_returned_no_rows",
        }

    enriched_payload = _build_enriched_artifact(
        payload,
        status=ENRICHMENT_STATUS_OK,
        reason=None,
        rows=rows,
    )
    _atomic_write_json_file(artifact_path, enriched_payload)
    return {
        "artifact_path": artifact_path,
        "enrichment_status": ENRICHMENT_STATUS_OK,
        "enrichment_reason": None,
    }


def _resolve_artifact_inputs(
    *,
    result_dir: Path,
    artifact_paths: Sequence[Path] | None,
    artifact_payloads: Sequence[Mapping[str, Any]] | None,
) -> list[tuple[Path, Mapping[str, Any] | None]]:
    if artifact_payloads is not None and artifact_paths is None:
        raise ValueError("artifact_payloads requires artifact_paths")

    if artifact_paths is None:
        return [(path, None) for path in _load_artifact_paths(result_dir)]

    resolved_paths = [Path(path) for path in artifact_paths]
    if artifact_payloads is None:
        return [(path, None) for path in resolved_paths]

    if len(resolved_paths) != len(artifact_payloads):
        raise ValueError(
            "artifact_paths and artifact_payloads must have the same length"
        )

    return list(zip(resolved_paths, artifact_payloads, strict=True))


async def write_run_summary(
    *,
    result_dir: Path,
    read_token: str | None = None,
    artifact_paths: Sequence[Path] | None = None,
    artifact_payloads: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    resolved_inputs = _resolve_artifact_inputs(
        result_dir=result_dir,
        artifact_paths=artifact_paths,
        artifact_payloads=artifact_payloads,
    )

    results: list[dict[str, Any]] = []
    for artifact_path, artifact_payload in resolved_inputs:
        results.append(
            await enrich_experiment_artifact(
                artifact_path,
                read_token=read_token,
                artifact_payload=artifact_payload,
            )
        )
    return results
