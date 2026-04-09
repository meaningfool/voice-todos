from evals.benchmarking.suite_adapters import resolve_coordinate_experiments
from evals.extraction_quality.experiment_configs import EXPERIMENTS


def test_resolve_coordinate_experiments_matches_registry_by_axis_and_fixed_config():
    experiment = EXPERIMENTS["gemini3_flash_default"]

    matches = resolve_coordinate_experiments(
        suite="extraction_quality",
        coordinate={
            "model_name": experiment.identity_metadata["model_name"],
            "thinking_mode": experiment.identity_metadata["thinking_mode"],
        },
        fixed_config={
            "prompt_sha": experiment.identity_metadata["prompt_sha"],
        },
    )

    assert matches == [experiment.name]
