"""Benchmark report contract tests."""

import json

import pytest

from evals.report import build_benchmark_report, render_terminal_report, report_benchmark
from evals.resolution import build_entry_query_selector
from evals.storage import load_benchmark_by_id


class FakeBenchmarkQueryClient:
    def __init__(self, rows, case_rows=None):
        self.rows = rows
        self.case_rows = case_rows or []
        self.selectors = None
        self.trace_ids = None
        self.case_span_call_count = 0

    def fetch_candidate_runs(self, selectors):
        self.selectors = selectors
        return self.rows

    def fetch_case_spans(self, trace_ids):
        self.trace_ids = trace_ids
        self.case_span_call_count += 1
        return self.case_rows


def _history_row(
    selector,
    *,
    run_id: str,
    started_at: str,
    failure_count: int = 0,
    trace_id: str = "trace-current",
):
    return {
        "experiment_run_id": run_id,
        "start_timestamp": started_at,
        "trace_id": trace_id,
        "suite": selector.suite,
        "dataset_sha": selector.dataset_sha,
        "evaluator_contract_sha": selector.evaluator_contract_sha,
        "model_name": selector.model_name,
        "prompt_sha": selector.prompt_sha,
        "config_fingerprint": selector.config_fingerprint,
        "repeat": selector.repeat,
        "task_retries": selector.task_retries,
        "headline_metric_value": 1.0,
        "completed_case_count": 9 - failure_count,
        "failure_count": failure_count,
        "average_case_duration_s": 1.2,
        "max_case_duration_s": 2.3,
        "cost_usd": 0.001,
        "total_case_count": 9,
    }


def _case_row(
    *,
    trace_id: str,
    case_id: str,
    span_id: str | None = None,
    level: int = 9,
    task_duration: float | None = 2.18,
    assertion_value: bool | None = None,
    inputs: dict | None = None,
    expected_output: list[dict] | None = None,
    output: list[dict] | None = None,
    exception_message: str | None = None,
    exception_type: str | None = None,
    otel_status_message: str | None = None,
):
    row = {
        "trace_id": trace_id,
        "case_id": case_id,
        "span_id": span_id,
        "level": level,
        "task_duration": task_duration,
        "inputs": inputs or {},
        "expected_output": expected_output or [],
        "output": output,
        "exception_message": exception_message,
        "exception_type": exception_type,
        "otel_status_message": otel_status_message,
    }
    if assertion_value is not None:
        row["assertions"] = {
            "todo_count_match": {
                "name": "todo_count_match",
                "value": assertion_value,
                "reason": None,
                "source": {"name": "TodoCountEvaluator", "arguments": None},
            }
        }
    return row


def _agent_run_row(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    all_messages: list[dict],
):
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "span_name": "agent run",
        "level": 17,
        "all_messages": all_messages,
    }


def test_benchmark_report_marks_missing_entries_instead_of_omitting_them():
    report = build_benchmark_report(
        benchmark_id="todo_extraction_bench_v1",
        query_client=FakeBenchmarkQueryClient(rows=[]),
    )

    assert "deepinfra_qwen35_9b_default" in report.missing_entry_ids


def test_benchmark_report_uses_latest_compatible_result_per_entry():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report = build_benchmark_report(
        benchmark_id="todo_extraction_bench_v1",
        query_client=FakeBenchmarkQueryClient(
            rows=[
                _history_row(
                    selector,
                    run_id="run-older-compatible",
                    started_at="2026-04-09T10:00:00+00:00",
                ),
                _history_row(
                    selector,
                    run_id="run-newer-compatible",
                    started_at="2026-04-10T10:00:00+00:00",
                ),
            ]
        ),
    )

    entry_state = next(
        row for row in report.entries if row.entry_id == "gemini3_flash_default"
    )
    assert entry_state.status == "current"
    assert entry_state.selected_run_id == "run-newer-compatible"


def test_terminal_benchmark_report_includes_incorrect_and_incomplete_sections():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    rendered = render_terminal_report(
        build_benchmark_report(
            benchmark_id="todo_extraction_bench_v1",
            query_client=FakeBenchmarkQueryClient(
                rows=[
                    _history_row(
                        selector,
                        run_id="run-current",
                        started_at="2026-04-10T10:00:00+00:00",
                        failure_count=1,
                    )
                ],
                case_rows=[
                    _case_row(
                        trace_id="trace-current",
                        case_id="incorrect-case",
                        assertion_value=False,
                        inputs={"transcript": "Should I call David tomorrow?"},
                        expected_output=[],
                        output=[
                            {
                                "text": "Call David",
                                "priority": None,
                                "category": None,
                                "due_date": None,
                                "notification": None,
                                "assign_to": None,
                            }
                        ],
                        task_duration=1.64,
                    ),
                    _case_row(
                        trace_id="trace-current",
                        case_id="incomplete-case",
                        level=17,
                        task_duration=None,
                        inputs={"transcript": "Buy milk, buy bread, call Marc"},
                        expected_output=[
                            {
                                "text": "Do one grocery run for milk and bread",
                                "priority": None,
                                "category": None,
                                "due_date": None,
                                "notification": None,
                                "assign_to": None,
                            }
                        ],
                        exception_message="Exceeded maximum retries (1) for output validation",
                    ),
                    _case_row(
                        trace_id="trace-current",
                        case_id="passed-case",
                        assertion_value=True,
                        task_duration=1.64,
                    ),
                ],
            ),
        )
    )

    assert "Incorrect Cases" in rendered
    assert "Incomplete Cases" in rendered
    assert "Slowest Cases" in rendered


