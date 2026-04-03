from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

from evals.common.retry_policy import (
    build_retry_task_config,
    is_transient_task_failure,
)


def test_build_retry_task_config_returns_none_for_zero_retries():
    assert build_retry_task_config(task_retries=0) is None


def test_transient_provider_transport_errors_are_retryable():
    assert is_transient_task_failure(
        ModelHTTPError(
            503,
            "test-model",
            "upstream connect error or disconnect/reset before headers",
        )
    )


def test_output_validation_failures_are_not_retryable():
    assert not is_transient_task_failure(
        UnexpectedModelBehavior("output validation failed: expected list of todos")
    )
