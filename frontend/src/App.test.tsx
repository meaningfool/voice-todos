import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockUseTranscript = vi.fn();

vi.mock("./hooks/useTranscript", () => ({
  useTranscript: () => mockUseTranscript(),
}));

import App from "./App";

describe("App", () => {
  const baseHook = {
    status: "idle" as const,
    finalText: "",
    interimText: "",
    todos: [],
    micRecordingUrl: null,
    warningMessage: null,
    start: vi.fn(),
    stop: vi.fn(),
  };

  it("renders the phone-shell empty state on first load", () => {
    mockUseTranscript.mockReturnValue(baseHook);

    const { container } = render(<App />);

    expect(screen.getByText("Voice Todos")).toBeInTheDocument();
    expect(screen.getByText("Get started")).toBeInTheDocument();
    expect(
      screen.getByText("Your voice will be turned into tasks in real time.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Session" })).toBeInTheDocument();
    expect(container.querySelectorAll(".lucide-mic")).toHaveLength(2);
    expect(screen.queryByTestId("app-icon-mic")).not.toBeInTheDocument();
  });

  it("keeps todos visible while recording", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [{ text: "Draft agenda" }],
    });

    render(<App />);

    expect(screen.getByText("Draft agenda")).toBeInTheDocument();
    expect(screen.getByText("Listening now...")).toBeInTheDocument();
  });

  it("shows three skeleton cards while recording with no todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [],
    });

    render(<App />);

    expect(screen.getAllByTestId("todo-skeleton-card")).toHaveLength(3);
  });

  it("shows two skeleton cards while recording with one todo", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [{ text: "Draft agenda" }],
    });

    render(<App />);

    expect(screen.getAllByTestId("todo-skeleton-card")).toHaveLength(2);
  });

  it("shows one skeleton card while recording with two todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [{ text: "Draft agenda" }, { text: "Book room" }],
    });

    render(<App />);

    expect(screen.getAllByTestId("todo-skeleton-card")).toHaveLength(1);
  });

  it("shows one skeleton card while recording with three todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "recording",
      todos: [
        { text: "Draft agenda" },
        { text: "Book room" },
        { text: "Share notes" },
      ],
    });

    render(<App />);

    expect(screen.getAllByTestId("todo-skeleton-card")).toHaveLength(1);
  });

  it("shows one skeleton card while extracting with existing todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [{ text: "Review budget" }],
    });

    render(<App />);

    expect(screen.getAllByTestId("todo-skeleton-card")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Extracting..." })).toBeDisabled();
  });

  it("shows a post-session no-todos state after a finished recording", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      finalText: "Remember to think about the roadmap",
    });

    render(<App />);

    expect(screen.getByText("No todos found in this recording.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("todo-skeleton-card")).toHaveLength(0);
  });

  it("renders session details when a recording URL exists", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      finalText: "Call Marie tomorrow",
      micRecordingUrl: "blob:recording",
    });

    render(<App />);

    expect(screen.getByText("Session details")).toBeInTheDocument();
    expect(screen.getByText("Call Marie tomorrow")).toBeInTheDocument();
    expect(document.querySelector("audio")).not.toBeNull();
    expect(
      screen.getByRole("link", { name: "Download raw recording" })
    ).toHaveAttribute("href", "blob:recording");
  });

  it("renders warning messaging inside the main feed", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      warningMessage: "Timed out waiting for the final transcript.",
    });

    render(<App />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Timed out waiting for the final transcript."
    );
  });

  it("suppresses the no-todos result when a warning is present", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      finalText: "Call Marie tomorrow",
      micRecordingUrl: "blob:recording",
      warningMessage: "Timed out waiting for the final transcript.",
    });

    render(<App />);

    expect(
      screen.getByText("Timed out waiting for the final transcript.")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No todos found in this recording.")
    ).not.toBeInTheDocument();
  });

  it("keeps todos visible during extracting when todos already exist", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [{ text: "Review budget" }],
    });

    const { container } = render(<App />);

    expect(screen.getByText("Review budget")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-testid='todo-skeleton-card']")).toHaveLength(1);
  });
});
