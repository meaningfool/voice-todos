from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models import Todo


class ReplayStep(BaseModel):
    step_index: int
    transcript: str


class ReplayCase(BaseModel):
    name: str
    source_fixture: str
    reference_dt: datetime
    replay_steps: list[ReplayStep]
    expected_final_todos: list[Todo]


class ReplayStepResult(BaseModel):
    step_index: int
    transcript: str
    todos: list[Todo]


class ReplayRunResult(BaseModel):
    final_todos: list[Todo]
    step_results: list[ReplayStepResult]
