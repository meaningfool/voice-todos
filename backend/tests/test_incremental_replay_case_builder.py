import json
from datetime import UTC, datetime
from inspect import signature
from pathlib import Path

from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD
from app.models import Todo
from app.ws import TOKEN_THRESHOLD
from evals.incremental_extraction_quality.models import ReplayCase, ReplayStep
from evals.incremental_extraction_quality.provider_trace_adapters.soniox import (
    build_soniox_checkpoint_candidates,
)
from evals.incremental_extraction_quality.replay_case_builder import (
    build_replay_case_from_fixture,
    build_replay_dataset_payload,
    build_replay_steps,
    write_replay_dataset_payload,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DATASET_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "evals"
    / "todo_extraction_replay_seed_expected.json"
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


def test_replay_seed_and_live_paths_share_the_same_token_threshold():
    assert EXTRACTION_TOKEN_THRESHOLD == TOKEN_THRESHOLD
    assert (
        signature(build_soniox_checkpoint_candidates).parameters[
            "token_threshold"
        ].default
        == EXTRACTION_TOKEN_THRESHOLD
    )
    assert (
        signature(build_replay_case_from_fixture).parameters[
            "token_threshold"
        ].default
        == EXTRACTION_TOKEN_THRESHOLD
    )
    assert (
        signature(build_replay_dataset_payload).parameters[
            "token_threshold"
        ].default
        == EXTRACTION_TOKEN_THRESHOLD
    )
    assert (
        signature(write_replay_dataset_payload).parameters[
            "token_threshold"
        ].default
        == EXTRACTION_TOKEN_THRESHOLD
    )


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
                transcript=(
                    "I need to buy milk. Actually, mais exact oud milk "
                    "from the organic store."
                ),
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


def test_replay_case_builder_writes_canonical_dataset_content(tmp_path: Path):
    output_path = tmp_path / "todo_extraction_replay_v1.json"

    write_replay_dataset_payload(
        fixture_names=[
            "call-mom-memo-supplier",
            "refine-todo",
            "while-speaking-two-todos",
            "stop-final-sweep-single-todo",
        ],
        fixtures_root=FIXTURES_DIR,
        output_path=output_path,
    )

    assert output_path.read_text(encoding="utf-8") == DATASET_PATH.read_text(
        encoding="utf-8"
    )


def test_replay_case_builder_rejects_mismatched_result_transcript(
    tmp_path: Path,
):
    fixture_name = "refine-todo"
    source_dir = FIXTURES_DIR / fixture_name
    fixture_dir = tmp_path / fixture_name
    fixture_dir.mkdir()
    fixture_dir.joinpath("soniox.jsonl").write_text(
        source_dir.joinpath("soniox.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    fixture_dir.joinpath("result.json").write_text(
        json.dumps(
            {
                "transcript": "This transcript does not match the trace.",
                "todos": [
                    {
                        "text": "Buy oat milk from the organic store",
                        "category": "Shopping",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        build_replay_case_from_fixture(
            fixture_name=fixture_name,
            fixtures_root=tmp_path,
        )
    except ValueError as exc:
        assert str(exc) == (
            "Fixture refine-todo terminal transcript does not match result.json "
            "transcript"
        )
    else:
        raise AssertionError("Expected build_replay_case_from_fixture() to fail")
