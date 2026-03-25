import { render, screen } from "@testing-library/react";
import { RecordButton } from "./RecordButton";

describe("RecordButton", () => {
  it("renders Start Session with mic icon when idle", () => {
    render(<RecordButton status="idle" onStart={() => {}} onStop={() => {}} />);

    const button = screen.getByRole("button", { name: "Start Session" });
    expect(button).toBeEnabled();
    expect(screen.getByTestId("app-icon-mic")).toBeInTheDocument();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
  });

  it("renders Connecting... as disabled while connecting", () => {
    render(<RecordButton status="connecting" onStart={() => {}} onStop={() => {}} />);

    const button = screen.getByRole("button", { name: "Connecting..." });
    expect(button).toBeDisabled();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
  });

  it("renders Finish Session and listening UI while recording", () => {
    render(<RecordButton status="recording" onStart={() => {}} onStop={() => {}} />);

    expect(screen.getByRole("button", { name: "Finish Session" })).toBeEnabled();
    expect(screen.getByText("Listening now...")).toBeInTheDocument();
    expect(screen.getAllByTestId("wave-bar")).toHaveLength(9);
    expect(screen.queryByTestId("app-icon-mic")).not.toBeInTheDocument();
  });

  it("renders Extracting... as disabled while extracting", () => {
    render(<RecordButton status="extracting" onStart={() => {}} onStop={() => {}} />);

    const button = screen.getByRole("button", { name: "Extracting..." });
    expect(button).toBeDisabled();
    expect(screen.queryByText("Listening now...")).not.toBeInTheDocument();
  });
});
