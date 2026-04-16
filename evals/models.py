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


class BenchmarkLockMetadata(BaseModel):
    benchmark_id: str
    hosted_dataset: str
    hosted_dataset_name: str | None = None
    fetched_at: str
    dataset_hash: str
    hash_algorithm: str = "sha256"
    case_count: int


class BenchmarkEntry(BaseModel):
    id: str
    label: str
    config: dict


class BenchmarkDefinition(BaseModel):
    benchmark_id: str
    hosted_dataset: str
    dataset_family: str
    focus: str
    headline_metric: str
    repeat: int
    task_retries: int
    max_concurrency: int
    entries: list[BenchmarkEntry]


class LockedDatasetDefinition(DatasetDefinition):
    benchmark_lock: BenchmarkLockMetadata = Field(alias="_benchmark_lock")


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
    total_case_count: int
    passed_case_count: int
    incorrect_case_count: int
    incomplete_case_count: int
    completed_case_count: int = 0
    failure_count: int = 0
    average_case_duration_s: float | None = None
    max_case_duration_s: float | None = None
    cost_usd: float | None = None
    config: dict = Field(default_factory=dict)
    failures: list[dict] = Field(default_factory=list)
    incorrect_cases: list[dict] = Field(default_factory=list)
    incomplete_cases: list[dict] = Field(default_factory=list)
    slowest_cases: list[dict] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    benchmark_id: str
    hosted_dataset: str
    focus: str
    headline_metric: str
    display_headline_metric: str
    active_lock_path: str | None = None
    locked_dataset_hash: str | None = None
    current_hosted_dataset_hash: str | None = None
    stale: bool = False
    entries: list[BenchmarkEntryState] = Field(default_factory=list)
    missing_entry_ids: list[str] = Field(default_factory=list)
