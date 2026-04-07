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
    enrichment_status: str = "pending",
    enrichment_reason: str | None = None,
) -> Path:
    payload = {
        "experiment_id": experiment_id,
        "trace_id": trace_id,
        "cases": cases,
        "failures": failures,
        "completed_cases": len(cases),
        "failure_count": len(failures),
        "overall_case_success_rate": (
            len(cases) / (len(cases) + len(failures)) if cases or failures else 0.0
        ),
        "failure_counts_by_category": {},
        "timestamp": "2026-04-03T09:32:51Z",
        "enrichment_status": enrichment_status,
        "enrichment_reason": enrichment_reason,
    }
    artifact_path = result_dir / f"{experiment_id}.json"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return artifact_path


def _load_artifact(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def _make_payload(
    *,
    experiment_id: str,
    trace_id: str | None,
    cases: list[dict[str, object]],
    failures: list[dict[str, object]],
    enrichment_status: str = "pending",
    enrichment_reason: str | None = None,
) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "trace_id": trace_id,
        "cases": cases,
        "failures": failures,
        "completed_cases": len(cases),
        "failure_count": len(failures),
        "overall_case_success_rate": (
            len(cases) / (len(cases) + len(failures)) if cases or failures else 0.0
        ),
        "failure_counts_by_category": {},
        "timestamp": "2026-04-03T09:32:51Z",
        "enrichment_status": enrichment_status,
        "enrichment_reason": enrichment_reason,
    }


@pytest.mark.asyncio
async def test_write_run_summary_marks_artifact_skipped_when_read_token_missing(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
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

    monkeypatch.setattr(logfire_enrichment, "_read_backend_env_var", lambda name: None)

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    payload = _load_artifact(artifact_path)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "skipped",
            "enrichment_reason": "missing_logfire_read_token",
        }
    ]
    assert payload["enrichment_status"] == "skipped"
    assert payload["enrichment_reason"] == "missing_logfire_read_token"
    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 0
    assert payload["overall_case_success_rate"] == 1.0
    assert payload["failure_counts_by_category"] == {}
    assert payload["avg_task_duration_s"] is None
    assert payload["min_task_duration_s"] is None
    assert payload["max_task_duration_s"] is None
    assert payload["cases"] == [
        {
            "name": "case-one",
            "span_id": "case-span-1",
            "trace_id": "trace-abc",
            "status": "success",
            "duration_s": None,
            "failure_category": None,
            "exception_summary": None,
            "token_metrics": {},
        }
    ]
    assert not (run_dir / "summary.json").exists()


@pytest.mark.asyncio
async def test_write_run_summary_supports_artifact_payloads_with_artifact_paths(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "payload-backed.json"
    original_payload = _make_payload(
        experiment_id="payload-backed",
        trace_id="trace-payload",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-payload",
            }
        ],
        failures=[],
    )
    artifact_path.write_text(json.dumps({"placeholder": True}) + "\n")

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
            assert "trace_id = 'trace-payload'" in sql
            return {
                "columns": [],
                "rows": [
                    {
                        "span_id": "case-span-1",
                        "parent_span_id": None,
                        "span_name": "case-one",
                        "kind": "span",
                        "message": "",
                        "duration": 0.4,
                        "attributes": "{\"role\": \"case\"}",
                    }
                ],
            }

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

    results = await logfire_enrichment.write_run_summary(
        result_dir=run_dir,
        artifact_paths=[artifact_path],
        artifact_payloads=[original_payload],
    )

    payload = _load_artifact(artifact_path)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "ok",
            "enrichment_reason": None,
        }
    ]
    assert payload["experiment_id"] == "payload-backed"
    assert payload["enrichment_status"] == "ok"
    assert payload["cases"][0]["duration_s"] == 0.4


@pytest.mark.asyncio
async def test_write_run_summary_rejects_artifact_payloads_without_paths(tmp_path):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()

    with pytest.raises(ValueError, match="artifact_payloads requires artifact_paths"):
        await logfire_enrichment.write_run_summary(
            result_dir=run_dir,
            artifact_payloads=[
                _make_payload(
                    experiment_id="payload-only",
                    trace_id="trace-only",
                    cases=[],
                    failures=[],
                )
            ],
        )


@pytest.mark.asyncio
async def test_write_run_summary_returns_invalid_artifact_result_for_malformed_file(
    tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "malformed.json"
    malformed_payload = {"experiment_id": "bad-artifact", "cases": [], "failures": {}}
    artifact_path.write_text(json.dumps(malformed_payload, indent=2) + "\n")

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "skipped",
            "enrichment_reason": "invalid_experiment_artifact",
        }
    ]
    assert _load_artifact(artifact_path) == malformed_payload


