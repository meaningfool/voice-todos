from __future__ import annotations

from pydantic import BaseModel, Field


class AxisDefinition(BaseModel):
    name: str
    field: str
    values: list[str]
    description: str | None = None


class AttachedExperimentRef(BaseModel):
    experiment_run_id: str
    note: str | None = None

    def __getitem__(self, key: str) -> str | None:
        return getattr(self, key)


class BenchmarkManifest(BaseModel):
    benchmark_id: str
    title: str
    description: str | None = None
    suite: str
    dataset_name: str
    dataset_sha: str
    evaluator_contract_sha: str
    fixed_config: dict[str, str]
    axes: list[AxisDefinition]
    attached_experiment_runs: list[AttachedExperimentRef] = Field(default_factory=list)
