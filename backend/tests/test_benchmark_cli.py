import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import evals.benchmarking.run as benchmark_run
from evals.benchmarking.models import (
    AxisDefinition,
    BenchmarkCoverage,
    BenchmarkManifest,
)
from evals.benchmarking.reporting import BenchmarkReport
from evals.benchmarking.run import main
from evals.extraction_quality.experiment_configs import EXPERIMENTS


def test_attach_command_appends_experiment_ref(tmp_path):
    manifest_path = tmp_path / "benchmark.json"
    manifest_path.write_text(
        Path(
            "tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json"
        ).read_text()
    )

    exit_code = main(
        [
            "attach",
            str(manifest_path),
            "--experiment-run-id",
            "batch-123--gemini3_flash_default",
        ]
    )

    assert exit_code == 0
    reloaded = manifest_path.read_text()
    assert "batch-123--gemini3_flash_default" in reloaded


def test_launch_command_attaches_successful_experiment_refs(monkeypatch, tmp_path):
    manifest_path = tmp_path / "benchmark.json"
    experiment = EXPERIMENTS["gemini3_flash_default"]
    manifest_path.write_text(
        BenchmarkManifest(
            benchmark_id="todo_model_smoke_v1",
            title="Todo extraction smoke model benchmark",
            suite="extraction_quality",
            dataset_name="todo_extraction_smoke_v1",
            dataset_sha="dataset-sha",
            evaluator_contract_sha="eval-sha",
            fixed_config={
                "prompt_sha": experiment.identity_metadata["prompt_sha"],
            },
            axes=[
                AxisDefinition(
                    name="model",
                    field="model_name",
                    values=[experiment.identity_metadata["model_name"]],
                ),
                AxisDefinition(
                    name="thinking",
                    field="thinking_mode",
                    values=[experiment.identity_metadata["thinking_mode"]],
                ),
            ],
        ).model_dump_json(indent=2)
        + "\n"
    )

    monkeypatch.setattr(
        "evals.benchmarking.suite_adapters.launch_benchmark_experiments",
        lambda **kwargs: [
            {
                "experiment_run_id": "batch-123--gemini3_flash_default",
                "experiment_id": "gemini3_flash_default",
                "batch_id": "batch-123",
            }
        ],
    )

    exit_code = main(["launch", str(manifest_path)])

    assert exit_code == 0
    reloaded = BenchmarkManifest.model_validate_json(manifest_path.read_text())
    assert [ref.experiment_run_id for ref in reloaded.attached_experiment_runs] == [
        "batch-123--gemini3_flash_default"
    ]


def test_launch_command_missing_only_appends_new_batch_refs(monkeypatch, tmp_path):
    manifest_path = tmp_path / "benchmark.json"
    first_experiment = EXPERIMENTS["gemini3_flash_default"]
    second_experiment = EXPERIMENTS["gemini31_flash_lite_default"]
    manifest_path.write_text(
        BenchmarkManifest(
            benchmark_id="todo_model_smoke_v1",
            title="Todo extraction smoke model benchmark",
            suite="extraction_quality",
            dataset_name="todo_extraction_smoke_v1",
            dataset_sha="dataset-sha",
            evaluator_contract_sha="eval-sha",
            fixed_config={
                "prompt_sha": first_experiment.identity_metadata["prompt_sha"],
            },
            axes=[
                AxisDefinition(
                    name="model",
                    field="model_name",
                    values=[
                        first_experiment.identity_metadata["model_name"],
                        second_experiment.identity_metadata["model_name"],
                    ],
                ),
                AxisDefinition(
                    name="thinking",
                    field="thinking_mode",
                    values=[first_experiment.identity_metadata["thinking_mode"]],
                ),
            ],
            attached_experiment_runs=[
                {
                    "experiment_run_id": "batch-old--gemini3_flash_default",
                }
            ],
        ).model_dump_json(indent=2)
        + "\n"
    )

    monkeypatch.setattr(
        "evals.benchmarking.run.build_benchmark_report",
        lambda **kwargs: SimpleNamespace(
            missing_coordinates=[
                {
                    "model_name": second_experiment.identity_metadata["model_name"],
                    "thinking_mode": second_experiment.identity_metadata[
                        "thinking_mode"
                    ],
                }
            ]
        ),
    )

    launch_calls: list[dict[str, object]] = []

    def fake_launch(**kwargs):
        launch_calls.append(kwargs)
        return [
            {
                "experiment_run_id": "batch-new--gemini31_flash_lite_default",
                "experiment_id": "gemini31_flash_lite_default",
                "batch_id": "batch-new",
            }
        ]

    monkeypatch.setattr(
        "evals.benchmarking.suite_adapters.launch_benchmark_experiments",
        fake_launch,
    )

    exit_code = main(["launch", str(manifest_path), "--missing-only"])

    assert exit_code == 0
    assert launch_calls == [
        {
            "suite": "extraction_quality",
            "experiment_names": ["gemini31_flash_lite_default"],
            "repeat": 1,
            "task_retries": 0,
            "max_concurrency": 1,
            "dataset_path": None,
            "allow_untracked": False,
        }
    ]
    reloaded = BenchmarkManifest.model_validate_json(manifest_path.read_text())
    assert [ref.experiment_run_id for ref in reloaded.attached_experiment_runs] == [
        "batch-old--gemini3_flash_default",
        "batch-new--gemini31_flash_lite_default",
    ]


def test_coverage_command_prints_coverage_json(monkeypatch, tmp_path, capsys):
    manifest_path = tmp_path / "benchmark.json"
    manifest_path.write_text(
        Path(
            "tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json"
        ).read_text()
    )

    monkeypatch.setattr(benchmark_run, "_fetch_attached_records", lambda manifest: [])
    monkeypatch.setattr(
        benchmark_run,
        "build_benchmark_coverage",
        lambda manifest, fetched: BenchmarkCoverage(
            compatible_count=1,
            incompatible_count=0,
            compatible_coordinates=[{"model_name": "model-a"}],
            missing_coordinates=[{"model_name": "model-b"}],
            compatible_experiment_run_ids=["run-a"],
        ),
    )

    exit_code = main(["coverage", str(manifest_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"compatible_count": 1' in captured.out
    assert '"missing_coordinates"' in captured.out


def test_report_command_prints_report_json(monkeypatch, tmp_path, capsys):
    manifest_path = tmp_path / "benchmark.json"
    manifest_path.write_text(
        Path(
            "tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json"
        ).read_text()
    )

    monkeypatch.setattr(
        benchmark_run,
        "build_benchmark_report",
        lambda **kwargs: BenchmarkReport(
            benchmark_id="todo_model_smoke_v1",
            compatible_experiments=["run-a"],
            missing_coordinates=[{"model_name": "model-b"}],
        ),
    )

    exit_code = main(["report", str(manifest_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"benchmark_id": "todo_model_smoke_v1"' in captured.out
    assert '"compatible_experiments"' in captured.out


def test_benchmark_cli_script_path_runs_help():
    result = subprocess.run(
        [sys.executable, "evals/benchmarking/run.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Benchmark workflows for eval experiments." in result.stdout
