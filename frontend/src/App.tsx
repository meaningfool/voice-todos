import { useTranscript } from "./hooks/useTranscript";
import { RecordButton } from "./components/RecordButton";
import { TranscriptArea } from "./components/TranscriptArea";
import { TodoList } from "./components/TodoList";
import { TodoSkeleton } from "./components/TodoSkeleton";

function App() {
  const {
    status,
    finalText,
    interimText,
    todos,
    micRecordingUrl,
    warningMessage,
    start,
    stop,
  } = useTranscript();

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem" }}>
      <h1>Voice Todos</h1>
      <RecordButton status={status} onStart={start} onStop={stop} />
      <TranscriptArea finalText={finalText} interimText={interimText} />
      {warningMessage && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.75rem 1rem",
            background: "#fff7ed",
            color: "#9a3412",
            borderRadius: 8,
          }}
        >
          {warningMessage}
        </div>
      )}
      {status === "extracting" && <TodoSkeleton />}
      {status === "idle" && todos.length > 0 && <TodoList todos={todos} />}
      {status === "idle" && todos.length === 0 && finalText && (
        <div style={{ marginTop: "1rem", color: "#888", fontStyle: "italic" }}>
          No todos found in this recording.
        </div>
      )}
      {micRecordingUrl && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#f5f5f5", borderRadius: 8 }}>
          <div style={{ marginBottom: "0.5rem", fontWeight: 500 }}>Raw mic recording</div>
          <audio controls src={micRecordingUrl} style={{ width: "100%" }} />
          <a href={micRecordingUrl} download="mic-recording.webm" style={{ fontSize: "0.85rem" }}>
            Download
          </a>
        </div>
      )}
    </div>
  );
}

export default App;
