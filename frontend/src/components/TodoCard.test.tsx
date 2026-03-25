import { render, screen } from "@testing-library/react";
import { TodoCard } from "./TodoCard";
import type { Todo } from "../types";

describe("TodoCard", () => {
  it("renders todo text", () => {
    const todo: Todo = { text: "Buy groceries" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByTestId("todo-card-0")).toBeInTheDocument();
  });

  it("renders due date chip with calendar icon when present", () => {
    const todo: Todo = { text: "Call dentist", dueDate: "2026-03-27" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("2026-03-27")).toBeInTheDocument();
    expect(screen.getByTestId("app-icon-calendar")).toBeInTheDocument();
  });

  it("renders priority chip when present", () => {
    const todo: Todo = { text: "Fix bug", priority: "high" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders category chip with tag icon when present", () => {
    const todo: Todo = { text: "Review PR", category: "work" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("work")).toBeInTheDocument();
    expect(screen.getByTestId("app-icon-tag")).toBeInTheDocument();
  });

  it("renders assignTo chip with user icon when present", () => {
    const todo: Todo = { text: "Review budget", assignTo: "Marie" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Marie")).toBeInTheDocument();
    expect(screen.getByTestId("app-icon-user")).toBeInTheDocument();
  });

  it("renders notification chip when present", () => {
    const todo: Todo = { text: "Meeting", notification: "2026-03-27T09:00" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("2026-03-27T09:00")).toBeInTheDocument();
  });

  it("does not render optional badges when fields are absent", () => {
    const todo: Todo = { text: "Simple task" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Simple task")).toBeInTheDocument();
    expect(screen.queryByTestId("app-icon-calendar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("app-icon-tag")).not.toBeInTheDocument();
    expect(screen.queryByTestId("app-icon-user")).not.toBeInTheDocument();
  });
});
