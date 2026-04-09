from evals.benchmarking.logfire_query import (
    LogfireBenchmarkQueryClient,
    _build_attached_experiments_query,
    _normalize_query_rows,
)
from evals.benchmarking.models import AttachedExperimentRef


def test_query_client_defaults_to_region_api_url(monkeypatch):
    monkeypatch.setattr(
        "evals.benchmarking.logfire_query.get_logfire_api_url",
        lambda: "https://logfire-eu.pydantic.dev",
    )
    monkeypatch.setattr(
        "evals.benchmarking.logfire_query.get_logfire_read_token",
        lambda: "read-token",
    )
    monkeypatch.setattr(
        "evals.benchmarking.logfire_query.get_logfire_project_name",
        lambda: "voice-todos",
    )

    client = LogfireBenchmarkQueryClient()

    assert client.query_url == "https://logfire-eu.pydantic.dev/v1/query"


def test_build_attached_experiments_query_reads_nested_metadata_fields():
    sql = _build_attached_experiments_query(
        [AttachedExperimentRef(experiment_run_id="run-123")]
    )

    assert "attributes->'metadata'->>'experiment_run_id' AS experiment_run_id" in sql
    assert "attributes->'metadata'->>'experiment_id' AS experiment_id" in sql
    assert "attributes->'metadata'->>'batch_id' AS batch_id" in sql


def test_normalize_query_rows_supports_column_oriented_payloads():
    payload = {
        "columns": [
            {"name": "experiment_run_id", "values": ["run-a", "run-b"]},
            {"name": "experiment_id", "values": ["exp-a", "exp-b"]},
            {"name": "batch_id", "values": ["batch-a", "batch-b"]},
        ]
    }

    rows = _normalize_query_rows(payload)

    assert rows == [
        {
            "experiment_run_id": "run-a",
            "experiment_id": "exp-a",
            "batch_id": "batch-a",
        },
        {
            "experiment_run_id": "run-b",
            "experiment_id": "exp-b",
            "batch_id": "batch-b",
        },
    ]
