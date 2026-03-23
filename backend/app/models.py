from typing import Literal

from pydantic import BaseModel


class Todo(BaseModel):
    text: str
    priority: Literal["high", "medium", "low"] | None = None
    category: str | None = None
    due_date: str | None = None
    notification: str | None = None
    assign_to: str | None = None


class ExtractionResult(BaseModel):
    todos: list[Todo]
