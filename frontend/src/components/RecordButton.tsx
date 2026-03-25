import type { Status } from "../hooks/useTranscript";
import { AppIcon } from "./AppIcon";

interface Props {
  status: Status;
  onStart: () => void;
  onStop: () => void;
}

function ListeningUi() {
  return (
    <div className="voice-listening-ui">
      <div className="voice-waveform" aria-hidden="true">
        {Array.from({ length: 9 }).map((_, index) => (
          <span key={index} className="wave-bar" data-testid="wave-bar" />
        ))}
      </div>
      <p className="voice-listening-label">Listening now...</p>
    </div>
  );
}

export function RecordButton({ status, onStart, onStop }: Props) {
  const isDisabled = status === "connecting" || status === "extracting";
  const isRecording = status === "recording";

  const labelByStatus: Record<Status, string> = {
    idle: "Start Session",
    connecting: "Connecting...",
    recording: "Finish Session",
    extracting: "Extracting...",
  };

  const handleClick = () => {
    if (status === "idle") {
      onStart();
    } else if (status === "recording") {
      onStop();
    }
  };

  return (
    <div className="voice-dock" data-status={status}>
      {isRecording ? <ListeningUi /> : null}
      <button
        type="button"
        className="voice-primary-button"
        disabled={isDisabled}
        onClick={handleClick}
      >
        {status === "idle" ? (
          <AppIcon name="mic" className="voice-button-icon" />
        ) : null}
        <span>{labelByStatus[status]}</span>
      </button>
    </div>
  );
}
