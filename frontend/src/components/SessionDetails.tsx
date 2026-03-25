interface Props {
  finalText: string;
  micRecordingUrl: string | null;
}

export function SessionDetails({ finalText, micRecordingUrl }: Props) {
  if (!finalText && !micRecordingUrl) {
    return null;
  }

  return (
    <details className="voice-session-details">
      <summary className="voice-session-details__summary">Session details</summary>
      <div className="voice-session-details__content">
        {finalText ? (
          <div className="voice-session-details__section">
            <h2 className="voice-session-details__label">Transcript</h2>
            <p className="voice-session-transcript">{finalText}</p>
          </div>
        ) : null}
        {micRecordingUrl ? (
          <div className="voice-session-details__section">
            <h2 className="voice-session-details__label">Recording</h2>
            <audio controls src={micRecordingUrl} className="voice-session-audio" />
            <a
              href={micRecordingUrl}
              download="mic-recording.webm"
              className="voice-session-download"
            >
              Download raw recording
            </a>
          </div>
        ) : null}
      </div>
    </details>
  );
}
