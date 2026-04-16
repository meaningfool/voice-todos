from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset

from app.models import Todo
from evals.benchmark_ids import TODO_REPLAY_BENCHMARK_ID
from evals.incremental_extraction_quality.models import ReplayStep
from evals.storage import benchmark_lock_path

DATASET_PATH = benchmark_lock_path(TODO_REPLAY_BENCHMARK_ID)


def load_incremental_replay_dataset(
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
    return Case(
        name=raw_case["name"],
        inputs={
            "reference_dt": datetime.fromisoformat(raw_case["reference_dt"]),
            "replay_steps": [
                ReplayStep.model_validate(step) for step in raw_case["replay_steps"]
            ],
        },
        expected_output=[
            Todo.model_validate(todo) for todo in raw_case["expected_final_todos"]
        ],
        metadata={
            "dataset": dataset_name,
            "case_type": "incremental_replay",
            "source_fixture": raw_case["source_fixture"],
        },
    )


def _build_case_from_canonical_row(
    raw_row: dict[str, Any],
    *,
    dataset_name: str,
) -> Case[dict[str, Any], list[Todo], dict[str, str]]:
    row_input = raw_row["input"]
    return Case(
        name=raw_row["id"],
        inputs={
            "reference_dt": datetime.fromisoformat(row_input["reference_dt"]),
            "replay_steps": [
                ReplayStep.model_validate(step) for step in row_input["replay_steps"]
            ],
        },
        expected_output=[
            Todo.model_validate(todo) for todo in raw_row["expected_output"]
        ],
        metadata={
            "dataset": dataset_name,
            "case_type": "incremental_replay",
            "source_fixture": raw_row.get("metadata", {}).get(
                "source_fixture",
                raw_row["id"],
            ),
        },
    )
