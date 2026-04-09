from pathlib import Path
from types import SimpleNamespace

from evals.benchmarking.models import AxisDefinition
from evals.benchmarking.models import BenchmarkManifest
from evals.benchmarking.run import main
from evals.extraction_quality.experiment_configs import EXPERIMENTS


def test_attach_command_appends_experiment_ref(tmp_path):
    manifest_path = tmp_path / "benchmark.json"
    manifest_path.write_text(
        Path("tests/fixtures/evals/benchmarks/todo_extraction_model_smoke.json").read_text()
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
                        "thinking_mode": second_experiment.identity_metadata["thinking_mode"],
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
