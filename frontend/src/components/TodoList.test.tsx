import { render, screen } from "@testing-library/react";
import { TodoList } from "./TodoList";
import type { Todo } from "../types";

describe("TodoList", () => {
  it("renders nothing when todos array is empty", () => {
    const { container } = render(<TodoList todos={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders count header with correct number", () => {
    const todos: Todo[] = [
      { text: "Task A" },
      { text: "Task B" },
    ];
    render(<TodoList todos={todos} />);
    expect(screen.getByText("Extracted Todos (2)")).toBeInTheDocument();
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
});
