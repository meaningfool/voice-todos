import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock useTranscript to control state
const mockUseTranscript = vi.fn();
vi.mock("./hooks/useTranscript", () => ({
  useTranscript: () => mockUseTranscript(),
}));

// Must import App after the mock is set up
import App from "./App";

describe("App", () => {
  const baseHook = {
    status: "idle" as const,
    finalText: "",
    interimText: "",
    todos: [],
    start: vi.fn(),
    stop: vi.fn(),
  };

  it("renders TodoSkeleton when status is extracting", () => {
    mockUseTranscript.mockReturnValue({ ...baseHook, status: "extracting" });
    const { container } = render(<App />);
    expect(container.querySelector("[class*='animate-pulse']")).not.toBeNull();
  });

  it("renders TodoList when idle with todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "idle",
      todos: [{ text: "Buy groceries" }, { text: "Call dentist" }],
    });
    render(<App />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByText("Call dentist")).toBeInTheDocument();
    expect(screen.getByText("Extracted Todos (2)")).toBeInTheDocument();
  });

  it("does not render TodoList when idle with no todos", () => {
    mockUseTranscript.mockReturnValue({ ...baseHook, status: "idle", todos: [] });
    render(<App />);
    expect(screen.queryByText(/Extracted Todos/)).not.toBeInTheDocument();
  });

  it("does not render TodoList while extracting even if todos exist", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [{ text: "Stale todo" }],
    });
    render(<App />);
    // Should show skeleton, not the todo list
    expect(screen.queryByText("Extracted Todos")).not.toBeInTheDocument();
  });
});
