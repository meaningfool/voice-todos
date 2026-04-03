from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_evals.evaluators import EvaluatorFailure

from evals.common.failure_classification import classify_failure_category


def test_classify_failure_category_handles_provider_transport_failure():
    error_message = str(
        ModelHTTPError(
            503,
            "test-model",
            "upstream connect error or disconnect/reset before headers",
        )
    )

    assert classify_failure_category(error_message) == "provider_transport_failure"


def test_classify_failure_category_handles_connectivity_dns_failure():
    error_message = "ConnectError: [Errno 8] nodename nor servname provided, or not known"

    assert classify_failure_category(error_message) == "provider_transport_failure"


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
