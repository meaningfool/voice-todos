from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.models import Todo


@dataclass
class TodoCountEvaluator(
    Evaluator[dict[str, Any], list[Todo], dict[str, str]]
):
    def evaluate(
        self,
        ctx: EvaluatorContext[dict[str, Any], list[Todo], dict[str, str]],
    ) -> dict[str, bool | int]:
        expected_todo_count = len(ctx.expected_output or [])
        predicted_todo_count = len(ctx.output or [])

        return {
            "todo_count_match": expected_todo_count == predicted_todo_count,
            "expected_todo_count": expected_todo_count,
            "predicted_todo_count": predicted_todo_count,
        }


EXTRACTION_QUALITY_EVALUATORS = (TodoCountEvaluator(),)
