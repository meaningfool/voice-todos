import type { Status } from "../hooks/useTranscript";

interface Props {
  status: Status;
  onStart: () => void;
  onStop: () => void;
}

export function RecordButton({ status, onStart, onStop }: Props) {
  switch (status) {
    case "idle":
      return <button onClick={onStart}>Start</button>;
    case "connecting":
      return <button disabled>Connecting...</button>;
    case "recording":
      return (
        <button onClick={onStop} style={{ backgroundColor: "#dc2626", color: "white" }}>
          Stop
        </button>
      );
    case "extracting":
      return <button disabled>Extracting...</button>;
  }
}
