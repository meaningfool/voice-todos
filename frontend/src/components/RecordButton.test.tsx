import { render, screen } from "@testing-library/react";
import { RecordButton } from "./RecordButton";

describe("RecordButton", () => {
  it("renders 'Extracting...' disabled button when status is extracting", () => {
    render(<RecordButton status="extracting" onStart={() => {}} onStop={() => {}} />);
    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("Extracting...");
    expect(button).toBeDisabled();
  });

  it("renders Start button when idle", () => {
    render(<RecordButton status="idle" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Start");
  });

  it("renders Stop button when recording", () => {
    render(<RecordButton status="recording" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Stop");
  });
});
