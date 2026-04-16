import json
from pathlib import Path
from types import SimpleNamespace

from evals.storage import REPORTS_DIR


def test_benchmark_html_report_path_uses_reports_dir():
    from evals.storage import benchmark_html_report_path

    path = benchmark_html_report_path("todo_extraction_bench_v1")

    assert path == REPORTS_DIR / "todo_extraction_bench_v1.html"


def test_ensure_benchmark_report_html_writes_bootstrapped_html(tmp_path, monkeypatch):
    from evals.report_html import ensure_benchmark_report_html

    json_report_path = tmp_path / "todo_extraction_bench_v1.json"
    html_report_path = tmp_path / "todo_extraction_bench_v1.html"
    report_payload = {
        "benchmark_id": "todo_extraction_bench_v1",
        "headline_metric": "todo_count_match",
        "entries": [
            {
                "entry_id": "gemini3_flash_default",
                "label": "Gemini 3 Flash / default",
                "status": "current",
                "headline_metric_value": 1.0,
                "failures": [],
                "slowest_cases": [],
            }
        ],
    }
    json_report_path.write_text(json.dumps(report_payload, indent=2))

    monkeypatch.setattr(
        "evals.report_html.ensure_benchmark_report",
        lambda **kwargs: (
            SimpleNamespace(benchmark_id="todo_extraction_bench_v1"),
            json_report_path,
            True,
        ),
    )
    monkeypatch.setattr(
        "evals.report_html.benchmark_html_report_path",
        lambda benchmark_id: html_report_path,
    )
    monkeypatch.setattr(
        "evals.report_html._load_viewer_shell_html",
        lambda: (
            "<html><body><div id='root'></div>"
            "<script id='benchmark-report-bootstrap' type='application/json'>"
            "__BENCHMARK_REPORT_BOOTSTRAP__"
            "</script></body></html>"
        ),
    )

    path = ensure_benchmark_report_html("todo_extraction_bench_v1")
    html = path.read_text()
    bootstrap = html.split("benchmark-report-bootstrap", 1)[1]

    assert path == html_report_path
    assert path.exists()
    assert "todo_extraction_bench_v1.json" in html
    assert "Gemini 3 Flash / default" in html
    assert "__BENCHMARK_REPORT_BOOTSTRAP__" not in html
    assert "application/json" in bootstrap
