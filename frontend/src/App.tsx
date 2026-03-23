import { useTranscript } from "./hooks/useTranscript";
import { RecordButton } from "./components/RecordButton";
import { TranscriptArea } from "./components/TranscriptArea";
import { TodoList } from "./components/TodoList";
import { TodoSkeleton } from "./components/TodoSkeleton";

function App() {
  const { status, finalText, interimText, todos, start, stop } =
    useTranscript();

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem" }}>
      <h1>Voice Todos</h1>
      <RecordButton status={status} onStart={start} onStop={stop} />
      <TranscriptArea finalText={finalText} interimText={interimText} />
      {status === "extracting" && <TodoSkeleton />}
      {status === "idle" && todos.length > 0 && <TodoList todos={todos} />}
    </div>
  );
}

export default App;
