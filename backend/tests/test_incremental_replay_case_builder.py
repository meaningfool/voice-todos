import json
from datetime import UTC, datetime
from pathlib import Path

from app.models import Todo
from evals.incremental_extraction_quality.models import ReplayCase, ReplayStep
from evals.incremental_extraction_quality.replay_case_builder import (
    build_replay_case_from_fixture,
    build_replay_dataset_payload,
    build_replay_steps,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DATASET_PATH = (
    Path(__file__).parents[1]
    / "evals"
    / "incremental_extraction_quality"
    / "todo_extraction_replay_v1.json"
)


def test_replay_case_builder_returns_ordered_transcript_snapshots():
    replay_steps = build_replay_steps(
        [
            "Buy milk",
            "Buy milk",
            "Buy milk and eggs",
            "Buy milk and eggs",
        ],
        final_transcript="Buy milk and eggs",
    )

    assert replay_steps == [
        "Buy milk",
        "Buy milk and eggs",
    ]


def test_replay_case_builder_appends_final_transcript_once():
    replay_steps = build_replay_steps(
        [
            "Buy milk",
            "Buy milk",
        ],
        final_transcript="Buy milk and eggs",
    )

    assert replay_steps == [
        "Buy milk",
        "Buy milk and eggs",
    ]


def test_replay_case_builder_compiles_fixture_into_replay_case():
    replay_case = build_replay_case_from_fixture(
        fixture_name="refine-todo",
        fixtures_root=FIXTURES_DIR,
    )

    assert replay_case == ReplayCase(
        name="refine-todo",
        source_fixture="refine-todo",
        reference_dt=datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
        replay_steps=[
            ReplayStep(step_index=1, transcript="I need to buy milk."),
            ReplayStep(
                step_index=2,
                transcript="I need to buy milk. Actually, mais exact oud milk from the organic store.",
            ),
        ],
        expected_final_todos=[
            Todo(
                text="Buy oat milk from the organic store",
                category="Shopping",
            )
        ],
    )


def test_replay_case_builder_compiles_seed_fixtures_into_canonical_dataset_payload():
    payload = build_replay_dataset_payload(
        fixture_names=[
            "call-mom-memo-supplier",
            "refine-todo",
            "while-speaking-two-todos",
            "stop-final-sweep-single-todo",
        ],
        fixtures_root=FIXTURES_DIR,
    )

    assert payload == json.loads(DATASET_PATH.read_text())
