"""Benchmark Logfire query contract tests."""

from evals.logfire_query import LogfireBenchmarkQueryClient, normalize_benchmark_rows


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


def test_fetch_case_spans_uses_single_query_with_explicit_limit(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "rows": [
                    {
                        "trace_id": "trace-1",
                        "start_timestamp": "2026-04-16T10:00:00Z",
                        "level": 9,
                        "case_id": "case-1",
                        "task_duration": "1.5",
                    },
                    {
                        "trace_id": "trace-2",
                        "start_timestamp": "2026-04-16T10:00:01Z",
                        "level": 17,
                        "case_id": "case-2",
                        "task_duration": None,
                    },
                ]
            }

    def fake_get(url, *, params, headers, timeout):
        calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr("evals.logfire_query.httpx.get", fake_get)

    client = LogfireBenchmarkQueryClient(
        read_token="token",
        project_name="voice-todos",
        query_url="https://example.invalid/v1/query",
    )

    rows = client.fetch_case_spans(["trace-1", "trace-2"])

    assert rows == [
        {
            "trace_id": "trace-1",
            "start_timestamp": "2026-04-16T10:00:00Z",
            "level": 9,
            "case_id": "case-1",
            "task_duration": "1.5",
        },
        {
            "trace_id": "trace-2",
            "start_timestamp": "2026-04-16T10:00:01Z",
            "level": 17,
            "case_id": "case-2",
            "task_duration": None,
        },
    ]
    assert len(calls) == 1
    assert calls[0]["params"]["limit"] == 1000
    assert "trace_id = 'trace-1'" in calls[0]["params"]["sql"]
    assert "trace_id = 'trace-2'" in calls[0]["params"]["sql"]
