from __future__ import annotations

from datetime import datetime

from evals.logfire_query import LogfireBenchmarkQueryClient
from evals.models import BenchmarkEntryState, BenchmarkReport
from evals.resolution import build_entry_query_selector
from evals.storage import load_benchmark_by_id


def build_benchmark_report(
    *,
    benchmark_id: str,
    query_client: object | None = None,
) -> BenchmarkReport:
    benchmark = load_benchmark_by_id(benchmark_id)
    selectors = [
        build_entry_query_selector(benchmark=benchmark, entry=entry)
        for entry in benchmark.entries
    ]
    client = query_client or LogfireBenchmarkQueryClient()
    history_rows = client.fetch_candidate_runs(selectors)

    entries: list[BenchmarkEntryState] = []
    for entry, selector in zip(benchmark.entries, selectors, strict=False):
        matching_rows = [
            row for row in history_rows if _row_matches_selector(row, selector)
        ]
        selected_row = _latest_row(matching_rows)
        if selected_row is None:
            entries.append(
                BenchmarkEntryState(
                    entry_id=entry.id,
                    label=entry.label,
                    status="missing",
                    config=entry.config,
                )
            )
            continue
        entries.append(
            BenchmarkEntryState(
                entry_id=entry.id,
                label=entry.label,
                status="current",
                selected_run_id=selected_row.get("experiment_run_id"),
                selected_timestamp=selected_row.get("start_timestamp"),
                headline_metric_value=_float_or_none(
                    selected_row.get("headline_metric_value")
                ),
                completed_case_count=_int_or_zero(
                    selected_row.get("completed_case_count")
                ),
                failure_count=_int_or_zero(selected_row.get("failure_count")),
                average_case_duration_s=_float_or_none(
                    selected_row.get("average_case_duration_s")
                ),
                max_case_duration_s=_float_or_none(
                    selected_row.get("max_case_duration_s")
                ),
                cost_usd=_float_or_none(selected_row.get("cost_usd")),
                config=entry.config,
                failures=_list_or_empty(selected_row.get("failures")),
                slowest_cases=_list_or_empty(selected_row.get("slowest_cases")),
            )
        )

    return BenchmarkReport(
        benchmark_id=benchmark.benchmark_id,
        focus=benchmark.focus,
        headline_metric=benchmark.headline_metric,
        entries=entries,
        missing_entry_ids=[
            entry.entry_id for entry in entries if entry.status == "missing"
        ],
    )


def render_terminal_report(report: BenchmarkReport) -> str:
    lines = [
        f"Benchmark: {report.benchmark_id}",
        f"Focus: {report.focus}",
        f"Headline metric: {report.headline_metric}",
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

    lines.extend(["", "Failures"])
    for entry in report.entries:
        if not entry.failures:
            continue
        lines.append(entry.label)
        for failure in entry.failures:
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
    report = build_benchmark_report(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    if json_output:
        return report.model_dump_json(indent=2)
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


def _list_or_empty(value) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
