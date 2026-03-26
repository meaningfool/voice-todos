import { fireEvent, render, screen } from "@testing-library/react";
import { RecordButton } from "./RecordButton";

describe("RecordButton", () => {
  it("renders Start Session with mic icon when idle", () => {
    const onStart = vi.fn();
    render(<RecordButton status="idle" onStart={onStart} onStop={() => {}} />);

    const button = screen.getByRole("button", { name: "Start Session" });
    expect(button).toBeEnabled();
    expect(button.querySelector(".lucide-mic")).not.toBeNull();
    expect(screen.queryByTestId("app-icon-mic")).not.toBeInTheDocument();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("renders Connecting... as disabled while connecting", () => {
    const onStart = vi.fn();
    const onStop = vi.fn();
    render(<RecordButton status="connecting" onStart={onStart} onStop={onStop} />);

    const button = screen.getByRole("button", { name: "Connecting..." });
    expect(button).toBeDisabled();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(onStart).not.toHaveBeenCalled();
    expect(onStop).not.toHaveBeenCalled();
  });

  it("renders Finish Session and listening UI while recording", () => {
    const onStop = vi.fn();
    render(<RecordButton status="recording" onStart={() => {}} onStop={onStop} />);

    const button = screen.getByRole("button", { name: "Finish Session" });
    expect(button).toBeEnabled();
    expect(screen.getByText("Listening now...")).toBeInTheDocument();
    expect(screen.getAllByTestId("wave-bar")).toHaveLength(9);
    expect(screen.queryByTestId("app-icon-mic")).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("renders Extracting... as disabled while extracting", () => {
    const onStart = vi.fn();
    const onStop = vi.fn();
    render(<RecordButton status="extracting" onStart={onStart} onStop={onStop} />);

    const button = screen.getByRole("button", { name: "Extracting..." });
    expect(button).toBeDisabled();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(onStart).not.toHaveBeenCalled();
    expect(onStop).not.toHaveBeenCalled();
  });
});
