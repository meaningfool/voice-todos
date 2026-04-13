from evals.report import build_benchmark_report, render_terminal_report
from evals.resolution import build_entry_query_selector
from evals.storage import load_benchmark_by_id


class FakeBenchmarkQueryClient:
    def __init__(self, rows):
        self.rows = rows
        self.selectors = None

    def fetch_candidate_runs(self, selectors):
        self.selectors = selectors
        return self.rows


def _history_row(selector, *, run_id: str, started_at: str, failure_count: int = 0):
    return {
        "experiment_run_id": run_id,
        "start_timestamp": started_at,
        "suite": selector.suite,
        "dataset_sha": selector.dataset_sha,
        "evaluator_contract_sha": selector.evaluator_contract_sha,
        "model_name": selector.model_name,
        "prompt_sha": selector.prompt_sha,
        "config_fingerprint": selector.config_fingerprint,
        "repeat": selector.repeat,
        "task_retries": selector.task_retries,
        "headline_metric_value": 1.0,
        "completed_case_count": 9,
        "failure_count": failure_count,
        "average_case_duration_s": 1.2,
        "max_case_duration_s": 2.3,
        "cost_usd": 0.001,
        "failures": [
            {
                "case_id": "call-mom-memo-supplier",
                "category": "output_validation_failure",
                "summary": "Exceeded maximum retries (1) for output validation",
                "duration_s": 2.18,
            }
        ]
        if failure_count
        else [],
        "slowest_cases": [
            {"case_id": "call-mom-memo-supplier", "duration_s": 2.18},
            {"case_id": "continuous-speech", "duration_s": 1.64},
        ],
    }


def test_report_marks_missing_entries_instead_of_omitting_them():
    report = build_benchmark_report(
        benchmark_id="extraction_llm_matrix_v1",
        query_client=FakeBenchmarkQueryClient(rows=[]),
    )

    assert "deepinfra_qwen35_9b_default" in report.missing_entry_ids


def test_report_uses_latest_compatible_result_per_entry():
    benchmark = load_benchmark_by_id("extraction_llm_matrix_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    report = build_benchmark_report(
        benchmark_id="extraction_llm_matrix_v1",
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


def test_terminal_report_contains_failures_and_slowest_cases_sections():
    benchmark = load_benchmark_by_id("extraction_llm_matrix_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    selector = build_entry_query_selector(benchmark=benchmark, entry=entry)
    rendered = render_terminal_report(
        build_benchmark_report(
            benchmark_id="extraction_llm_matrix_v1",
            query_client=FakeBenchmarkQueryClient(
                rows=[
                    _history_row(
                        selector,
                        run_id="run-current",
                        started_at="2026-04-10T10:00:00+00:00",
                        failure_count=1,
                    )
                ]
            ),
        )
    )

    assert "Failures" in rendered
    assert "Slowest Cases" in rendered
