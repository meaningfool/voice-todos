from pathlib import Path

from evals.storage import load_dataset_definition

from evals.extraction_quality.dataset_loader import load_extraction_quality_dataset
from evals.incremental_extraction_quality.dataset_loader import (
    load_incremental_replay_dataset,
)


def test_extraction_dataset_matches_legacy_case_ids():
    legacy = load_extraction_quality_dataset()
    current = load_dataset_definition(
        Path("../evals/datasets/extraction/todo_extraction_v1.json")
    )

    assert [row.id for row in current.rows] == [case.name for case in legacy.cases]


def test_replay_dataset_matches_legacy_case_ids():
    legacy = load_incremental_replay_dataset()
    current = load_dataset_definition(
        Path("../evals/datasets/replay/todo_extraction_replay_v1.json")
    )

    assert [row.id for row in current.rows] == [case.name for case in legacy.cases]
