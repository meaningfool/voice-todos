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
    warningMessage: null,
    start: vi.fn(),
    stop: vi.fn(),
  };

  it("renders TodoSkeleton when status is extracting and no todos exist", () => {
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

  it("renders TodoList while recording when todos exist", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [{ text: "Draft agenda" }],
    });
    render(<App />);
    expect(screen.getByText("Draft agenda")).toBeInTheDocument();
    expect(screen.getByText("Extracted Todos (1)")).toBeInTheDocument();
  });

  it("keeps TodoList visible during extracting when todos already exist", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [{ text: "Stale todo" }],
    });
    const { container } = render(<App />);
    expect(screen.getByText("Stale todo")).toBeInTheDocument();
    expect(screen.getByText("Extracted Todos (1)")).toBeInTheDocument();
    expect(container.querySelector("[class*='animate-pulse']")).toBeNull();
  });

  it("shows transcript and 'no todos' message when idle with transcript but no todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "idle",
      finalText: "Okay so let's get started on this exercise",
      todos: [],
    });
    render(<App />);
    // Transcript must stay visible
    expect(
      screen.getByText("Okay so let's get started on this exercise")
    ).toBeInTheDocument();
    // Empty state message shown
    expect(
      screen.getByText("No todos found in this recording.")
    ).toBeInTheDocument();
  });

  it("renders a warning banner when the hook exposes one", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      warningMessage: "Timed out waiting for the final transcript.",
    });
    render(<App />);
    expect(
      screen.getByText("Timed out waiting for the final transcript.")
    ).toBeInTheDocument();
  });
});
