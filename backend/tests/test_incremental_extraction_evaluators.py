from datetime import UTC, datetime

from pydantic_evals.evaluators import EvaluatorContext

from app.models import Todo
from evals.incremental_extraction_quality.models import (
    ReplayRunResult,
    ReplayStepResult,
)


def _build_context(
    *,
    expected_output: list[Todo],
    output: ReplayRunResult,
) -> EvaluatorContext[dict[str, object], ReplayRunResult, dict[str, str]]:
    return EvaluatorContext(
        name="replay-case-under-test",
        inputs={
            "reference_dt": datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
            "replay_steps": [],
        },
        metadata={
            "dataset": "todo_extraction_replay_v1",
            "case_type": "incremental_replay",
            "source_fixture": "fixture-name",
        },
        expected_output=expected_output,
        output=output,
        duration=0.25,
        _span_tree=object(),
        attributes={},
        metrics={},
    )


def test_final_todo_count_evaluator_reports_match_and_mismatch():
    from evals.incremental_extraction_quality.evaluators import FinalTodoCountEvaluator

    matching_ctx = _build_context(
        expected_output=[Todo(text="Buy milk")],
        output=ReplayRunResult(
            final_todos=[Todo(text="Call mom")],
            step_results=[
                ReplayStepResult(
                    step_index=1,
                    transcript="Call mom",
                    todos=[Todo(text="Call mom")],
                )
            ],
        ),
    )
    mismatch_ctx = _build_context(
        expected_output=[],
        output=ReplayRunResult(
            final_todos=[Todo(text="Unexpected todo")],
            step_results=[
                ReplayStepResult(
                    step_index=1,
                    transcript="Unexpected todo",
                    todos=[Todo(text="Unexpected todo")],
                )
            ],
        ),
    )

    matching_result = FinalTodoCountEvaluator().evaluate_sync(matching_ctx)
    mismatch_result = FinalTodoCountEvaluator().evaluate_sync(mismatch_ctx)

    assert matching_result == {
        "final_todo_count_match": True,
        "expected_final_todo_count": 1,
        "predicted_final_todo_count": 1,
    }
    assert mismatch_result == {
        "final_todo_count_match": False,
        "expected_final_todo_count": 0,
        "predicted_final_todo_count": 1,
    }
