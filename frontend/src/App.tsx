import { useTranscript } from "./hooks/useTranscript";
import { RecordButton } from "./components/RecordButton";
import { TranscriptArea } from "./components/TranscriptArea";

function App() {
  const { status, finalText, interimText, start, stop } = useTranscript();

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem" }}>
      <h1>Voice Todos</h1>
      <RecordButton status={status} onStart={start} onStop={stop} />
      <TranscriptArea finalText={finalText} interimText={interimText} />
    </div>
  );
}

export default App;