@pytest.mark.asyncio
async def test_write_run_summary_returns_invalid_artifact_result_for_non_object_json(
    tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "non-object.json"
    artifact_path.write_text('["not", "an", "object"]\n')

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "skipped",
            "enrichment_reason": "invalid_experiment_artifact",
        }
    ]
    assert json.loads(artifact_path.read_text()) == ["not", "an", "object"]


@pytest.mark.asyncio
async def test_write_run_summary_uses_disk_artifact_as_safe_base_for_payload_overrides(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "payload-safe-base.json"
    disk_payload = _make_payload(
        experiment_id="payload-safe-base",
        trace_id="trace-disk",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-disk",
                "status": "success",
                "duration_s": 0.9,
                "failure_category": None,
                "exception_summary": None,
                "token_metrics": {"input_tokens": 44, "output_tokens": 5},
            }
        ],
        failures=[],
        enrichment_status="ok",
    )
    disk_payload["model"] = {"name": "disk-model"}
    disk_payload["avg_task_duration_s"] = 0.9
    disk_payload["min_task_duration_s"] = 0.9
    disk_payload["max_task_duration_s"] = 0.9
    artifact_path.write_text(json.dumps(disk_payload, indent=2, sort_keys=True) + "\n")

    stale_payload = _make_payload(
        experiment_id="payload-safe-base",
        trace_id="trace-stale",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-stale",
            }
        ],
        failures=[],
    )

    monkeypatch.setattr(logfire_enrichment, "_read_backend_env_var", lambda name: None)

    results = await logfire_enrichment.write_run_summary(
        result_dir=run_dir,
        artifact_paths=[artifact_path],
        artifact_payloads=[stale_payload],
    )

    enriched = _load_artifact(artifact_path)
    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "skipped",
            "enrichment_reason": "missing_logfire_read_token",
        }
    ]
    assert enriched["trace_id"] == "trace-disk"
    assert enriched["model"] == {"name": "disk-model"}
    assert enriched["cases"] == disk_payload["cases"]
    assert enriched["avg_task_duration_s"] == 0.9


@pytest.mark.asyncio
async def test_write_run_summary_marks_missing_trace_id_partial_on_artifact(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "missing-trace.json"
    payload = _make_payload(
        experiment_id="missing-trace",
        trace_id=None,
        cases=[{"name": "case-one", "span_id": "case-span-1", "trace_id": None}],
        failures=[],
    )
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    monkeypatch.setattr(
        logfire_enrichment,
        "_read_backend_env_var",
        lambda name: "read-token",
    )

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    enriched = _load_artifact(artifact_path)
    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "partial",
            "enrichment_reason": "missing_trace_id",
        }
    ]
    assert enriched["enrichment_status"] == "partial"
    assert enriched["enrichment_reason"] == "missing_trace_id"
    assert enriched["cases"][0]["duration_s"] is None


@pytest.mark.asyncio
async def test_write_run_summary_preserves_existing_enrichment_on_degraded_rerun(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = run_dir / "already-enriched.json"
    payload = _make_payload(
        experiment_id="already-enriched",
        trace_id="trace-rerun",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-rerun",
                "status": "success",
                "duration_s": 0.75,
                "failure_category": None,
                "exception_summary": None,
                "token_metrics": {
                    "input_tokens": 12,
                    "output_tokens": 3,
                },
            }
        ],
        failures=[],
        enrichment_status="ok",
    )
    payload["avg_task_duration_s"] = 0.75
    payload["min_task_duration_s"] = 0.75
    payload["max_task_duration_s"] = 0.75
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    monkeypatch.setattr(logfire_enrichment, "_read_backend_env_var", lambda name: None)

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)

    enriched = _load_artifact(artifact_path)
    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "skipped",
            "enrichment_reason": "missing_logfire_read_token",
        }
    ]
    assert enriched["enrichment_status"] == "skipped"
    assert enriched["enrichment_reason"] == "missing_logfire_read_token"
    assert enriched["avg_task_duration_s"] == 0.75
    assert enriched["min_task_duration_s"] == 0.75
    assert enriched["max_task_duration_s"] == 0.75
    assert enriched["cases"] == payload["cases"]


@pytest.mark.asyncio
async def test_write_run_summary_rewrites_artifact_atomically(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
        run_dir,
        experiment_id="atomic-case",
        trace_id="trace-atomic",
        cases=[
            {
                "name": "case-one",
                "span_id": "case-span-1",
                "trace_id": "trace-atomic",
            }
        ],
        failures=[],
    )
    original_text = artifact_path.read_text()

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
    monkeypatch.setattr(
        logfire_enrichment.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError("rename failed")),
    )

    with pytest.raises(OSError, match="rename failed"):
        await logfire_enrichment.write_run_summary(result_dir=run_dir)

    assert artifact_path.read_text() == original_text
    assert list(run_dir.glob(f".{artifact_path.name}.*.tmp")) == []


