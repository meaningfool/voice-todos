from __future__ import annotations

provider_transport_failure = "provider_transport_failure"
output_validation_failure = "output_validation_failure"
evaluator_failure = "evaluator_failure"
unexpected_task_failure = "unexpected_task_failure"

_PROVIDER_HTTP_TRANSPORT_MARKERS = (
    "upstream connect error",
    "disconnect/reset before headers",
    "connection reset",
    "connection refused",
    "connection timed out",
    "reset reason: overflow",
)

_SERIALIZED_HTTPX_TRANSPORT_MESSAGES = (
    "connect failed",
    "read timed out",
    "write timed out",
)


def classify_failure_category(error_message: str | None) -> str:
    normalized_message = (error_message or "").casefold()

    if _is_provider_transport_failure(normalized_message):
        return provider_transport_failure
    if _is_output_validation_failure(normalized_message):
        return output_validation_failure
    if _is_evaluator_failure(normalized_message):
        return evaluator_failure
    return unexpected_task_failure


def _is_provider_transport_failure(normalized_message: str) -> bool:
    if "provider timeout" in normalized_message:
        return True

    if _is_exact_serialized_httpx_transport_failure(normalized_message):
        return True

    if any(
        marker in normalized_message
        for marker in (
            "connect failed",
            "connecterror",
            "nodename nor servname provided",
            "name or service not known",
            "read timed out",
            "write timed out",
            "temporary failure in name resolution",
            "connection reset",
            "connection refused",
            "connection timed out",
        )
    ):
        return True

    return _is_provider_http_5xx_transport_failure(normalized_message)


def _is_exact_serialized_httpx_transport_failure(normalized_message: str) -> bool:
    return normalized_message.strip() in _SERIALIZED_HTTPX_TRANSPORT_MESSAGES


def _is_provider_http_5xx_transport_failure(normalized_message: str) -> bool:
    if (
        "status_code: 5" not in normalized_message
        and "status code: 5" not in normalized_message
    ):
        return False

    return any(
        marker in normalized_message for marker in _PROVIDER_HTTP_TRANSPORT_MARKERS
    )


def _is_output_validation_failure(normalized_message: str) -> bool:
    return any(
        marker in normalized_message
        for marker in (
            "output validation",
            "unexpectedmodelbehavior",
        )
    )


def _is_evaluator_failure(normalized_message: str) -> bool:
    return any(
        marker in normalized_message
        for marker in (
            "evaluatorfailure",
            "evaluator failure",
        )
    )
