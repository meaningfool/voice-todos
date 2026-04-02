from datetime import UTC, datetime

from app.models import Todo
from evals.incremental_extraction_quality.dataset_loader import (
    DATASET_PATH,
    load_incremental_replay_dataset,
)
from evals.incremental_extraction_quality.models import ReplayStep


def test_load_incremental_replay_dataset_returns_expected_cases():
    dataset = load_incremental_replay_dataset()

    assert dataset.name == "todo_extraction_replay_v1"
    assert DATASET_PATH.name == "todo_extraction_replay_v1.json"
    assert [case.name for case in dataset.cases] == [
        "call-mom-memo-supplier",
        "refine-todo",
        "while-speaking-two-todos",
        "stop-final-sweep-single-todo",
    ]

    refine_case = next(case for case in dataset.cases if case.name == "refine-todo")
    assert refine_case.inputs["reference_dt"] == datetime(
        2026,
        3,
        24,
        9,
        30,
        tzinfo=UTC,
    )
    assert refine_case.inputs["replay_steps"] == [
        ReplayStep(step_index=1, transcript="I need to buy milk."),
        ReplayStep(
            step_index=2,
            transcript=(
                "I need to buy milk. Actually, mais exact oud milk "
                "from the organic store."
            ),
        ),
    ]
    assert refine_case.expected_output == [
        Todo(
            text="Buy oat milk from the organic store",
            category="Shopping",
        )
    ]
    assert refine_case.metadata == {
        "dataset": "todo_extraction_replay_v1",
        "case_type": "incremental_replay",
        "source_fixture": "refine-todo",
    }

    stop_case = next(
        case for case in dataset.cases if case.name == "stop-final-sweep-single-todo"
    )
    assert all(
        isinstance(step, ReplayStep) for step in stop_case.inputs["replay_steps"]
    )
    assert all(isinstance(todo, Todo) for todo in stop_case.expected_output)
    assert stop_case.expected_output == [
        Todo(
            text="Send the signed contract to Priya",
            category="Legal",
            due_date=datetime(2026, 3, 24, tzinfo=UTC).date(),
            assign_to="Priya",
        )
    ]