@pytest.mark.asyncio
async def test_write_run_summary_uses_exact_trace_id_and_enriches_artifact_in_place(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
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
                "failure_category": "provider_transport_failure",
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
                "columns": [],
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

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)
    payload = _load_artifact(artifact_path)

    assert fake_client.queries == [
        (
            "SELECT trace_id, span_id, parent_span_id, span_name, kind, message, "
            "duration, attributes, exception_type, exception_message, "
            "http_response_status_code, otel_status_code "
            "FROM records WHERE trace_id = '019d52b132be51488e7d960a6f737adf' "
            "ORDER BY start_timestamp ASC"
        )
    ]
    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "ok",
            "enrichment_reason": None,
        }
    ]
    assert payload["enrichment_status"] == "ok"
    assert payload["enrichment_reason"] is None
    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 1
    assert payload["overall_case_success_rate"] == 0.5
    assert payload["failure_counts_by_category"] == {
        "provider_transport_failure": 1
    }
    assert payload["avg_task_duration_s"] == 0.375
    assert payload["min_task_duration_s"] == 0.25
    assert payload["max_task_duration_s"] == 0.5
    assert payload["cases"] == [
        {
            "name": "call-mom-memo-supplier",
            "span_id": "case-span-1",
            "trace_id": "019d52b132be51488e7d960a6f737adf",
            "status": "success",
            "duration_s": 0.25,
            "failure_category": None,
            "exception_summary": None,
            "token_metrics": {
                "cost_usd": 0.0125,
                "input_tokens": 100,
                "output_tokens": 20,
            },
        }
    ]
    assert payload["failures"] == [
        {
            "name": "refine-todo",
            "span_id": "case-span-2",
            "trace_id": "019d52b132be51488e7d960a6f737adf",
            "error_message": (
                "ModelHTTPError: status_code: 503, body: upstream connect error"
            ),
            "failure_category": "provider_transport_failure",
            "status": "failure",
            "duration_s": 0.5,
            "exception_summary": (
                "ModelHTTPError: status_code: 503, body: upstream connect error"
            ),
            "token_metrics": {
                "cost_usd": 0.02,
                "input_tokens": 80,
                "output_tokens": 0,
            },
        }
    ]
    assert not (run_dir / "summary.json").exists()


@pytest.mark.asyncio
async def test_write_run_summary_aggregates_nested_token_metrics_across_descendants(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
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

    await logfire_enrichment.write_run_summary(result_dir=run_dir)
    payload = _load_artifact(artifact_path)

    assert payload["enrichment_status"] == "ok"
    assert payload["cases"][0]["token_metrics"] == {
        "cost_usd": 0.0325,
        "input_tokens": 130,
        "output_tokens": 24,
        "thoughts_tokens": 5,
    }


@pytest.mark.asyncio
async def test_write_run_summary_marks_empty_query_results_partial_on_artifact(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
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

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)
    payload = _load_artifact(artifact_path)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "partial",
            "enrichment_reason": "logfire_query_returned_no_rows",
        }
    ]
    assert payload["enrichment_status"] == "partial"
    assert payload["enrichment_reason"] == "logfire_query_returned_no_rows"
    assert payload["cases"][0]["token_metrics"] == {}
    assert payload["avg_task_duration_s"] is None
    assert payload["min_task_duration_s"] is None
    assert payload["max_task_duration_s"] is None
    assert not (run_dir / "summary.json").exists()


@pytest.mark.asyncio
async def test_write_run_summary_records_partial_status_on_query_failure(
    monkeypatch, tmp_path
):
    from importlib import import_module

    logfire_enrichment = import_module("evals.common.logfire_enrichment")

    run_dir = tmp_path / "2026-04-03T09-32-51Z"
    run_dir.mkdir()
    artifact_path = _write_artifact(
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

    results = await logfire_enrichment.write_run_summary(result_dir=run_dir)
    payload = _load_artifact(artifact_path)

    assert results == [
        {
            "artifact_path": artifact_path,
            "enrichment_status": "partial",
            "enrichment_reason": "logfire_query_failed",
        }
    ]
    assert payload["enrichment_status"] == "partial"
    assert payload["enrichment_reason"] == "logfire_query_failed"
    assert payload["completed_cases"] == 1
    assert payload["failure_count"] == 0
    assert payload["cases"][0]["duration_s"] is None
    assert not (run_dir / "summary.json").exists()
