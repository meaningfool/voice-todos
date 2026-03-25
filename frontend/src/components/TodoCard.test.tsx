import { render, screen } from "@testing-library/react";
import { TodoCard } from "./TodoCard";
import type { Todo } from "../types";

describe("TodoCard", () => {
  it("renders todo text", () => {
    const todo: Todo = { text: "Buy groceries" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
  });

  it("renders due date badge when present", () => {
    const todo: Todo = { text: "Call dentist", dueDate: "2026-03-27" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("2026-03-27")).toBeInTheDocument();
  });

  it("renders priority badge when present", () => {
    const todo: Todo = { text: "Fix bug", priority: "high" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders category badge when present", () => {
    const todo: Todo = { text: "Review PR", category: "work" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("work")).toBeInTheDocument();
  });

  it("renders assignTo badge when present", () => {
    const todo: Todo = { text: "Review budget", assignTo: "Marie" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Marie")).toBeInTheDocument();
  });

  it("renders notification badge when present", () => {
    const todo: Todo = { text: "Meeting", notification: "2026-03-27T09:00" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("2026-03-27T09:00")).toBeInTheDocument();
  });

  it("does not render optional badges when fields are absent", () => {
    const todo: Todo = { text: "Simple task" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Simple task")).toBeInTheDocument();
    // No badges should be rendered
    expect(screen.queryByText(/📅/)).not.toBeInTheDocument();
    expect(screen.queryByText(/⚡/)).not.toBeInTheDocument();
    expect(screen.queryByText(/📁/)).not.toBeInTheDocument();
    expect(screen.queryByText(/👤/)).not.toBeInTheDocument();
    expect(screen.queryByText(/🔔/)).not.toBeInTheDocument();
  });
});
