interface Props {
  finalText: string;
  interimText: string;
}

export function TranscriptArea({ finalText, interimText }: Props) {
  if (!finalText && !interimText) {
    return (
      <div style={{ marginTop: "1rem", color: "#888", fontStyle: "italic" }}>
        Click Start and begin speaking...
      </div>
    );
  }

  return (
    <div style={{ marginTop: "1rem", lineHeight: 1.6 }}>
      <span>{finalText}</span>
      <span style={{ color: "#888", fontStyle: "italic" }}>{interimText}</span>
    </div>
  );
}
