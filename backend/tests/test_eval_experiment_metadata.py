import hashlib

from evals.common.experiment_metadata import (
    build_experiment_metadata,
    config_fingerprint,
)


def test_build_experiment_metadata_includes_required_core_fields(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    evaluators_path = tmp_path / "evaluators.py"
    dataset_path.write_text('{"cases": []}\n')
    evaluators_path.write_text("EVALUATORS = []\n")
    full_config = {"temperature": 0, "provider": "google-gla"}

    metadata = build_experiment_metadata(
        suite="extraction_quality",
        dataset_name="todo_extraction_v1",
        dataset_path=dataset_path,
        evaluators_path=evaluators_path,
        experiment_id="gemini3_flash_default",
        model_name="gemini-3-flash-preview",
        prompt_sha="prompt-sha-123",
        repeat=2,
        task_retries=3,
        batch_id="batch-123",
        full_config=full_config,
    )

    assert set(metadata) == {
        "suite",
        "dataset_name",
        "dataset_sha",
        "evaluator_contract_sha",
        "experiment_id",
        "model_name",
        "prompt_sha",
        "config_fingerprint",
        "repeat",
        "task_retries",
        "batch_id",
    }
    assert metadata["suite"] == "extraction_quality"
    assert metadata["dataset_name"] == "todo_extraction_v1"
    assert metadata["dataset_sha"] == hashlib.sha256(
        dataset_path.read_bytes()
    ).hexdigest()
    assert metadata["evaluator_contract_sha"] == hashlib.sha256(
        evaluators_path.read_bytes()
    ).hexdigest()
    assert metadata["experiment_id"] == "gemini3_flash_default"
    assert metadata["model_name"] == "gemini-3-flash-preview"
    assert metadata["prompt_sha"] == "prompt-sha-123"
    assert metadata["config_fingerprint"] == config_fingerprint(full_config)
    assert metadata["repeat"] == 2
    assert metadata["task_retries"] == 3
    assert metadata["batch_id"] == "batch-123"


def test_config_fingerprint_changes_when_execution_config_changes():
    first = config_fingerprint({"model": "a", "repeat": 1})
    second = config_fingerprint({"model": "a", "repeat": 2})

    assert first != second
