import json
from datetime import UTC, datetime
from pathlib import Path

from app.models import Todo
from evals.incremental_extraction_quality.dataset_loader import (
    DATASET_PATH,
    load_incremental_replay_dataset,
)
from evals.incremental_extraction_quality.models import ReplayStep

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "evals"


def test_load_incremental_replay_dataset_returns_expected_cases():
    dataset = load_incremental_replay_dataset()
    payload = json.loads(DATASET_PATH.read_text())

    assert dataset.name == "todo_extraction_replay_v1"
    assert DATASET_PATH.name == "todo_replay_bench_v1.json"
    assert [case.name for case in dataset.cases] == [
        raw_row["id"] for raw_row in payload["rows"]
    ]


def test_load_incremental_replay_dataset_normalizes_lock_shaped_payloads():
    dataset = load_incremental_replay_dataset(
        FIXTURES_DIR / "todo_replay_lock_smoke.json"
    )

    assert dataset.name == "todo_replay_lock_smoke_v1"
    assert [case.name for case in dataset.cases] == ["buy-milk-replay-locked"]

    replay_case = dataset.cases[0]
    assert replay_case.inputs["reference_dt"] == datetime(
        2026,
        4,
        8,
        9,
        30,
        tzinfo=UTC,
    )
    assert replay_case.inputs["replay_steps"] == [
        ReplayStep(step_index=1, transcript="Buy milk."),
        ReplayStep(
            step_index=2,
            transcript="Buy milk on the way home.",
        ),
    ]
    assert replay_case.expected_output == [Todo(text="Buy milk on the way home")]
    assert replay_case.metadata == {
        "dataset": "todo_replay_lock_smoke_v1",
        "case_type": "incremental_replay",
        "source_fixture": "smoke-buy-milk-replay-locked",
    }


def test_load_incremental_replay_dataset_still_supports_legacy_case_payloads():
    dataset = load_incremental_replay_dataset(
        FIXTURES_DIR / "todo_extraction_replay_smoke.json"
    )

    assert dataset.name == "todo_extraction_replay_smoke_v1"
    assert [case.name for case in dataset.cases] == ["buy-milk-incremental"]

    replay_case = dataset.cases[0]
    assert replay_case.inputs["reference_dt"] == datetime(
        2026,
        4,
        8,
        9,
        30,
        tzinfo=UTC,
    )
    assert replay_case.inputs["replay_steps"] == [
        ReplayStep(step_index=1, transcript="Buy milk."),
        ReplayStep(
            step_index=2,
            transcript="Buy milk on the way home.",
        ),
    ]
    assert replay_case.expected_output == [Todo(text="Buy milk on the way home")]
    assert replay_case.metadata == {
        "dataset": "todo_extraction_replay_smoke_v1",
        "case_type": "incremental_replay",
        "source_fixture": "smoke-buy-milk-incremental",
    }
