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

    render(<App />);

    expect(screen.getByText("Voice-Todos")).toBeInTheDocument();
    expect(screen.getByText("Start speaking...")).toBeInTheDocument();
    expect(
      screen.getByText("Your voice will be turned into tasks in real time.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Session" })).toBeInTheDocument();
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

  it("shows skeleton cards only when extracting without todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [],
    });

    const { container } = render(<App />);

    expect(container.querySelectorAll("[class*='animate-pulse']")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Extracting..." })).toBeDisabled();
  });

  it("shows a post-session no-todos state after a finished recording", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      finalText: "Remember to think about the roadmap",
    });

    render(<App />);

    expect(screen.getByText("No todos found in this recording.")).toBeInTheDocument();
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
  });

  it("renders warning messaging inside the main feed", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      warningMessage: "Timed out waiting for the final transcript.",
    });

    render(<App />);

    expect(
      screen.getByText("Timed out waiting for the final transcript.")
    ).toBeInTheDocument();
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
    expect(container.querySelector("[class*='animate-pulse']")).toBeNull();
  });
});
