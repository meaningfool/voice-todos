from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class AxisDefinition(BaseModel):
    name: str
    field: str
    values: list[str]
    description: str | None = None


class AttachedExperimentRef(BaseModel):
    experiment_run_id: str
    note: str | None = None


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

    @model_validator(mode="after")
    def validate_unique_axis_fields(self) -> BenchmarkManifest:
        seen_fields: set[str] = set()
        duplicate_fields: set[str] = set()

        for axis in self.axes:
            if axis.field in seen_fields:
                duplicate_fields.add(axis.field)
            seen_fields.add(axis.field)

        if duplicate_fields:
            duplicate_list = ", ".join(sorted(duplicate_fields))
            raise ValueError(f"axis.field values must be unique: {duplicate_list}")

        return self


class BenchmarkCoverage(BaseModel):
    compatible_count: int
    incompatible_count: int
    compatible_coordinates: list[dict[str, str]] = Field(default_factory=list)
    missing_coordinates: list[dict[str, str]] = Field(default_factory=list)
    compatible_experiment_run_ids: list[str] = Field(default_factory=list)
    incompatible_experiment_run_ids: list[str] = Field(default_factory=list)
    missing_attached_experiment_run_ids: list[str] = Field(default_factory=list)
    unmappable_experiment_run_ids: list[str] = Field(default_factory=list)
