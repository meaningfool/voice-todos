"""Compatibility re-exports for replay eval experiment configuration.

The replay suite now shares the canonical experiment registry with the
transcript-only extraction suite so both eval tracks stay in sync.
"""

from evals.extraction_quality.experiment_configs import (
    EXPERIMENTS,
    ExperimentDefinition,
    _read_backend_env_var,
)

__all__ = ["EXPERIMENTS", "ExperimentDefinition", "_read_backend_env_var"]
