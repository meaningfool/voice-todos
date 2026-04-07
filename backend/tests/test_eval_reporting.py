from datetime import UTC, datetime

import pytest
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_evals.evaluators import EvaluatorFailure
from pydantic_evals.reporting import EvaluationReport, ReportCase, ReportCaseFailure

from app.models import Todo
from evals.common.failure_classification import classify_failure_category
from evals.extraction_quality import result_artifacts


def test_classify_failure_category_handles_provider_transport_failure():
    error_message = str(
        ModelHTTPError(
            503,
            "test-model",
            "upstream connect error or disconnect/reset before headers",
        )
    )

    assert classify_failure_category(error_message) == "provider_transport_failure"


def test_classify_failure_category_does_not_treat_generic_provider_5xx_as_transport():
    error_message = str(
        ModelHTTPError(
            500,
            "test-model",
            "internal server error",
        )
    )

    assert classify_failure_category(error_message) == "unexpected_task_failure"


def test_classify_failure_category_handles_connectivity_dns_failure():
    error_message = (
        "ConnectError: [Errno 8] nodename nor servname provided, or not known"
    )

    assert classify_failure_category(error_message) == "provider_transport_failure"


@pytest.mark.parametrize(
    ("error_message", "expected_category"),
    [
        ("connect failed", "provider_transport_failure"),
        ("connect timed out", "provider_transport_failure"),
        ("read timed out", "provider_transport_failure"),
        ("write timed out", "provider_transport_failure"),
    ],
)
def test_classify_failure_category_handles_exhausted_serialized_transport_failures(
    error_message: str,
    expected_category: str,
):
    assert classify_failure_category(error_message) == expected_category


@pytest.mark.parametrize(
    "error_message",
    [
        "RuntimeError: connect failed while retrying",
        "TaskError: read timed out after 3 attempts",
        "transport wrapper: write timed out during cleanup",
    ],
)
def test_classify_failure_category_does_not_overmatch_transport_fragments(
    error_message: str,
):
    assert classify_failure_category(error_message) == "unexpected_task_failure"


def test_classify_failure_category_handles_output_validation_failure():
    error_message = str(
        UnexpectedModelBehavior("output validation failed: expected list of todos")
    )

    assert classify_failure_category(error_message) == "output_validation_failure"


def test_classify_failure_category_handles_evaluator_failure():
    error_message = str(
        EvaluatorFailure(
            "score",
            "evaluation blew up",
            "Traceback...",
            source=object(),
        )
    )

    assert classify_failure_category(error_message) == "evaluator_failure"


def test_classify_failure_category_falls_back_to_unexpected_task_failure():
    assert classify_failure_category("RuntimeError: boom") == "unexpected_task_failure"


def test_build_report_artifact_starts_with_pending_enrichment_fields():
    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[
            ReportCase(
                name="case-1",
                inputs={"transcript": "Pick up milk"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-1.json",
                },
                expected_output=[Todo(text="Pick up milk")],
                output=[Todo(text="Pick up milk")],
                metrics={"expected_todo_count": 1, "predicted_todo_count": 1},
                attributes={},
                scores={},
                labels={},
                assertions={},
                task_duration=0.1,
                total_duration=0.2,
                trace_id="case-trace-id",
                span_id="case-span-id",
            )
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_v1",
        },
        trace_id="report-trace-id",
        span_id="report-span-id",
    )

    payload = result_artifacts.build_report_artifact(
        report,
        repeat=1,
        max_concurrency=1,
        task_retries=0,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert payload["enrichment_status"] == "pending"
    assert payload["enrichment_reason"] is None
    assert payload["avg_task_duration_s"] is None
    assert payload["min_task_duration_s"] is None
    assert payload["max_task_duration_s"] is None
    assert payload["cases"] == [
        {
            "name": "case-1",
            "source_fixture": "fixture-1.json",
            "expected_todo_count": 1,
            "predicted_todo_count": 1,
            "trace_id": "case-trace-id",
            "span_id": "case-span-id",
        }
    ]


def test_build_report_artifact_classifies_serialized_transport_failure():
    report = EvaluationReport(
        name="gemini3_flash_default",
        cases=[],
        failures=[
            ReportCaseFailure(
                name="case-2",
                inputs={"transcript": "Schedule dentist"},
                metadata={
                    "dataset": "todo_extraction_v1",
                    "case_type": "extraction",
                    "source_fixture": "fixture-2.json",
                },
                expected_output=[Todo(text="Schedule dentist")],
                error_message="connect failed",
                error_stacktrace="Traceback...",
                trace_id="failure-trace-id",
                span_id="failure-span-id",
            )
        ],
        experiment_metadata={
            "experiment": "gemini3_flash_default",
            "dataset_name": "todo_extraction_v1",
        },
        trace_id="report-trace-id",
        span_id="report-span-id",
    )

    payload = result_artifacts.build_report_artifact(
        report,
        repeat=1,
        max_concurrency=1,
        task_retries=0,
        timestamp=datetime(2026, 4, 1, 16, 20, 0, tzinfo=UTC),
    )

    assert payload["failure_counts_by_category"] == {
        "provider_transport_failure": 1
    }
    assert payload["failures"] == [
        {
            "name": "case-2",
            "source_fixture": "fixture-2.json",
            "expected_todo_count": 1,
            "predicted_todo_count": None,
            "error_message": "connect failed",
            "trace_id": "failure-trace-id",
            "span_id": "failure-span-id",
            "failure_category": "provider_transport_failure",
        }
    ]
