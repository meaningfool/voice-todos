# Item 2: Extract Todos on Stop

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

- Unit tests for `extract_todos()` with sample transcripts
- Mock the PydanticAI agent to avoid real Gemini API calls
- WebSocket integration tests: verify stop → todos → stopped sequence

### Frontend

- Component rendering tests using Vitest + @testing-library/react
- Tests for TodoCard (renders text, badges conditionally), TodoList (renders items, empty state), TodoSkeleton (renders placeholders), RecordButton (extracting state)

## Out of Scope

- Real-time extraction while speaking (item 3)
- Tentative/confirmed todo states (item 4)
- Todo persistence or database
- Todo editing or deletion
- Authentication
- Transcript visibility toggle (deferred to first working version)
