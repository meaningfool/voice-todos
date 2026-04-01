from datetime import UTC, datetime

from pydantic_evals.evaluators import EvaluatorContext

from app.models import Todo
from evals.extraction_quality.evaluators import TodoCountEvaluator


def _build_context(
    *,
    expected_output: list[Todo],
    output: list[Todo],
) -> EvaluatorContext[dict[str, object], list[Todo], dict[str, str]]:
    return EvaluatorContext(
        name="case-under-test",
        inputs={
            "transcript": "Call Marie tomorrow.",
            "reference_dt": datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
            "previous_todos": None,
        },
        metadata={
            "dataset": "todo_extraction_v1",
            "case_type": "extraction",
            "source_fixture": "fixture-name",
        },
        expected_output=expected_output,
        output=output,
        duration=0.25,
        _span_tree=object(),
        attributes={},
        metrics={},
    )


def test_todo_count_evaluator_reports_matching_counts():
    ctx = _build_context(
        expected_output=[Todo(text="Call Marie")],
        output=[Todo(text="Email Sarah")],
    )

    result = TodoCountEvaluator().evaluate_sync(ctx)

    assert result == {
        "todo_count_match": True,
        "expected_todo_count": 1,
        "predicted_todo_count": 1,
    }


def test_todo_count_evaluator_reports_empty_and_noisy_cases():
    empty_ctx = _build_context(expected_output=[], output=[])
    mismatch_ctx = _build_context(
        expected_output=[],
        output=[Todo(text="Unexpected todo")],
    )

    empty_result = TodoCountEvaluator().evaluate_sync(empty_ctx)
    mismatch_result = TodoCountEvaluator().evaluate_sync(mismatch_ctx)

    assert empty_result["todo_count_match"] is True
    assert empty_result["expected_todo_count"] == 0
    assert empty_result["predicted_todo_count"] == 0

    assert mismatch_result["todo_count_match"] is False
    assert mismatch_result["expected_todo_count"] == 0
    assert mismatch_result["predicted_todo_count"] == 1