def test_benchmark_report_classifies_passed_incorrect_and_incomplete_cases():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report = build_benchmark_report(
        benchmark_id="todo_extraction_bench_v1",
        query_client=FakeBenchmarkQueryClient(
            rows=[
                _history_row(
                    selector,
                    run_id="run-current",
                    started_at="2026-04-10T10:00:00+00:00",
                    trace_id="trace-live",
                )
            ],
            case_rows=[
                _case_row(
                    trace_id="trace-live",
                    case_id="passed-case",
                    assertion_value=True,
                    task_duration=5.0,
                    inputs={"transcript": "Call Mom tonight."},
                    expected_output=[
                        {
                            "text": "Call Mom tonight",
                            "priority": None,
                            "category": None,
                            "due_date": None,
                            "notification": None,
                            "assign_to": None,
                        }
                    ],
                    output=[
                        {
                            "text": "Call Mom tonight",
                            "priority": None,
                            "category": None,
                            "due_date": None,
                            "notification": None,
                            "assign_to": None,
                        }
                    ],
                ),
                _case_row(
                    trace_id="trace-live",
                    case_id="incorrect-case",
                    assertion_value=False,
                    task_duration=1.0,
                    inputs={
                        "transcript": "I was wondering, should I call David tomorrow?"
                    },
                    expected_output=[],
                    output=[
                        {
                            "text": "Call David",
                            "priority": None,
                            "category": "Communication",
                            "due_date": "2026-03-25",
                            "notification": None,
                            "assign_to": None,
                        }
                    ],
                ),
                _case_row(
                    trace_id="trace-live",
                    case_id="incomplete-case",
                    span_id="case-incomplete",
                    level=17,
                    task_duration=None,
                    inputs={
                        "transcript": "Buy milk, buy bread, call Marc, and actually make that one grocery run."
                    },
                    expected_output=[
                        {
                            "text": "Do one grocery run for milk and bread",
                            "priority": None,
                            "category": None,
                            "due_date": None,
                            "notification": None,
                            "assign_to": None,
                        },
                        {
                            "text": "Call Marc",
                            "priority": None,
                            "category": None,
                            "due_date": None,
                            "notification": None,
                            "assign_to": None,
                        },
                    ],
                    exception_message="Exceeded maximum retries (1) for output validation",
                    exception_type="pydantic_ai.exceptions.UnexpectedModelBehavior",
                    otel_status_message="UnexpectedModelBehavior: Exceeded maximum retries (1) for output validation",
                ),
                _agent_run_row(
                    trace_id="trace-live",
                    span_id="agent-run-span",
                    parent_span_id="case-incomplete",
                    all_messages=[
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "type": "text",
                                    "content": "Validation feedback:\nPlease return text or include your response in a tool call.\n\nFix the errors and try again.",
                                }
                            ],
                        }
                    ],
                ),
            ],
        ),
    )

    entry_state = next(
        row for row in report.entries if row.entry_id == "gemini3_flash_default"
    )
    assert entry_state.total_case_count == 3
    assert entry_state.passed_case_count == 1
    assert entry_state.incorrect_case_count == 1
    assert entry_state.incomplete_case_count == 1
    assert entry_state.headline_metric_value == pytest.approx(1 / 3)
    assert entry_state.max_case_duration_s == 5.0
    assert entry_state.slowest_cases == [
        {"case_id": "passed-case", "duration_s": 5.0},
        {"case_id": "incorrect-case", "duration_s": 1.0},
    ]
    assert entry_state.incorrect_cases == [
        {
            "case_id": "incorrect-case",
            "inputs": {
                "transcript": "I was wondering, should I call David tomorrow?"
            },
            "expected_output": [],
            "actual_output": [
                {
                    "text": "Call David",
                    "priority": None,
                    "category": "Communication",
                    "due_date": "2026-03-25",
                    "notification": None,
                    "assign_to": None,
                }
            ],
        }
    ]
    assert entry_state.incomplete_cases == [
        {
            "case_id": "incomplete-case",
            "inputs": {
                "transcript": "Buy milk, buy bread, call Marc, and actually make that one grocery run."
            },
            "expected_output": [
                {
                    "text": "Do one grocery run for milk and bread",
                    "priority": None,
                    "category": None,
                    "due_date": None,
                    "notification": None,
                    "assign_to": None,
                },
                {
                    "text": "Call Marc",
                    "priority": None,
                    "category": None,
                    "due_date": None,
                    "notification": None,
                    "assign_to": None,
                },
            ],
            "summary": "Exceeded maximum retries (1) for output validation",
            "exception_type": "pydantic_ai.exceptions.UnexpectedModelBehavior",
            "validator_feedback": "Please return text or include your response in a tool call.",
            "actual_output": None,
        }
    ]


