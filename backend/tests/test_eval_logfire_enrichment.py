from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_artifact(
    result_dir: Path,
    *,
    experiment_id: str,
    trace_id: str,
    cases: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> Path:
    payload = {
        "experiment_id": experiment_id,
        "trace_id": trace_id,
        "cases": cases,
        "failures": failures,
        "timestamp": "2026-04-03T09:32:51Z",
    }
    artifact_path = result_dir / f"{experiment_id}.json"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return artifact_path


@pytest.mark.asyncio
async def test_write_run_summary_skips_when_read_token_missing(monkeypatch, tmp_path):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    _write_artifact(
        run_dir,
        experiment_id="gemini3_flash_default",
        trace_id="trace-abc",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-abc",
            }
        ],
        failures=[],
    )

    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: None,
    )

    summary = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert summary["status"] == "skipped"
    assert summary["reason"] == "missing_logfire_read_token"
    assert summary["run_timestamp"] == "2026-04-03T09:32:51Z"
    assert summary["experiments"] == [
        {
            "experiment_id": "gemini3_flash_default",
            "trace_id": "trace-abc",
            "status": "skipped",
            "reason": "missing_logfire_read_token",
            "completed_cases": 1,
            "failure_count": 0,
            "overall_case_success_rate": 1.0,
            "failure_counts_by_category": {},
            "avg_task_duration_s": None,
            "min_task_duration_s": None,
            "max_task_duration_s": None,
            "cases": [
                {
                    "name": "case-one",
                    "status": "success",
                    "duration_s": None,
                    "failure_category": None,
                    "exception_summary": None,
                    "token_metrics": {},
                }
            ],
        }
    ]
    assert (run_dir / "summary.json").exists()


