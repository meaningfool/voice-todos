import pytest
from evals.report import build_benchmark_report

from app.live_eval_env import benchmark_report_skip_reason

_SKIP_REASON = benchmark_report_skip_reason()

pytestmark = pytest.mark.skipif(
    _SKIP_REASON is not None,
    reason=_SKIP_REASON or "requires dedicated Logfire dev project",
)


def test_build_benchmark_report_queries_live_logfire():
    report = build_benchmark_report(benchmark_id="extraction_llm_matrix_v1")

    assert report.benchmark_id == "extraction_llm_matrix_v1"
    assert report.entries
