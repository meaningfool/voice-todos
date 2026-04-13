"""Compatibility re-exports for replay eval experiment configuration.

The replay suite now shares the canonical experiment registry with the
transcript-only extraction suite so both eval tracks stay in sync.
"""

from evals.extraction_quality.experiment_configs import (
    EXPERIMENTS,
    ExperimentDefinition,
    experiment_definition_from_entry_config,
    read_backend_env_var,
)

__all__ = [
    "EXPERIMENTS",
    "ExperimentDefinition",
    "read_backend_env_var",
    "experiment_definition_from_entry_config",
]
