from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.incremental_extraction_quality.models import ReplayRunResult


@dataclass
class FinalTodoCountEvaluator(
    Evaluator[dict[str, Any], ReplayRunResult, dict[str, str]]
):
    metric_name = "final_todo_count_match"

    def evaluate(
        self,
        ctx: EvaluatorContext[dict[str, Any], ReplayRunResult, dict[str, str]],
    ) -> dict[str, bool | int]:
        expected_final_todo_count = len(ctx.expected_output or [])
        predicted_final_todo_count = len(ctx.output.final_todos)

        return {
            "final_todo_count_match": (
                expected_final_todo_count == predicted_final_todo_count
            ),
            "expected_final_todo_count": expected_final_todo_count,
            "predicted_final_todo_count": predicted_final_todo_count,
        }


INCREMENTAL_EXTRACTION_QUALITY_EVALUATORS = (FinalTodoCountEvaluator(),)
