# Item 2 Design: Extract Todos on Stop

User clicks Stop. Todos are extracted from the full transcript and appear as a Todoist-style card list below the transcript.

## Context

Item 1 is complete: browser mic → FastAPI WebSocket → Soniox STT → live transcript. Item 2 adds a structured extraction layer triggered by the Stop button. No turn detection or real-time extraction — that's item 3.

## Data Model

### Backend (Pydantic)

```python
class Todo(BaseModel):
    text: str
    priority: Literal["high", "medium", "low"] | None = None
    category: str | None = None
    due_date: str | None = None
    notification: str | None = None
    assign_to: str | None = None

class ExtractionResult(BaseModel):
    todos: list[Todo]
```

All fields optional except `text`. The LLM infers them from natural speech cues — "I really need to call the dentist by Friday" → `{text: "Call the dentist", priority: "high", due_date: "2026-03-27"}`.

### Frontend (TypeScript)

```typescript
interface Todo {
  text: string
  priority?: "high" | "medium" | "low"
  category?: string
  dueDate?: string
  notification?: string
  assignTo?: string
}
```

## Extraction Layer

New module `backend/app/extract.py`.

- PydanticAI agent with Gemini 3 Flash as the model
- `ExtractionResult` as the structured output type
- System prompt instructs the model to:
  - Extract actionable todos from the transcript
  - Infer optional fields only when clearly stated in speech
  - Return clean, concise todo text (not verbatim speech)
- Single public function: `extract_todos(transcript: str) -> list[Todo]`
- Agent created once at module level (reused across requests)
- API key: `GEMINI_API_KEY` env var, added to `config.py` Settings

## WebSocket Flow

### Current (item 1)

```
browser: { type: "stop" }
server: signals end-of-audio to Soniox
server: waits for Soniox "finished"
server: { type: "stopped" }
```

### New (item 2)

```
browser: { type: "stop" }
server: signals end-of-audio to Soniox
server: waits for Soniox "finished"
server: calls extract_todos(full_transcript)
server: { type: "todos", items: [...] }
server: { type: "stopped" }
```

The backend already processes final tokens from Soniox in the relay loop. It accumulates the full transcript string as final tokens arrive. After Soniox finishes, it passes the transcript to `extract_todos()` before sending `stopped`.

### New message type

```json
{
  "type": "todos",
  "items": [
    {
      "text": "Write a strategic note",
      "priority": "high",
      "due_date": "2026-03-24T10:00:00",
      "category": null,
      "notification": null,
      "assign_to": null
    }
  ]
}
```

Null fields are omitted in the JSON sent to the frontend.

## Frontend

### Status transitions

```
idle → connecting → recording → extracting → idle
```

The `stopping` state is replaced by `extracting`. When the user clicks Stop, the frontend enters `extracting` immediately (showing skeleton cards). It stays in `extracting` until `stopped` is received. The `todos` message arrives during this state and populates the todo list. There is no separate `stopping` state — from the user's perspective, clicking Stop means "extract my todos," so the UI should reflect that.

### New components

- **`TodoList`** — receives `todos: Todo[]`, renders vertical card list
- **`TodoCard`** — single card with priority-colored circle, todo text, metadata tags (due date, priority, category, assigned to, notification)
- **`TodoSkeleton`** — skeleton placeholder cards shown during `extracting` state

### Changes to existing components

- **`useTranscript` hook** — new `todos: Todo[]` state, handles `{ type: "todos" }` message, new `extracting` status
- **`App.tsx`** — renders `TodoList` below `TranscriptArea`, renders `TodoSkeleton` during extracting
- **`RecordButton`** — shows "Extracting..." (disabled) during `extracting` state

### UI design

Todoist-inspired vertical cards:

- Priority circle on the left (red = high, orange = medium, blue = low, gray = none)
- Todo text as the primary line
- Metadata tags below as small colored pills: due date, priority label, category, assigned person, notification
- Tags only rendered when the field is present
- Skeleton cards (gray placeholder) shown while extraction is in progress

### UI framework

Install shadcn/ui + Tailwind CSS into the frontend:

- Tailwind CSS v4 + `@tailwindcss/vite` plugin
- shadcn/ui initialized for Vite
- Components used: `Card`, `Badge`
- Priority circle and metadata tags are custom-styled on top of shadcn primitives

## Dependencies

### Backend

- `pydantic-ai` with Google/Gemini provider
- New env var: `GEMINI_API_KEY`

### Frontend

- `tailwindcss`, `@tailwindcss/vite`
- shadcn/ui components: `card`, `badge`

## Testing

### Backend

