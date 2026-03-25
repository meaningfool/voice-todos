import { useTranscript } from "./hooks/useTranscript";
import { AppIcon } from "./components/AppIcon";
import { RecordButton } from "./components/RecordButton";
import { SessionDetails } from "./components/SessionDetails";
import { TodoList } from "./components/TodoList";
import { TodoSkeleton } from "./components/TodoSkeleton";

function App() {
  const {
    status,
    finalText,
    todos,
    micRecordingUrl,
    warningMessage,
    start,
    stop,
  } = useTranscript();

  const hasSessionArtifacts = Boolean(
    finalText || micRecordingUrl || warningMessage || todos.length > 0
  );
  const showInitialEmptyState = status === "idle" && !hasSessionArtifacts;
  const showNoTodosState =
    status === "idle" &&
    !warningMessage &&
    todos.length === 0 &&
    (Boolean(finalText) || Boolean(micRecordingUrl));

  return (
    <main className="voice-page-shell">
      <section className="voice-device-shell" aria-label="Voice-Todos app shell">
        <header className="voice-header">
          <h1>Voice-Todos</h1>
        </header>

        <div className="voice-task-container">
          {showInitialEmptyState ? (
            <div className="voice-empty-state">
              <div className="voice-empty-illustration" aria-hidden="true">
                <AppIcon name="mic" className="voice-empty-illustration__icon" />
              </div>
              <h2>Start speaking...</h2>
              <p>Your voice will be turned into tasks in real time.</p>
            </div>
          ) : null}

          {warningMessage ? <div className="voice-warning-card">{warningMessage}</div> : null}
          {todos.length > 0 ? <TodoList todos={todos} /> : null}
          {status === "extracting" && todos.length === 0 ? <TodoSkeleton /> : null}
          {showNoTodosState ? (
            <div className="voice-result-state">No todos found in this recording.</div>
          ) : null}
        </div>

        <div className="voice-device-dock">
          <RecordButton status={status} onStart={start} onStop={stop} />
        </div>
      </section>

      <SessionDetails finalText={finalText} micRecordingUrl={micRecordingUrl} />
    </main>
  );
}

export default App;
