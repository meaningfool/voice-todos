"""Benchmark Logfire query contract tests."""

from evals.logfire_query import normalize_benchmark_rows


def test_normalize_benchmark_rows_accepts_columnar_logfire_payload():
    payload = {
        "columns": [
            {
                "name": "experiment_run_id",
                "datatype": "Utf8",
                "nullable": True,
                "values": ["run-1", "run-2"],
            },
            {
                "name": "suite",
                "datatype": "Utf8",
                "nullable": True,
                "values": ["extraction", "replay"],
            },
            {
                "name": "failure_count",
                "datatype": "Int64",
                "nullable": True,
                "values": [0, 2],
            },
        ]
    }

    rows = normalize_benchmark_rows(payload)

    assert rows == [
        {
            "experiment_run_id": "run-1",
            "suite": "extraction",
            "failure_count": 0,
        },
        {
            "experiment_run_id": "run-2",
            "suite": "replay",
            "failure_count": 2,
        },
    ]
