import subprocess
import sys
from pathlib import Path

import pytest

from app.live_eval_env import benchmark_run_skip_reason

_TRACKED_SMOKE_SKIP_REASON = benchmark_run_skip_reason()


def test_cli_bootstrap_list_works_without_live_providers():
    result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "list",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "extraction_llm_matrix_v1" in result.stdout


@pytest.mark.skipif(
    _TRACKED_SMOKE_SKIP_REASON is not None,
    reason=_TRACKED_SMOKE_SKIP_REASON or "requires dedicated Logfire dev project",
)
def test_tracked_benchmark_run_then_report_state():
    tracked_run_result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "run",
            "extraction_llm_matrix_v1",
            "--dataset-path",
            "tests/fixtures/evals/todo_extraction_smoke.json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert tracked_run_result.returncode == 0

    report_result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "report",
            "extraction_llm_matrix_v1",
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert report_result.returncode == 0
    assert '"benchmark_id": "extraction_llm_matrix_v1"' in report_result.stdout
    assert '"entries"' in report_result.stdout


def test_legacy_benchmark_entrypoint_is_a_shim_or_intentional_deprecation():
    result = subprocess.run(
        [sys.executable, "evals/benchmarking/run.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in {0, 1}
    assert "benchmark" in (result.stdout + result.stderr).lower()
