import json
from datetime import UTC, datetime

from app.models import Todo
from evals.extraction_quality.dataset_loader import (
    DATASET_PATH,
    load_extraction_quality_dataset,
)


def test_load_extraction_quality_dataset_returns_expected_cases():
    dataset = load_extraction_quality_dataset()

    assert dataset.name == "todo_extraction_v1"
    assert DATASET_PATH.name == "todo_extraction_v1.json"
    assert [case.name for case in dataset.cases] == [
        "call-mom-memo-supplier",
        "continuous-speech",
        "finding-out-if-you",
        "refine-todo",
        "stop-final-sweep-single-todo",
        "stop-the-button",
        "text-is-captured",
        "to-build-todos",
        "while-speaking-two-todos",
    ]


def test_load_extraction_quality_dataset_normalizes_case_inputs_and_todos():
    dataset = load_extraction_quality_dataset()

    stop_case = next(case for case in dataset.cases if case.name == "stop-the-button")
    assert stop_case.inputs == {
        "transcript": "Stop",
        "reference_dt": datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
        "previous_todos": None,
    }
    assert stop_case.expected_output == []
    assert stop_case.metadata == {
        "dataset": "todo_extraction_v1",
        "case_type": "extraction",
        "source_fixture": "stop-the-button",
    }

    continuous_case = next(
        case for case in dataset.cases if case.name == "continuous-speech"
    )
    assert all(isinstance(todo, Todo) for todo in continuous_case.expected_output)
    assert continuous_case.expected_output[0].due_date.isoformat() == "2026-03-25"


def test_load_extraction_quality_dataset_preserves_stable_row_ids():
    dataset = load_extraction_quality_dataset()
    payload = json.loads(DATASET_PATH.read_text())

    assert [case.name for case in dataset.cases] == [
        raw_case["name"] for raw_case in payload["cases"]
    ]