@pytest.mark.asyncio
async def test_write_run_summary_uses_exact_trace_id_and_case_metrics(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    _write_artifact(
        run_dir,
        experiment_id="mistral_small_4_default",
        trace_id="019d52b132be51488e7d960a6f737adf",
        cases=[
            {
                "name": "call-mom-memo-supplier",
                "span_id": "case-span-1",
                "trace_id": "019d52b132be51488e7d960a6f737adf",
            },
        ],
        failures=[
            {
                "name": "refine-todo",
                "span_id": "case-span-2",
                "trace_id": "019d52b132be51488e7d960a6f737adf",
                "error_message": (
                    "ModelHTTPError: status_code: 503, body: upstream connect error"
                ),
            }
        ],
    )

    class FakeAsyncLogfireQueryClient:
        def __init__(self, read_token: str):
            self.read_token = read_token
            self.queries: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def query_json_rows(
            self,
            sql,
            min_timestamp=None,
            max_timestamp=None,
            limit=None,
        ):
            self.queries.append(sql)
            assert "trace_id = '019d52b132be51488e7d960a6f737adf'" in sql
            return {
                "columns": [
                    {"name": "span_id", "datatype": "string", "nullable": False},
                    {"name": "parent_span_id", "datatype": "string", "nullable": True},
                    {"name": "span_name", "datatype": "string", "nullable": False},
                    {"name": "kind", "datatype": "string", "nullable": False},
                    {"name": "message", "datatype": "string", "nullable": False},
                    {"name": "duration", "datatype": "float64", "nullable": True},
                    {"name": "attributes", "datatype": "string", "nullable": True},
                ],
                "rows": [
                    {
                        "span_id": "case-span-1",
                        "parent_span_id": None,
                        "span_name": "call-mom-memo-supplier",
                        "kind": "span",
                        "message": "",
                        "duration": 0.25,
                        "attributes": "{\"role\": \"case\"}",
                    },
                    {
                        "span_id": "provider-span-1",
                        "parent_span_id": "case-span-1",
                        "span_name": "provider.request",
                        "kind": "span",
                        "message": "",
                        "duration": 0.1,
                        "attributes": (
                            "{\"input_tokens\": 100, \"output_tokens\": 20, "
                            "\"cost_usd\": 0.0125}"
                        ),
                    },
                    {
                        "span_id": "case-span-2",
                        "parent_span_id": None,
                        "span_name": "refine-todo",
                        "kind": "span",
                        "message": (
                            "ModelHTTPError: status_code: 503, body: upstream "
                            "connect error"
                        ),
                        "duration": 0.5,
                        "attributes": "{\"role\": \"case\"}",
                    },
                    {
                        "span_id": "provider-span-2",
                        "parent_span_id": "case-span-2",
                        "span_name": "provider.request",
                        "kind": "span",
                        "message": "",
                        "duration": 0.2,
                        "attributes": (
                            "{\"input_tokens\": 80, \"output_tokens\": 0, "
                            "\"cost\": 0.02}"
                        ),
                    },
                ],
            }

    fake_client = FakeAsyncLogfireQueryClient("read-token")
    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: "read-token",
    )
    monkeypatch.setattr(
        logfire_enrichment,
        "AsyncLogfireQueryClient",
        lambda read_token: fake_client,
    )

    summary = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert fake_client.queries == [
        (
            "SELECT trace_id, span_id, parent_span_id, span_name, kind, message, "
            "duration, attributes, exception_type, exception_message, "
            "http_response_status_code, otel_status_code "
            "FROM records WHERE trace_id = '019d52b132be51488e7d960a6f737adf' "
            "ORDER BY start_timestamp ASC"
        )
    ]
    assert summary["status"] == "ok"
    assert summary["completed_cases"] == 1
    assert summary["failure_count"] == 1
    assert summary["overall_case_success_rate"] == 0.5
    assert summary["failure_counts_by_category"] == {
        "provider_transport_failure": 1
    }
    assert summary["avg_task_duration_s"] == 0.375
    assert summary["min_task_duration_s"] == 0.25
    assert summary["max_task_duration_s"] == 0.5
    assert summary["experiments"][0]["cases"][0]["token_metrics"] == {
        "cost_usd": 0.0125,
        "input_tokens": 100,
        "output_tokens": 20,
    }
    assert summary["experiments"][0]["cases"][1]["token_metrics"] == {
        "cost_usd": 0.02,
        "input_tokens": 80,
        "output_tokens": 0,
    }
    assert summary["experiments"] == [
        {
            "experiment_id": "mistral_small_4_default",
            "trace_id": "019d52b132be51488e7d960a6f737adf",
            "status": "ok",
            "reason": None,
            "completed_cases": 1,
            "failure_count": 1,
            "overall_case_success_rate": 0.5,
            "failure_counts_by_category": {
                "provider_transport_failure": 1
            },
            "avg_task_duration_s": 0.375,
            "min_task_duration_s": 0.25,
            "max_task_duration_s": 0.5,
            "cases": [
                {
                    "name": "call-mom-memo-supplier",
                    "status": "success",
                    "duration_s": 0.25,
                    "failure_category": None,
                    "exception_summary": None,
                    "token_metrics": {
                        "cost_usd": 0.0125,
                        "input_tokens": 100,
                        "output_tokens": 20,
                    },
                },
                {
                    "name": "refine-todo",
                    "status": "failure",
                    "duration_s": 0.5,
                    "failure_category": "provider_transport_failure",
                    "exception_summary": (
                        "ModelHTTPError: status_code: 503, body: upstream connect error"
                    ),
                    "token_metrics": {
                        "cost_usd": 0.02,
                        "input_tokens": 80,
                        "output_tokens": 0,
                    },
                },
            ],
        }
    ]
    assert (run_dir / "summary.json").exists()


