from pathlib import Path

from app.prompts.registry import PromptRef
from evals.extraction_quality import experiment_configs
from evals.extraction_quality.experiment_configs import EXPERIMENTS
from evals.extraction_quality.run import _experiment_metadata, main

EXPECTED_EXPERIMENTS = [
    "gemini3_flash_default",
    "gemini3_flash_minimal_thinking",
    "gemini31_flash_lite_default",
    "gemini31_flash_lite_minimal_thinking",
    "mistral_small_4_default",
]


def test_experiment_registry_contains_expected_names():
    assert list(EXPERIMENTS) == EXPECTED_EXPERIMENTS


def test_main_list_experiments_prints_registry(capsys):
    exit_code = main(["--list-experiments"])
    captured = capsys.readouterr()

    assert exit_code == 0
    for experiment_name in EXPECTED_EXPERIMENTS:
        assert experiment_name in captured.out


def test_mistral_experiment_reports_provider_unavailability(monkeypatch):
    monkeypatch.setattr(
        experiment_configs,
        "_mistral_unavailable_reason",
        lambda: "mistral provider unavailable",
    )

    assert (
        EXPERIMENTS["mistral_small_4_default"].unavailable_reason()
        == "mistral provider unavailable"
    )


def test_experiment_metadata_includes_prompt_identity(monkeypatch):
    prompt_ref = PromptRef(
        family="todo_extraction",
        version="v1",
        path=Path("/tmp/todo_extraction_v1.md"),
        content="prompt body",
        sha256="prompt-sha-123",
    )

    monkeypatch.setattr(
        "evals.extraction_quality.run.get_extraction_prompt_ref",
        lambda config: prompt_ref,
    )

    metadata = _experiment_metadata(EXPERIMENTS["gemini3_flash_default"])

    assert metadata["prompt_family"] == "todo_extraction"
    assert metadata["prompt_version"] == "v1"
    assert metadata["prompt_sha"] == "prompt-sha-123"
