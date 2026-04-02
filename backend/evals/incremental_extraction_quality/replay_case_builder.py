from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models import Todo
from evals.incremental_extraction_quality.models import ReplayCase, ReplayStep
from evals.incremental_extraction_quality.provider_trace_adapters.soniox import (
    build_soniox_checkpoint_candidates,
)

DEFAULT_REFERENCE_DT = datetime(2026, 3, 24, 9, 30, tzinfo=UTC)
DEFAULT_DATASET_NAME = "todo_extraction_replay_v1"

def build_replay_steps(
    checkpoint_candidates: list[str],
    *,
    final_transcript: str,
) -> list[str]:
    replay_steps: list[str] = []

    for snapshot in checkpoint_candidates:
        if not snapshot.strip():
            continue
        if replay_steps and replay_steps[-1] == snapshot:
            continue
        replay_steps.append(snapshot)

    if final_transcript.strip() and (
        not replay_steps or replay_steps[-1] != final_transcript
    ):
        replay_steps.append(final_transcript)

    return replay_steps


def build_replay_case_from_fixture(
    *,
    fixture_name: str,
    fixtures_root: Path,
    reference_dt: datetime = DEFAULT_REFERENCE_DT,
    token_threshold: int = 15,
) -> ReplayCase:
    fixture_dir = fixtures_root / fixture_name
    messages = _load_jsonl(fixture_dir / "soniox.jsonl")
    result = json.loads((fixture_dir / "result.json").read_text())

    replay_transcripts = build_replay_steps(
        build_soniox_checkpoint_candidates(messages, token_threshold=token_threshold),
        final_transcript=result["transcript"],
    )

    return ReplayCase(
        name=fixture_name,
        source_fixture=fixture_name,
        reference_dt=reference_dt,
        replay_steps=[
            ReplayStep(step_index=index, transcript=transcript)
            for index, transcript in enumerate(replay_transcripts, start=1)
        ],
        expected_final_todos=[
            Todo.model_validate(todo) for todo in result.get("todos", [])
        ],
    )


def build_replay_dataset_payload(
    *,
    fixture_names: list[str],
    fixtures_root: Path,
    dataset_name: str = DEFAULT_DATASET_NAME,
    reference_dt: datetime = DEFAULT_REFERENCE_DT,
    token_threshold: int = 15,
) -> dict[str, Any]:
    cases = [
        build_replay_case_from_fixture(
            fixture_name=fixture_name,
            fixtures_root=fixtures_root,
            reference_dt=reference_dt,
            token_threshold=token_threshold,
        )
        for fixture_name in fixture_names
    ]
    return {
        "dataset": dataset_name,
        "cases": [_serialize_replay_case(case) for case in cases],
    }


def write_replay_dataset_payload(
    *,
    fixture_names: list[str],
    fixtures_root: Path,
    output_path: Path,
    dataset_name: str = DEFAULT_DATASET_NAME,
    reference_dt: datetime = DEFAULT_REFERENCE_DT,
    token_threshold: int = 15,
) -> None:
    payload = build_replay_dataset_payload(
        fixture_names=fixture_names,
        fixtures_root=fixtures_root,
        dataset_name=dataset_name,
        reference_dt=reference_dt,
        token_threshold=token_threshold,
    )
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            messages.append(json.loads(line))
    return messages


def _serialize_replay_case(case: ReplayCase) -> dict[str, Any]:
    return {
        "name": case.name,
        "source_fixture": case.source_fixture,
        "reference_dt": case.reference_dt.isoformat(),
        "replay_steps": [
            step.model_dump(mode="json") for step in case.replay_steps
        ],
        "expected_final_todos": [
            todo.model_dump(exclude_none=True, mode="json")
            for todo in case.expected_final_todos
        ],
    }