def test_report_benchmark_persists_json_report_file(tmp_path, monkeypatch):
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report_path = tmp_path / "todo_extraction_bench_v1.json"
    monkeypatch.setattr(
        "evals.report.benchmark_report_path",
        lambda benchmark_id: report_path,
        raising=False,
    )

    client = FakeBenchmarkQueryClient(
        rows=[
            _history_row(
                selector,
                run_id="run-current",
                started_at="2026-04-10T10:00:00+00:00",
                trace_id="trace-live",
            )
        ],
        case_rows=[
            _case_row(
                trace_id="trace-live",
                case_id="slow-case",
                task_duration=5.0,
            ),
            _case_row(
                trace_id="trace-live",
                case_id="failed-case",
                level=17,
                task_duration=None,
            ),
        ],
    )

    output = report_benchmark(
        benchmark_id="todo_extraction_bench_v1",
        json_output=True,
        query_client=client,
    )

    assert report_path.exists()
    assert report_path.read_text() == output
    assert json.loads(output)["benchmark_id"] == "todo_extraction_bench_v1"


def test_report_benchmark_reuses_persisted_file_when_state_unchanged(
    tmp_path, monkeypatch
):
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report_path = tmp_path / "todo_extraction_bench_v1.json"
    monkeypatch.setattr(
        "evals.report.benchmark_report_path",
        lambda benchmark_id: report_path,
        raising=False,
    )

    initial_client = FakeBenchmarkQueryClient(
        rows=[
            _history_row(
                selector,
                run_id="run-current",
                started_at="2026-04-10T10:00:00+00:00",
                trace_id="trace-live",
            )
        ],
        case_rows=[
            _case_row(
                trace_id="trace-live",
                case_id="slow-case",
                task_duration=5.0,
            ),
            _case_row(
                trace_id="trace-live",
                case_id="failed-case",
                level=17,
                task_duration=None,
            ),
        ],
    )
    initial_output = report_benchmark(
        benchmark_id="todo_extraction_bench_v1",
        json_output=True,
        query_client=initial_client,
    )

    reused_client = FakeBenchmarkQueryClient(
        rows=[
            _history_row(
                selector,
                run_id="run-current",
                started_at="2026-04-10T10:00:00+00:00",
                trace_id="trace-live",
            )
        ],
        case_rows=[],
    )
    reused_output = report_benchmark(
        benchmark_id="todo_extraction_bench_v1",
        json_output=True,
        query_client=reused_client,
    )

    assert reused_output == initial_output
    assert reused_client.case_span_call_count == 0
    assert report_path.read_text() == initial_output


def test_report_benchmark_refreshes_persisted_file_when_state_changes(
    tmp_path, monkeypatch
):
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report_path = tmp_path / "todo_extraction_bench_v1.json"
    monkeypatch.setattr(
        "evals.report.benchmark_report_path",
        lambda benchmark_id: report_path,
        raising=False,
    )

    report_benchmark(
        benchmark_id="todo_extraction_bench_v1",
        json_output=True,
        query_client=FakeBenchmarkQueryClient(
            rows=[
                _history_row(
                    selector,
                    run_id="run-old",
                    started_at="2026-04-10T10:00:00+00:00",
                    trace_id="trace-old",
                )
            ],
            case_rows=[
                _case_row(
                    trace_id="trace-old",
                    case_id="old-case",
                    task_duration=3.0,
                )
            ],
        ),
    )

    refreshed_client = FakeBenchmarkQueryClient(
        rows=[
            _history_row(
                selector,
                run_id="run-new",
                started_at="2026-04-11T10:00:00+00:00",
                trace_id="trace-new",
            )
        ],
        case_rows=[
            _case_row(
                trace_id="trace-new",
                case_id="new-case",
                task_duration=7.0,
            )
        ],
    )

    refreshed_output = report_benchmark(
        benchmark_id="todo_extraction_bench_v1",
        json_output=True,
        query_client=refreshed_client,
    )
    persisted = json.loads(report_path.read_text())
    refreshed_entry = next(
        row for row in persisted["entries"] if row["entry_id"] == "gemini3_flash_default"
    )

    assert refreshed_client.case_span_call_count == 1
    assert refreshed_entry["selected_run_id"] == "run-new"
    assert refreshed_entry["slowest_cases"] == [
        {"case_id": "new-case", "duration_s": 7.0}
    ]
    assert json.loads(refreshed_output) == persisted