@pytest.mark.asyncio
async def test_write_run_summary_aggregates_nested_token_metrics_across_descendants(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    _write_artifact(
        run_dir,
        experiment_id="gemini3_flash_default",
        trace_id="trace-nested",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-nested",
            }
        ],
        failures=[],
    )

    class FakeAsyncLogfireQueryClient:
        def __init__(self, read_token: str):
            self.read_token = read_token
            self.queries: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def query_json_rows(
            self,
            sql,
            min_timestamp=None,
            max_timestamp=None,
            limit=None,
        ):
            self.queries.append(sql)
            return {
                "columns": [],
                "rows": [
                    {
                        "span_id": "case-span-1",
                        "parent_span_id": None,
                        "span_name": "case-one",
                        "kind": "span",
                        "message": "",
                        "duration": 0.3,
                        "attributes": "{\"role\": \"case\"}",
                    },
                    {
                        "span_id": "provider-span-1",
                        "parent_span_id": "case-span-1",
                        "span_name": "provider.request",
                        "kind": "span",
                        "message": "",
                        "duration": 0.1,
                        "attributes": json.dumps(
                            {
                                "gen_ai": {
                                    "usage": {
                                        "input_tokens": 100,
                                        "output_tokens": 20,
                                        "details": {"thoughts_tokens": 5},
                                    }
                                },
                                "operation": {"cost": 0.0125},
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "span_id": "provider-span-2",
                        "parent_span_id": "case-span-1",
                        "span_name": "provider.retry",
                        "kind": "span",
                        "message": "",
                        "duration": 0.2,
                        "attributes": json.dumps(
                            {
                                "gen_ai.usage.input_tokens": 30,
                                "gen_ai.usage.output_tokens": 4,
                                "operation.cost": 0.02,
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            }

    fake_client = FakeAsyncLogfireQueryClient("read-token")
    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: "read-token",
    )
    monkeypatch.setattr(
        logfire_enrichment,
        "AsyncLogfireQueryClient",
        lambda read_token: fake_client,
    )

    summary = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert summary["status"] == "ok"
    assert summary["experiments"][0]["cases"][0]["token_metrics"] == {
        "cost_usd": 0.0325,
        "input_tokens": 130,
        "output_tokens": 24,
        "thoughts_tokens": 5,
    }


@pytest.mark.asyncio
async def test_write_run_summary_marks_empty_query_results_partial(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    _write_artifact(
        run_dir,
        experiment_id="gemini3_flash_default",
        trace_id="trace-empty",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-empty",
            }
        ],
        failures=[],
    )

    class FakeAsyncLogfireQueryClient:
        def __init__(self, read_token: str):
            self.read_token = read_token

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def query_json_rows(
            self,
            sql,
            min_timestamp=None,
            max_timestamp=None,
            limit=None,
        ):
            return {"columns": [], "rows": []}

    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: "read-token",
    )
    monkeypatch.setattr(
        logfire_enrichment,
        "AsyncLogfireQueryClient",
        lambda read_token: FakeAsyncLogfireQueryClient(read_token),
    )

    summary = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert summary["status"] == "partial"
    assert summary["reason"] == "logfire_query_returned_no_rows"
    assert summary["experiments"][0]["status"] == "partial"
    assert summary["experiments"][0]["reason"] == "logfire_query_returned_no_rows"
    assert summary["experiments"][0]["cases"][0]["token_metrics"] == {}


@pytest.mark.asyncio
async def test_write_run_summary_records_partial_status_on_query_failure(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    _write_artifact(
        run_dir,
        experiment_id="gemini3_flash_default",
        trace_id="trace-partial",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-partial",
            }
        ],
        failures=[],
    )

    class FakeAsyncLogfireQueryClient:
        def __init__(self, read_token: str):
            self.read_token = read_token

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def query_json_rows(
            self,
            sql,
            min_timestamp=None,
            max_timestamp=None,
            limit=None,
        ):
            raise RuntimeError("logfire unavailable")

    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: "read-token",
    )
    monkeypatch.setattr(
        logfire_enrichment,
        "AsyncLogfireQueryClient",
        lambda read_token: FakeAsyncLogfireQueryClient(read_token),
    )

    summary = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert summary["status"] == "partial"
    assert summary["reason"] == "logfire_query_failed"
    assert summary["experiments"][0]["status"] == "partial"
    assert summary["experiments"][0]["reason"] == "logfire_query_failed"
    assert summary["experiments"][0]["completed_cases"] == 1
    assert summary["experiments"][0]["failure_count"] == 0
    assert (run_dir / "summary.json").exists()
