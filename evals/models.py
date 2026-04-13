from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetRow(BaseModel):
    id: str
    input: dict
    expected_output: list[dict]
    metadata: dict = Field(default_factory=dict)


class DatasetDefinition(BaseModel):
    name: str
    version: str
    rows: list[DatasetRow]


class BenchmarkEntry(BaseModel):
    id: str
    label: str
    config: dict


class BenchmarkDefinition(BaseModel):
    benchmark_id: str
    dataset: str
    focus: str
    headline_metric: str
    repeat: int
    task_retries: int
    max_concurrency: int
    entries: list[BenchmarkEntry]


class ResolvedEntryConfig(BaseModel):
    suite: str
    dataset_family: str
    provider: str
    model_name: str
    prompt_version: str
    model_settings: dict = Field(default_factory=dict)


class BenchmarkRunResult(BaseModel):
    benchmark_id: str
    executed_entry_ids: list[str] = Field(default_factory=list)
    batch_ids: dict[str, str] = Field(default_factory=dict)


class EntryQuerySelector(BaseModel):
    entry_id: str
    label: str
    suite: str
    dataset_sha: str
    evaluator_contract_sha: str
    model_name: str
    prompt_sha: str
    config_fingerprint: str
    repeat: int
    task_retries: int


class BenchmarkEntryState(BaseModel):
    entry_id: str
    label: str
    status: str
    selected_run_id: str | None = None
    selected_timestamp: str | None = None
    headline_metric_value: float | None = None
    completed_case_count: int = 0
    failure_count: int = 0
    average_case_duration_s: float | None = None
    max_case_duration_s: float | None = None
    cost_usd: float | None = None
    config: dict = Field(default_factory=dict)
    failures: list[dict] = Field(default_factory=list)
    slowest_cases: list[dict] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    benchmark_id: str
    focus: str
    headline_metric: str
    entries: list[BenchmarkEntryState] = Field(default_factory=list)
    missing_entry_ids: list[str] = Field(default_factory=list)
