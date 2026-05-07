from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Priority = Literal["high", "medium", "low"]


@dataclass(eq=True)
class Todo:
    text: str
    priority: Priority | None = None
    category: str | None = None
    due_date: date | str | None = None
    notification: datetime | str | None = None
    assign_to: str | None = None

    def __post_init__(self) -> None:
        if self.priority not in {None, "high", "medium", "low"}:
            raise ValueError(f"Invalid priority: {self.priority!r}")
        if isinstance(self.due_date, str):
            self.due_date = date.fromisoformat(self.due_date)
        if isinstance(self.notification, str):
            self.notification = datetime.fromisoformat(self.notification)

    def model_dump(
        self,
        *,
        exclude_none: bool = False,
        mode: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "text": self.text,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date,
            "notification": self.notification,
            "assign_to": self.assign_to,
        }
        if exclude_none:
            payload = {
                key: value for key, value in payload.items() if value is not None
            }
        if mode == "json":
            if "due_date" in payload and isinstance(payload["due_date"], date):
                payload["due_date"] = payload["due_date"].isoformat()
            if "notification" in payload and isinstance(
                payload["notification"], datetime
            ):
                payload["notification"] = payload["notification"].isoformat()
        return payload


@dataclass(eq=True)
class ExtractionResult:
    todos: list[Todo] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.todos = [
            item if isinstance(item, Todo) else Todo(**item)
            for item in self.todos
        ]
