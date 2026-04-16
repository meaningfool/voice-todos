from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from evals.hosted_datasets import canonical_dataset_hash, export_hosted_dataset
from evals.logfire_query import LogfireBenchmarkQueryClient
from evals.models import BenchmarkEntryState, BenchmarkReport
from evals.resolution import build_entry_query_selector
from evals.storage import (
    benchmark_lock_path,
    benchmark_report_path,
    load_benchmark_by_id,
    load_benchmark_lock,
)


def build_benchmark_report(
    *,
    benchmark_id: str,
    query_client: object | None = None,
) -> BenchmarkReport:
    benchmark, lock_state, client, selected_rows_by_entry_id = _resolve_benchmark_state(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    return _build_benchmark_report_from_state(
        benchmark=benchmark,
        lock_state=lock_state,
        client=client,
        selected_rows_by_entry_id=selected_rows_by_entry_id,
    )


def ensure_benchmark_report(
    *,
    benchmark_id: str,
    query_client: object | None = None,
) -> tuple[BenchmarkReport, Path, bool]:
    benchmark, lock_state, client, selected_rows_by_entry_id = _resolve_benchmark_state(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    path = benchmark_report_path(benchmark_id)
    persisted = _load_persisted_report(path)
    if persisted is not None and _persisted_report_matches_state(
        report=persisted,
        benchmark=benchmark,
        lock_state=lock_state,
        selected_rows_by_entry_id=selected_rows_by_entry_id,
    ):
        return persisted, path, True

    report = _build_benchmark_report_from_state(
        benchmark=benchmark,
        lock_state=lock_state,
        client=client,
        selected_rows_by_entry_id=selected_rows_by_entry_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2))
    return report, path, False


def _build_benchmark_report_from_state(
    *,
    benchmark,
    lock_state,
    client: object,
    selected_rows_by_entry_id: dict[str, dict],
) -> BenchmarkReport:

    case_rows_by_trace_id = _fetch_case_rows_by_trace_id(
        client=client,
        trace_ids=[
            trace_id
            for trace_id in (
                row.get("trace_id") for row in selected_rows_by_entry_id.values()
            )
            if isinstance(trace_id, str) and trace_id
        ],
    )

    entries: list[BenchmarkEntryState] = []
    for entry in benchmark.entries:
        selected_row = selected_rows_by_entry_id.get(entry.id)
        if selected_row is None:
            entries.append(
                BenchmarkEntryState(
                    entry_id=entry.id,
                    label=entry.label,
                    status="missing",
                    total_case_count=0,
                    passed_case_count=0,
                    incorrect_case_count=0,
                    incomplete_case_count=0,
                    config=entry.config,
                )
            )
            continue

        trace_rows = case_rows_by_trace_id.get(selected_row.get("trace_id"), [])
        case_records = _build_case_records(
            trace_rows=trace_rows,
            headline_metric=benchmark.headline_metric,
        )
        total_case_count = _total_case_count(
            selected_row=selected_row,
            case_records=case_records,
        )
        completed_case_count = _completed_case_count(
            selected_row=selected_row,
            case_records=case_records,
        )
        passed_case_count = _passed_case_count(
            selected_row=selected_row,
            case_records=case_records,
            total_case_count=total_case_count,
            completed_case_count=completed_case_count,
        )
        incorrect_case_count = _incorrect_case_count(
            case_records=case_records,
            completed_case_count=completed_case_count,
            passed_case_count=passed_case_count,
        )
        incomplete_case_count = _incomplete_case_count(
            case_records=case_records,
            total_case_count=total_case_count,
            completed_case_count=completed_case_count,
        )
        entries.append(
            BenchmarkEntryState(
                entry_id=entry.id,
                label=entry.label,
                status="current",
                selected_run_id=selected_row.get("experiment_run_id"),
                selected_timestamp=selected_row.get("start_timestamp"),
                headline_metric_value=_pass_rate(
                    passed_case_count=passed_case_count,
                    total_case_count=total_case_count,
                ),
                total_case_count=total_case_count,
                passed_case_count=passed_case_count,
                incorrect_case_count=incorrect_case_count,
                incomplete_case_count=incomplete_case_count,
                completed_case_count=completed_case_count,
                failure_count=incomplete_case_count,
                average_case_duration_s=_float_or_none(
                    selected_row.get("average_case_duration_s")
                ),
                max_case_duration_s=_max_case_duration(case_records),
                cost_usd=_float_or_none(selected_row.get("cost_usd")),
                config=entry.config,
                failures=_build_incomplete_cases(case_records),
                incorrect_cases=_build_incorrect_cases(case_records),
                incomplete_cases=_build_incomplete_cases(case_records),
                slowest_cases=_build_slowest_cases(case_records),
            )
        )

    return BenchmarkReport(
        benchmark_id=benchmark.benchmark_id,
        hosted_dataset=benchmark.hosted_dataset,
        focus=benchmark.focus,
        headline_metric=benchmark.headline_metric,
        display_headline_metric="passed / total",
        active_lock_path=(
            str(lock_state.lock_path) if lock_state.active_lock_exists else None
        ),
        locked_dataset_hash=lock_state.locked_dataset_hash,
        current_hosted_dataset_hash=lock_state.current_hosted_dataset_hash,
        stale=lock_state.stale,
        entries=entries,
        missing_entry_ids=[
            entry.entry_id for entry in entries if entry.status == "missing"
        ],
    )


def _resolve_benchmark_state(
    *,
    benchmark_id: str,
    query_client: object | None = None,
):
    benchmark = load_benchmark_by_id(benchmark_id)
    lock_state = _safe_lock_state(benchmark)
    selectors = [
        build_entry_query_selector(benchmark=benchmark, entry=entry)
        for entry in benchmark.entries
    ]
    client = query_client or LogfireBenchmarkQueryClient()
    history_rows = client.fetch_candidate_runs(selectors)
    selected_rows_by_entry_id: dict[str, dict] = {}

    for entry, selector in zip(benchmark.entries, selectors, strict=False):
        matching_rows = [
            row for row in history_rows if _row_matches_selector(row, selector)
        ]
        selected_row = _latest_row(matching_rows)
        if selected_row is not None:
            selected_rows_by_entry_id[entry.id] = selected_row

    return benchmark, lock_state, client, selected_rows_by_entry_id


def render_terminal_report(report: BenchmarkReport) -> str:
    lines = [
        f"Benchmark: {report.benchmark_id}",
        f"Hosted dataset: {report.hosted_dataset}",
        f"Focus: {report.focus}",
        f"Headline metric: {report.headline_metric}",
        f"Displayed headline: {report.display_headline_metric}",
        f"Stale: {str(report.stale).lower()}",
        "",
        "Entries",
    ]
    for entry in report.entries:
        lines.append(
            f"{entry.label}: {entry.status}"
            + (
                f" ({entry.selected_run_id})"
                if entry.selected_run_id is not None
                else ""
            )
        )
        if entry.status == "current":
            lines.append(
                f"  passed={entry.passed_case_count} incorrect={entry.incorrect_case_count} incomplete={entry.incomplete_case_count}"
            )

    lines.extend(["", "Incorrect Cases"])
    for entry in report.entries:
        if not entry.incorrect_cases:
            continue
        lines.append(entry.label)
        for case in entry.incorrect_cases:
            lines.append(f"- {case.get('case_id')}")

    lines.extend(["", "Incomplete Cases"])
    for entry in report.entries:
        if not entry.incomplete_cases:
            continue
        lines.append(entry.label)
        for failure in entry.incomplete_cases:
            lines.append(f"- {failure.get('case_id')}: {failure.get('summary')}")

    lines.extend(["", "Slowest Cases"])
    for entry in report.entries:
        if not entry.slowest_cases:
            continue
        lines.append(entry.label)
        for case in entry.slowest_cases:
            lines.append(f"- {case.get('case_id')}: {case.get('duration_s')}s")

    return "\n".join(lines)


def report_benchmark(
    *,
    benchmark_id: str,
    json_output: bool = False,
    query_client: object | None = None,
) -> str:
    report, path, _ = ensure_benchmark_report(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    if json_output:
        return path.read_text()
    return render_terminal_report(report)


def _row_matches_selector(row: dict, selector) -> bool:
    return (
        row.get("suite") == selector.suite
        and row.get("dataset_sha") == selector.dataset_sha
        and row.get("evaluator_contract_sha") == selector.evaluator_contract_sha
        and row.get("model_name") == selector.model_name
        and row.get("prompt_sha") == selector.prompt_sha
        and row.get("config_fingerprint") == selector.config_fingerprint
        and _int_or_zero(row.get("repeat")) == selector.repeat
        and _int_or_zero(row.get("task_retries")) == selector.task_retries
    )


def _latest_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return max(rows, key=lambda row: _timestamp_key(row.get("start_timestamp")))


def _timestamp_key(value: str | None) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _int_or_zero(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_case_rows_by_trace_id(
    *,
    client: object,
    trace_ids: list[str],
) -> dict[str, list[dict]]:
    fetch_case_spans = getattr(client, "fetch_case_spans", None)
    if not callable(fetch_case_spans) or not trace_ids:
        return {}

    case_rows_by_trace_id: dict[str, list[dict]] = {}
    try:
        for row in fetch_case_spans(trace_ids):
            trace_id = row.get("trace_id")
            if not isinstance(trace_id, str) or not trace_id:
                continue
            case_rows_by_trace_id.setdefault(trace_id, []).append(row)
    except Exception:
        return {}
    return case_rows_by_trace_id


def _load_persisted_report(path: Path) -> BenchmarkReport | None:
    if not path.exists():
        return None
    try:
        return BenchmarkReport.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def _persisted_report_matches_state(
    *,
    report: BenchmarkReport,
    benchmark,
    lock_state,
    selected_rows_by_entry_id: dict[str, dict],
) -> bool:
    if report.benchmark_id != benchmark.benchmark_id:
        return False
    if report.hosted_dataset != benchmark.hosted_dataset:
        return False
    if report.focus != benchmark.focus or report.headline_metric != benchmark.headline_metric:
        return False
    if report.display_headline_metric != "passed / total":
        return False

    active_lock_path = (
        str(lock_state.lock_path) if lock_state.active_lock_exists else None
    )
    if report.active_lock_path != active_lock_path:
        return False
    if report.locked_dataset_hash != lock_state.locked_dataset_hash:
        return False
    if report.current_hosted_dataset_hash != lock_state.current_hosted_dataset_hash:
        return False
    if report.stale != lock_state.stale:
        return False

    entry_state_by_id = {entry.entry_id: entry for entry in report.entries}
    if set(entry_state_by_id) != {entry.id for entry in benchmark.entries}:
        return False

    for benchmark_entry in benchmark.entries:
        entry_state = entry_state_by_id.get(benchmark_entry.id)
        if entry_state is None:
            return False
        if entry_state.label != benchmark_entry.label:
            return False
        if entry_state.config != benchmark_entry.config:
            return False

        selected_row = selected_rows_by_entry_id.get(benchmark_entry.id)
        if selected_row is None:
            if entry_state.status != "missing" or entry_state.selected_run_id is not None:
                return False
            continue

        if entry_state.status != "current":
            return False
        if entry_state.selected_run_id != selected_row.get("experiment_run_id"):
            return False

    return True


def _completed_case_count(*, selected_row: dict, case_records: list[dict]) -> int:
    if case_records:
        return sum(1 for row in case_records if row.get("status") in {"passed", "incorrect"})

    completed_case_count = _int_or_zero(selected_row.get("completed_case_count"))
    if completed_case_count:
        return completed_case_count
    return _int_or_zero(selected_row.get("total_case_count"))


def _row_completed(row: dict) -> bool:
    return _float_or_none(row.get("task_duration")) is not None and not _row_failed(row)


def _row_failed(row: dict) -> bool:
    return _int_or_zero(row.get("level")) >= 17 or _float_or_none(
        row.get("task_duration")
    ) is None


def _max_case_duration(case_records: list[dict]) -> float | None:
    durations = [
        duration
        for duration in (
            _float_or_none(row.get("duration_s")) for row in case_records if row.get("status") in {"passed", "incorrect"}
        )
        if duration is not None
    ]
    if not durations:
        return None
    return max(durations)


def _build_slowest_cases(case_records: list[dict]) -> list[dict]:
    completed_rows = [
        {"case_id": row["case_id"], "duration_s": row["duration_s"]}
        for row in case_records
        if row.get("status") in {"passed", "incorrect"}
        and _float_or_none(row.get("duration_s")) is not None
    ]
    completed_rows.sort(key=lambda row: row["duration_s"], reverse=True)
    return completed_rows[:3]


def _total_case_count(*, selected_row: dict, case_records: list[dict]) -> int:
    if case_records:
        return len(case_records)
    return _int_or_zero(selected_row.get("total_case_count"))


def _passed_case_count(
    *,
    selected_row: dict,
    case_records: list[dict],
    total_case_count: int,
    completed_case_count: int,
) -> int:
    if case_records:
        return sum(1 for row in case_records if row.get("status") == "passed")

    headline_metric_value = _float_or_none(selected_row.get("headline_metric_value"))
    if headline_metric_value is None or not total_case_count:
        return 0
    return min(
        completed_case_count,
        max(0, int(round(headline_metric_value * total_case_count))),
    )


def _incorrect_case_count(
    *,
    case_records: list[dict],
    completed_case_count: int,
    passed_case_count: int,
) -> int:
    if case_records:
        return sum(1 for row in case_records if row.get("status") == "incorrect")
    return max(0, completed_case_count - passed_case_count)


def _incomplete_case_count(
    *,
    case_records: list[dict],
    total_case_count: int,
    completed_case_count: int,
) -> int:
    if case_records:
        return sum(1 for row in case_records if row.get("status") == "incomplete")
    return max(0, total_case_count - completed_case_count)


def _pass_rate(*, passed_case_count: int, total_case_count: int) -> float | None:
    if total_case_count <= 0:
        return None
    return passed_case_count / total_case_count


def _build_case_records(*, trace_rows: list[dict], headline_metric: str) -> list[dict]:
    case_rows = _case_span_rows(trace_rows)
    execute_rows_by_case_span_id: dict[str, dict] = {}
    agent_rows_by_execute_span_id: dict[str, list[dict]] = {}

    for row in trace_rows:
        span_name = row.get("span_name")
        if span_name == "execute {task}":
            parent_span_id = row.get("parent_span_id")
            if isinstance(parent_span_id, str) and parent_span_id:
                execute_rows_by_case_span_id[parent_span_id] = row
        elif span_name == "agent run":
            parent_span_id = row.get("parent_span_id")
            if isinstance(parent_span_id, str) and parent_span_id:
                agent_rows_by_execute_span_id.setdefault(parent_span_id, []).append(row)

    case_records: list[dict] = []
    for row in case_rows:
        case_record = _base_case_record(row)
        if not case_record:
            continue

        if _row_failed(row):
            case_record["status"] = "incomplete"
            case_record["summary"] = _incomplete_summary(row)
            case_record["exception_type"] = row.get("exception_type")
            case_record["actual_output"] = None
            case_record["validator_feedback"] = _validator_feedback_for_case(
                row=row,
                execute_rows_by_case_span_id=execute_rows_by_case_span_id,
                agent_rows_by_execute_span_id=agent_rows_by_execute_span_id,
            )
        elif _case_assertion_value(row, headline_metric) is False:
            case_record["status"] = "incorrect"
            case_record["actual_output"] = row.get("output")
        else:
            case_record["status"] = "passed"
            case_record["actual_output"] = row.get("output")

        case_records.append(case_record)

    return case_records


def _base_case_record(row: dict) -> dict | None:
    case_id = row.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        return None
    return {
        "case_id": case_id,
        "inputs": row.get("inputs") or {},
        "expected_output": row.get("expected_output") or [],
        "duration_s": _float_or_none(row.get("task_duration")),
    }


def _case_span_rows(trace_rows: list[dict]) -> list[dict]:
    return [row for row in trace_rows if isinstance(row.get("case_id"), str) and row.get("case_id")]


def _case_assertion_value(row: dict, headline_metric: str) -> bool | None:
    assertions = row.get("assertions")
    if not isinstance(assertions, dict):
        return None
    metric_assertion = assertions.get(headline_metric)
    if not isinstance(metric_assertion, dict):
        return None
    value = metric_assertion.get("value")
    if isinstance(value, bool):
        return value
    return None


def _build_incorrect_cases(case_records: list[dict]) -> list[dict]:
    return [
        {
            "case_id": row["case_id"],
            "inputs": row.get("inputs") or {},
            "expected_output": row.get("expected_output") or [],
            "actual_output": row.get("actual_output"),
        }
        for row in case_records
        if row.get("status") == "incorrect"
    ]


def _build_incomplete_cases(case_records: list[dict]) -> list[dict]:
    return [
        {
            "case_id": row["case_id"],
            "inputs": row.get("inputs") or {},
            "expected_output": row.get("expected_output") or [],
            "summary": row.get("summary"),
            "exception_type": row.get("exception_type"),
            "validator_feedback": row.get("validator_feedback"),
            "actual_output": row.get("actual_output"),
        }
        for row in case_records
        if row.get("status") == "incomplete"
    ]


def _incomplete_summary(row: dict) -> str:
    for key in ("exception_message", "otel_status_message", "message"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return "Incomplete case"


def _validator_feedback_for_case(
    *,
    row: dict,
    execute_rows_by_case_span_id: dict[str, dict],
    agent_rows_by_execute_span_id: dict[str, list[dict]],
) -> str | None:
    case_span_id = row.get("span_id")
    if not isinstance(case_span_id, str) or not case_span_id:
        return None
    execute_row = execute_rows_by_case_span_id.get(case_span_id)
    agent_rows = []
    if execute_row:
        execute_span_id = execute_row.get("span_id")
        if isinstance(execute_span_id, str) and execute_span_id:
            agent_rows.extend(agent_rows_by_execute_span_id.get(execute_span_id, []))
    agent_rows.extend(agent_rows_by_execute_span_id.get(case_span_id, []))
    if not agent_rows:
        return None

    latest_agent_row = _latest_row(agent_rows)
    all_messages = latest_agent_row.get("all_messages") if latest_agent_row else None
    return _extract_validator_feedback(all_messages)


def _extract_validator_feedback(all_messages) -> str | None:
    if not isinstance(all_messages, list):
        return None
    for message in reversed(all_messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            content = part.get("content")
            if not isinstance(content, str):
                continue
            if content.startswith("Validation feedback:"):
                remainder = content.split("Validation feedback:", 1)[1].strip()
                first_paragraph = remainder.split("\n\n", 1)[0].strip()
                return first_paragraph or remainder or None
    return None


def _safe_lock_state(benchmark):
    try:
        lock = load_benchmark_lock(benchmark.benchmark_id)
        exported = export_hosted_dataset(benchmark.hosted_dataset)
        current_hash = canonical_dataset_hash(exported)
        from evals.run import BenchmarkLockState

        return BenchmarkLockState(
            active_lock_exists=lock is not None,
            stale=(
                lock is not None and current_hash != lock.benchmark_lock.dataset_hash
            ),
            lock_path=benchmark_lock_path(benchmark.benchmark_id),
            locked_dataset_hash=(
                lock.benchmark_lock.dataset_hash if lock is not None else None
            ),
            current_hosted_dataset_hash=current_hash,
            exported_payload=exported,
        )
    except Exception:
        from evals.run import BenchmarkLockState

        lock = load_benchmark_lock(benchmark.benchmark_id)
        return BenchmarkLockState(
            active_lock_exists=lock is not None,
            stale=False,
            lock_path=benchmark_lock_path(benchmark.benchmark_id),
            locked_dataset_hash=(
                lock.benchmark_lock.dataset_hash if lock is not None else None
            ),
        )
