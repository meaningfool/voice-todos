from __future__ import annotations

from httpx import NetworkError, TimeoutException
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.retries import RetryConfig
from pydantic_evals.evaluators import EvaluatorFailure
from tenacity import retry_if_exception, stop_after_attempt, wait_exponential

_MODEL_HTTP_TRANSPORT_MARKERS = (
    "upstream connect error",
    "disconnect/reset before headers",
    "connection reset",
    "connection refused",
    "connection timed out",
    "reset reason: overflow",
    "overflow",
)


def build_retry_task_config(task_retries: int) -> RetryConfig | None:
    if task_retries <= 0:
        return None

    return RetryConfig(
        retry=retry_if_exception(is_transient_task_failure),
        wait=wait_exponential(multiplier=0.5, max=4),
        stop=stop_after_attempt(task_retries + 1),
        reraise=True,
    )


def is_transient_task_failure(error: Exception) -> bool:
    if isinstance(error, (UnexpectedModelBehavior, EvaluatorFailure)):
        return False

    if isinstance(error, ModelHTTPError):
        return error.status_code >= 500 and _is_transport_flavored_model_http_error(
            error
        )

    return isinstance(error, (NetworkError, TimeoutException))


def _is_transport_flavored_model_http_error(error: ModelHTTPError) -> bool:
    normalized_message = error.message.casefold()
    return any(
        marker in normalized_message for marker in _MODEL_HTTP_TRANSPORT_MARKERS
    )
