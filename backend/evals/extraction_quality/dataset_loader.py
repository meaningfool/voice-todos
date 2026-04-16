from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset

from app.models import Todo
from evals.benchmark_ids import TODO_EXTRACTION_BENCHMARK_ID
from evals.storage import benchmark_lock_path

DATASET_PATH = benchmark_lock_path(TODO_EXTRACTION_BENCHMARK_ID)


def load_extraction_quality_dataset(
    path: Path | None = None,
) -> Dataset[dict[str, Any], list[Todo], dict[str, str]]:
    dataset_path = path or DATASET_PATH
    payload = json.loads(dataset_path.read_text())

    if "rows" in payload:
        dataset_name = f"{payload['name']}_{payload['version']}"
        cases = [
            _build_case_from_canonical_row(raw_row, dataset_name=dataset_name)
            for raw_row in payload["rows"]
        ]
        return Dataset(name=dataset_name, cases=cases)

    return Dataset(
        name=payload["dataset"],
        cases=[
            _build_case(raw_case, dataset_name=payload["dataset"])
            for raw_case in payload["cases"]
        ],
    )


def _build_case(
    raw_case: dict[str, Any],
    *,
    dataset_name: str,
) -> Case[dict[str, Any], list[Todo], dict[str, str]]:
    previous_todos = raw_case["previous_todos"]
    if previous_todos is not None:
        previous_todos = [Todo.model_validate(todo) for todo in previous_todos]

    return Case(
        name=raw_case["name"],
        inputs={
            "transcript": raw_case["transcript"],
            "reference_dt": datetime.fromisoformat(raw_case["reference_dt"]),
            "previous_todos": previous_todos,
        },
        expected_output=[
            Todo.model_validate(todo) for todo in raw_case["expected_todos"]
        ],
        metadata={
            "dataset": dataset_name,
            "case_type": "extraction",
            "source_fixture": raw_case["source_fixture"],
        },
    )


def _build_case_from_canonical_row(
    raw_row: dict[str, Any],
    *,
    dataset_name: str,
) -> Case[dict[str, Any], list[Todo], dict[str, str]]:
    row_input = raw_row["input"]
    previous_todos = row_input["previous_todos"]
    if previous_todos is not None:
        previous_todos = [Todo.model_validate(todo) for todo in previous_todos]

    return Case(
        name=raw_row["id"],
        inputs={
            "transcript": row_input["transcript"],
            "reference_dt": datetime.fromisoformat(row_input["reference_dt"]),
            "previous_todos": previous_todos,
        },
        expected_output=[
            Todo.model_validate(todo) for todo in raw_row["expected_output"]
        ],
        metadata={
            "dataset": dataset_name,
            "case_type": "extraction",
            "source_fixture": raw_row.get("metadata", {}).get(
                "source_fixture",
                raw_row["id"],
            ),
        },
    )
