import { describe, expect, it } from "vitest";
import type { Todo } from "../types";
import { getChangedTodoIndices } from "./todoDiff";

describe("getChangedTodoIndices", () => {
  it("returns changed indices when a todo field changes", () => {
    const previous: Todo[] = [
      { text: "Buy groceries", priority: "low" },
      { text: "Call dentist", dueDate: "2026-03-27" },
    ];
    const next: Todo[] = [
      { text: "Buy groceries", priority: "low" },
      { text: "Call dentist", dueDate: "2026-03-28" },
    ];

    expect(getChangedTodoIndices(previous, next)).toEqual([1]);
  });

  it("returns new indices when todos are added", () => {
    const previous: Todo[] = [{ text: "Buy groceries" }];
    const next: Todo[] = [{ text: "Buy groceries" }, { text: "Call dentist" }];

    expect(getChangedTodoIndices(previous, next)).toEqual([1]);
  });

  it("returns every index when the order changes", () => {
    const previous: Todo[] = [{ text: "A" }, { text: "B" }];
    const next: Todo[] = [{ text: "B" }, { text: "A" }];

    expect(getChangedTodoIndices(previous, next)).toEqual([0, 1]);
  });
});
