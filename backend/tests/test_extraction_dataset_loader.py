import json
from datetime import UTC, datetime
from pathlib import Path

from app.models import Todo
from evals.extraction_quality.dataset_loader import (
    DATASET_PATH,
    load_extraction_quality_dataset,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "evals"


def test_load_extraction_quality_dataset_returns_expected_cases():
    dataset = load_extraction_quality_dataset()
    payload = json.loads(DATASET_PATH.read_text())

    assert dataset.name == "todo_extraction_v1"
    assert DATASET_PATH.name == "todo_extraction_bench_v1.json"
    assert [case.name for case in dataset.cases] == [
        raw_row["id"] for raw_row in payload["rows"]
    ]


def test_load_extraction_quality_dataset_normalizes_lock_shaped_payloads():
    dataset = load_extraction_quality_dataset(
        FIXTURES_DIR / "todo_extraction_lock_smoke.json"
    )

    assert dataset.name == "todo_extraction_lock_smoke_v1"
    assert [case.name for case in dataset.cases] == ["buy-milk-locked"]

    locked_case = dataset.cases[0]
    assert locked_case.inputs == {
        "transcript": "Buy milk on the way home.",
        "reference_dt": datetime(2026, 4, 8, 9, 30, tzinfo=UTC),
        "previous_todos": None,
    }
    assert locked_case.expected_output == [Todo(text="Buy milk on the way home")]
    assert locked_case.metadata == {
        "dataset": "todo_extraction_lock_smoke_v1",
        "case_type": "extraction",
        "source_fixture": "smoke-buy-milk-locked",
    }


def test_load_extraction_quality_dataset_still_supports_legacy_case_payloads():
    dataset = load_extraction_quality_dataset(
        FIXTURES_DIR / "todo_extraction_smoke.json"
    )

    assert dataset.name == "todo_extraction_smoke_v1"
    assert [case.name for case in dataset.cases] == ["buy-milk"]
    assert dataset.cases[0].metadata == {
        "dataset": "todo_extraction_smoke_v1",
        "case_type": "extraction",
        "source_fixture": "smoke-buy-milk",
    }
