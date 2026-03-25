import { render, screen, waitFor } from "@testing-library/react";
import { TodoList } from "./TodoList";
import type { Todo } from "../types";

describe("TodoList", () => {
  it("renders nothing when todos array is empty", () => {
    const { container } = render(<TodoList todos={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("does not render the extracted todos heading", () => {
    const todos: Todo[] = [
      { text: "Task A" },
      { text: "Task B" },
    ];
    render(<TodoList todos={todos} />);
    expect(screen.queryByText("Extracted Todos (2)")).not.toBeInTheDocument();
  });

  it("renders all todo items", () => {
    const todos: Todo[] = [
      { text: "Buy groceries" },
      { text: "Call dentist", priority: "high" },
      { text: "Review PR", assignTo: "Marie" },
    ];
    render(<TodoList todos={todos} />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByText("Call dentist")).toBeInTheDocument();
    expect(screen.getByText("Review PR")).toBeInTheDocument();
  });

  it("highlights todos from the first non-empty render", async () => {
    const todos: Todo[] = [{ text: "Buy groceries" }, { text: "Call dentist" }];

    render(<TodoList todos={todos} />);

    await waitFor(() => {
      expect(screen.getByTestId("todo-card-0")).toHaveAttribute(
        "data-highlighted",
        "true",
      );
      expect(screen.getByTestId("todo-card-1")).toHaveAttribute(
        "data-highlighted",
        "true",
      );
    });
  });

  it("highlights changed todos after rerender", () => {
    const previousTodos: Todo[] = [
      { text: "Buy groceries" },
      { text: "Call dentist", dueDate: "2026-03-27" },
    ];
    const nextTodos: Todo[] = [
      { text: "Buy groceries" },
      { text: "Call dentist", dueDate: "2026-03-28" },
    ];

    const { rerender } = render(<TodoList todos={previousTodos} />);
    rerender(<TodoList todos={nextTodos} />);

    expect(screen.getByTestId("todo-card-1")).toHaveAttribute(
      "data-highlighted",
      "true",
    );
    expect(screen.getByTestId("todo-card-0")).toHaveAttribute(
      "data-highlighted",
      "false",
    );
  });
});
