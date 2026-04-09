from pathlib import Path

from evals.benchmarking.run import main


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
