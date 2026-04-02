from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset

from app.models import Todo
from evals.incremental_extraction_quality.models import ReplayStep

DATASET_PATH = Path(__file__).with_name("todo_extraction_replay_v1.json")


def load_incremental_replay_dataset(
    path: Path | None = None,
) -> Dataset[dict[str, Any], list[Todo], dict[str, str]]:
    dataset_path = path or DATASET_PATH
    payload = json.loads(dataset_path.read_text())

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
