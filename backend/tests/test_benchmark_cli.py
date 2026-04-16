"""Benchmark CLI contract tests."""

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from evals.cli import main
from evals.run import BenchmarkStaleError


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_list_command_prints_known_ids(capsys):
    exit_code = main(["benchmark", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "todo_extraction_bench_v1" in captured.out
    assert "todo_replay_bench_v1" in captured.out


def test_benchmark_list_script_entrypoint_prints_known_ids():
    result = subprocess.run(
        [sys.executable, "../evals/cli.py", "benchmark", "list"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "todo_extraction_bench_v1" in result.stdout
    assert "todo_replay_bench_v1" in result.stdout


def test_benchmark_show_prints_entry_labels_and_config(capsys):
    exit_code = main(["benchmark", "show", "todo_extraction_bench_v1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Gemini 3 Flash / default" in captured.out
    assert "prompt_version" in captured.out


def test_benchmark_run_defaults_to_missing_entries(monkeypatch):
    planned = []
    monkeypatch.setattr(
        "evals.cli.run_benchmark",
        lambda **kwargs: planned.append(kwargs)
        or SimpleNamespace(executed_entry_ids=["mistral_small_4_default"]),
    )

    main(["benchmark", "run", "todo_extraction_bench_v1"])

    assert planned[0]["all_entries"] is False


def test_benchmark_run_passes_stale_control_flags(monkeypatch):
    planned = []
    monkeypatch.setattr(
        "evals.cli.run_benchmark",
        lambda **kwargs: planned.append(kwargs)
        or SimpleNamespace(executed_entry_ids=["gemini3_flash_default"], batch_ids={}),
    )

    main(
        [
            "benchmark",
            "run",
            "todo_extraction_bench_v1",
            "--allow-stale",
            "--rebase",
        ]
    )

    assert planned[0]["allow_stale"] is True
    assert planned[0]["rebase"] is True


def test_benchmark_run_returns_one_with_stale_error_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "evals.cli.run_benchmark",
        lambda **kwargs: BenchmarkStaleError(
            benchmark_id="todo_extraction_bench_v1",
            lock_path="../evals/locks/todo_extraction_bench_v1.json",
        ),
    )

    exit_code = main(["benchmark", "run", "todo_extraction_bench_v1"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "stale" in captured.out.lower()


def test_benchmark_report_html_prints_generated_path(monkeypatch, capsys):
    monkeypatch.setattr(
        "evals.cli.report_benchmark_html",
        lambda **kwargs: "/tmp/todo_extraction_bench_v1.html",
        raising=False,
    )

    exit_code = main(["benchmark", "report", "todo_extraction_bench_v1", "--html"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "/tmp/todo_extraction_bench_v1.html" in captured.out


def test_benchmark_report_open_generates_and_opens_html(monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(
        "evals.cli.open_benchmark_report_html",
        lambda **kwargs: opened.append(kwargs) or "/tmp/todo_extraction_bench_v1.html",
        raising=False,
    )

    exit_code = main(["benchmark", "report", "todo_extraction_bench_v1", "--open"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert opened == [{"benchmark_id": "todo_extraction_bench_v1"}]
    assert "/tmp/todo_extraction_bench_v1.html" in captured.out
