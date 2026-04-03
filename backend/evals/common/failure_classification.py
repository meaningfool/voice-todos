from __future__ import annotations

provider_transport_failure = "provider_transport_failure"
output_validation_failure = "output_validation_failure"
evaluator_failure = "evaluator_failure"
unexpected_task_failure = "unexpected_task_failure"


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
    return any(
        marker in normalized_message
        for marker in (
            "provider timeout",
            "upstream connect error",
            "connection reset",
            "connection refused",
            "connection timed out",
            "status_code: 5",
            "status code: 5",
        )
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