- Unit tests for `extract_todos()` with sample transcripts (real Gemini API, skipped without key)
- WebSocket integration tests: verify stop → todos → stopped sequence
- **Session replay tests**: replay recorded `soniox.jsonl` fixtures to verify transcript accumulation — catches interim tail text loss without needing a mic or Soniox API
- **Session recording**: every WebSocket session automatically records `audio.pcm`, `soniox.jsonl`, `result.json` to `sessions/recent/` (last 10 kept). Test fixtures are copied to `backend/tests/fixtures/`.

### Frontend

- Component rendering tests using Vitest + @testing-library/react
- Tests for TodoCard (renders text, badges conditionally), TodoList (renders items, empty state), TodoSkeleton (renders placeholders), RecordButton (extracting state)
- **Stop sequence test**: verifies `ws.send(stop)` is sent AFTER the 300ms audio flush delay, not synchronously (uses fake timers, catches ordering regressions)

### Audio pipeline integration test (agent-browser)

End-to-end test that verifies no audio bytes are dropped between the browser's AudioWorklet and the backend WebSocket during the stop sequence. Uses a real browser with a real audio pipeline — no mocks in the data path.

**Mechanism:**
1. `agent-browser eval` monkey-patches `navigator.mediaDevices.getUserMedia` to return a `MediaStream` from an `OscillatorNode` (440Hz tone at 16kHz). This produces real audio samples that flow through the real AudioWorklet, real WebSocket send, to the real backend.
2. Click Start, wait N seconds, click Stop, wait for idle.
3. Read the backend's recorded `sessions/recent/*/audio.pcm` file size.
4. Assert: received bytes >= 90% of expected (`N × 16000 samples/sec × 2 bytes/sample`).

**What it proves:** If someone removes the 300ms flush delay or breaks the stop sequence order, the backend will receive fewer audio bytes than expected because in-flight chunks between the worklet thread and the main thread are destroyed on disconnect.

**Requirements:** Backend and frontend dev servers running. Chrome installed via `agent-browser install`.

## Out of Scope

- Real-time extraction while speaking (item 3)
- Later todo presentation-state refinements
- Todo persistence or database
- Todo editing or deletion
- Authentication
- Transcript visibility toggle (deferred to first working version)

---

## Revision — 2026-03-23 (post-implementation)

Changes discovered and applied during implementation that diverge from the original spec above.

### Soniox stop sequence

The original spec assumed sending an empty frame (`b""`) was sufficient to end the Soniox stream. It is not — pending interim tokens are silently dropped. The correct sequence is:

1. Send `{"type": "finalize"}` — promotes all interim tokens to final, emits `<fin>` marker
2. Send `b""` — signals end of stream
3. Filter `<fin>` from transcript tokens, clear stale interim state after finalize

See `docs/references/soniox.md` for full details.

### Backend sends full transcript in `stopped` message

The `stopped` message now includes a `transcript` field with the backend's assembled transcript:

```json
{ "type": "stopped", "transcript": "full text here" }
```

The frontend uses this as the source of truth instead of independently reconstructing from interim/final tokens, which was prone to state timing issues.

### Frontend empty state

When extraction returns no todos, the transcript stays visible and a "No todos found in this recording." message is shown. The original spec had no handling for this case — the transcript would disappear.

### Raw mic recording

The frontend records the raw mic stream via `MediaRecorder` (runs independently, non-blocking). After stop, an audio player and download link appear. This is a debugging tool for comparing what the mic captured vs what Soniox transcribed.

### 200ms mic tail delay

On stop, the mic keeps streaming for 200ms before teardown, giving Soniox trailing audio context. The stop signal is sent to the backend after this delay.

### Testing

- **Soniox integration test** (`test_soniox_integration.py`): Sends real audio to real Soniox API. Proves finalize captures trailing words, and without finalize they're lost.
- **Replay tests simplified**: 3 fixture-specific interim tail tests replaced by 2 generic tests (`test_transcript_not_empty`, `test_result_matches_transcript`) that run against all fixtures. New fixtures added: `to-build-todos`, `finding-out-if-you`, `stop-the-button`, `text-is-captured`.
- **Frontend `transcriptReducer`**: Extracted message-processing logic into a pure testable function. Tests prove old behavior (interim promotion) loses text when a finals-only message clears the ref, and new behavior (backend transcript) preserves it.
- **300ms flush delay removed**: Was added then removed after proving audio bytes are not lost. The audio pipeline integration test (Task 14) was not needed.
- **Stop sequence test removed**: The 300ms delay it tested no longer exists.

### Utility scripts added

- `scripts/pcm_to_wav.py` — converts `audio.pcm` to playable WAV
- `scripts/soniox_transcribe.py` — sends audio directly to Soniox (bypasses backend)
