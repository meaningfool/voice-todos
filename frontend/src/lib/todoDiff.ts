import type { Todo } from "../types";

const todoFields: Array<keyof Todo> = [
  "text",
  "priority",
  "category",
  "dueDate",
  "assignTo",
  "notification",
];

export function getChangedTodoIndices(previous: Todo[], next: Todo[]) {
  const changedIndices: number[] = [];

  for (let index = 0; index < next.length; index += 1) {
    const previousTodo = previous[index];
    const nextTodo = next[index];

    if (!previousTodo) {
      changedIndices.push(index);
      continue;
    }

    const hasChanged = todoFields.some(
      (field) => !Object.is(previousTodo[field], nextTodo[field]),
    );

    if (hasChanged) {
      changedIndices.push(index);
    }
  }

  return changedIndices;
}
