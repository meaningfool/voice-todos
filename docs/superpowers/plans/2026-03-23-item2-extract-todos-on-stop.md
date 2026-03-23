# Item 2: Extract Todos on Stop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user clicks Stop, extract structured todos from the full transcript using PydanticAI + Gemini 3 Flash, and display them as Todoist-style cards.

**Architecture:** Backend accumulates the full transcript during the Soniox relay, then calls a PydanticAI agent after Soniox finishes to extract todos. Todos are sent to the frontend over the existing WebSocket before `stopped`. Frontend renders them as cards using shadcn/ui + Tailwind CSS.

**Tech Stack:** PydanticAI, Gemini 3 Flash, shadcn/ui, Tailwind CSS v4, FastAPI, React 19

**Spec:** `docs/superpowers/specs/2026-03-23-item2-extract-todos-on-stop-design.md`

---

## File Map

### Backend — New files

| File | Responsibility |
|------|---------------|
| `backend/app/models.py` | `Todo` and `ExtractionResult` Pydantic models |
| `backend/app/extract.py` | PydanticAI agent, `extract_todos()` function |
| `backend/tests/test_models.py` | Model validation tests |
| `backend/tests/test_extract.py` | Extraction integration tests (real Gemini calls) |

### Backend — Modified files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `gemini_api_key` to Settings |
| `backend/app/ws.py` | Accumulate transcript, call `extract_todos()` after Soniox finishes, send `todos` message |
| `backend/pyproject.toml` | Add `pydantic-ai[google]` dependency |
| `backend/.env` | Add `GEMINI_API_KEY` |
| `backend/tests/test_config.py` | Test new config field |

### Frontend — New files

| File | Responsibility |
|------|---------------|
| `frontend/src/types.ts` | `Todo` TypeScript interface |
| `frontend/src/components/TodoCard.tsx` | Single todo card with priority circle and metadata tags |
| `frontend/src/components/TodoCard.test.tsx` | TodoCard rendering tests |
| `frontend/src/components/TodoList.tsx` | Renders list of `TodoCard` components |
| `frontend/src/components/TodoList.test.tsx` | TodoList rendering tests |
| `frontend/src/components/TodoSkeleton.tsx` | Skeleton placeholder cards during extraction |
| `frontend/src/components/TodoSkeleton.test.tsx` | TodoSkeleton rendering test |
| `frontend/src/components/RecordButton.test.tsx` | RecordButton extracting state test |
| `frontend/src/App.test.tsx` | App conditional rendering tests |
| `frontend/src/test/setup.ts` | Vitest + testing-library setup |

### Frontend — Modified files

| File | Change |
|------|--------|
| `frontend/src/hooks/useTranscript.ts` | Add `todos` state, `extracting` status, handle `todos` message type |
| `frontend/src/components/RecordButton.tsx` | Add `extracting` case |
| `frontend/src/App.tsx` | Render `TodoList` / `TodoSkeleton` below transcript |
| `frontend/vite.config.ts` | Add Tailwind CSS plugin, vitest config |
| `frontend/src/index.css` | Tailwind import |
| `frontend/tsconfig.app.json` | Add vitest/jest-dom types |
| `frontend/package.json` | New dependencies (tailwindcss, shadcn, vitest, testing-library) |

---

## Task 1: Add Gemini API key to backend config

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing test for gemini_api_key**

Add to `backend/tests/test_config.py`:

```python
def test_settings_loads_gemini_key(monkeypatch):
    """Settings reads GEMINI_API_KEY from environment."""
    monkeypatch.setenv("SONIOX_API_KEY", "soniox-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")

    from app.config import Settings

    s = Settings()  # type: ignore[missing-argument]
    assert s.gemini_api_key == "gemini-test-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_config.py::test_settings_loads_gemini_key -v`
Expected: FAIL — `Settings` has no `gemini_api_key` attribute

- [ ] **Step 3: Implement — add gemini_api_key to Settings**

In `backend/app/config.py`, add the field to the `Settings` class:

```python
class Settings(BaseSettings):
    soniox_api_key: str
    gemini_api_key: str

    model_config = {"env_file": ".env"}
```

Add to `backend/.env`:

```
GEMINI_API_KEY=<user's actual key>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_config.py::test_settings_loads_gemini_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add gemini_api_key to backend config"
```

Note: do NOT commit `.env` — it contains secrets and is gitignored.

---

## Task 2: Create Todo and ExtractionResult models

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing tests for Todo model**

Create `backend/tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError


def test_todo_text_only():
    """Todo with just text is valid — all other fields default to None."""
    from app.models import Todo

    todo = Todo(text="Buy groceries")
    assert todo.text == "Buy groceries"
    assert todo.priority is None
    assert todo.category is None
    assert todo.due_date is None
    assert todo.notification is None
    assert todo.assign_to is None


def test_todo_all_fields():
    """Todo accepts all optional fields."""
    from app.models import Todo

    todo = Todo(
        text="Call dentist",
        priority="high",
        category="health",
        due_date="2026-03-27",
        notification="2026-03-27T09:00:00",
        assign_to="Marie",
    )
    assert todo.text == "Call dentist"
    assert todo.priority == "high"
    assert todo.assign_to == "Marie"


def test_todo_requires_text():
    """Todo without text raises ValidationError."""
    from app.models import Todo

    with pytest.raises(ValidationError):
        Todo()  # type: ignore[call-arg]


def test_todo_invalid_priority():
    """Priority must be high, medium, or low."""
    from app.models import Todo

    with pytest.raises(ValidationError):
        Todo(text="test", priority="critical")  # type: ignore[arg-type]


def test_extraction_result():
    """ExtractionResult wraps a list of todos."""
    from app.models import ExtractionResult, Todo

    result = ExtractionResult(
        todos=[Todo(text="Task A"), Todo(text="Task B", priority="low")]
    )
    assert len(result.todos) == 2
    assert result.todos[0].text == "Task A"
    assert result.todos[1].priority == "low"


def test_extraction_result_empty():
    """ExtractionResult with empty list is valid (no todos found)."""
    from app.models import ExtractionResult

    result = ExtractionResult(todos=[])
    assert result.todos == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: FAIL — `app.models` module not found

- [ ] **Step 3: Implement models**

Create `backend/app/models.py`:

```python
from typing import Literal

from pydantic import BaseModel


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: add Todo and ExtractionResult pydantic models"
```

---

## Task 3: Add pydantic-ai dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Install pydantic-ai with Google provider**

Run: `cd backend && uv add "pydantic-ai[google]"`

This updates `pyproject.toml` and `uv.lock`.

- [ ] **Step 2: Verify import works**

Run: `cd backend && uv run python -c "from pydantic_ai import Agent; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat: add pydantic-ai[google] dependency"
```

---

## Task 4: Create extraction module

**Files:**
- Create: `backend/app/extract.py`
- Create: `backend/tests/test_extract.py`

- [ ] **Step 1: Write failing integration tests for extract_todos**

These tests call the real Gemini API. They require `GEMINI_API_KEY` in the environment and are skipped without it.

Create `backend/tests/test_extract.py`:

```python
import os

import pytest

requires_gemini = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping integration test",
)


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_from_clear_transcript():
    """Given a transcript with obvious todos, extract_todos returns them."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "I need to buy groceries and I have to call the dentist. "
        "Also ask Marie to review the budget."
    )

    assert len(todos) >= 2
    texts = [t.text.lower() for t in todos]
    # Should find something about groceries and dentist
    assert any("grocer" in t for t in texts)
    assert any("dentist" in t for t in texts)


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_with_priority_and_deadline():
    """When the speaker uses urgency language and dates, those fields are populated."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "I urgently need to finish the report by Friday."
    )

    assert len(todos) >= 1
    report_todo = todos[0]
    assert report_todo.text  # Has text
    assert report_todo.priority == "high"  # "urgently" → high
    assert report_todo.due_date is not None  # "by Friday" → a date


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_with_assignment():
    """When the speaker delegates to someone, assign_to is populated."""
    from app.extract import extract_todos

    todos = await extract_todos("Ask Jean to send the invoice.")

    assert len(todos) >= 1
    assert todos[0].assign_to is not None
    assert "jean" in todos[0].assign_to.lower()


@pytest.mark.asyncio
async def test_extract_todos_empty_transcript():
    """Empty transcript returns empty list without calling the API."""
    from app.extract import extract_todos

    todos = await extract_todos("")
    assert todos == []


@pytest.mark.asyncio
async def test_extract_todos_whitespace_only():
    """Whitespace-only transcript returns empty list without calling the API."""
    from app.extract import extract_todos

    todos = await extract_todos("   \n  ")
    assert todos == []


@requires_gemini
@pytest.mark.asyncio
async def test_extract_todos_no_actionable_items():
    """Transcript with no tasks returns empty or near-empty list."""
    from app.extract import extract_todos

    todos = await extract_todos(
        "The weather is nice today. I had a good lunch."
    )

    assert len(todos) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_extract.py -v`
Expected: FAIL — `app.extract` module not found. The empty/whitespace tests will also fail since the module doesn't exist.

- [ ] **Step 3: Implement extract module**

Create `backend/app/extract.py`:

```python
from pydantic_ai import Agent

from app.config import settings
from app.models import ExtractionResult, Todo

agent = Agent(
    "google-gla:gemini-3-flash",
    output_type=ExtractionResult,
    system_prompt=(
        "You extract actionable todo items from a voice transcript.\n\n"
        "Rules:\n"
        "- Extract only clearly actionable tasks, not observations or commentary.\n"
        "- Write each todo as a clean, concise imperative sentence (not verbatim speech).\n"
        "- Only set optional fields (priority, category, due_date, notification, assign_to) "
        "when the speaker clearly indicates them.\n"
        "- priority: 'high' for urgent/important emphasis, 'medium' for moderate, 'low' for minor.\n"
        "- due_date: extract dates/deadlines as ISO format (YYYY-MM-DD). Resolve relative dates "
        "(e.g., 'tomorrow', 'next Friday') relative to the current date.\n"
        "- notification: extract reminder times as ISO datetime (YYYY-MM-DDTHH:MM:SS).\n"
        "- assign_to: extract person names when the speaker delegates a task.\n"
        "- category: infer a short category label only when the context is clear.\n"
        "- If no actionable todos are found, return an empty list.\n"
    ),
)


async def extract_todos(transcript: str) -> list[Todo]:
    """Extract structured todos from a transcript using Gemini."""
    if not transcript.strip():
        return []
    result = await agent.run(transcript)
    return result.output.todos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_extract.py -v`
Expected: empty/whitespace tests PASS immediately (no API call needed). Integration tests PASS if `GEMINI_API_KEY` is set, skipped otherwise. Run with the key set to verify the full extraction works.

Note: integration tests assert on the *shape* and *presence* of fields, not exact text — LLM output is non-deterministic. E.g., assert that a todo about groceries exists, not that the text is exactly "Buy groceries".

- [ ] **Step 5: Commit**

```bash
git add backend/app/extract.py backend/tests/test_extract.py
git commit -m "feat: add PydanticAI extraction module with Gemini 3 Flash"
```

---

## Task 5: Wire extraction into WebSocket handler

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

- [ ] **Step 1: Write failing test for the stop→todos→stopped protocol**

This test verifies the WebSocket message sequence after stop. It mocks Soniox (external service) and extract_todos (Gemini call) to test the protocol flow in isolation.

Add imports at the top of `backend/tests/test_ws.py`:

```python
from unittest.mock import AsyncMock, patch

from app.models import Todo
```

Add the test:

```python
def test_ws_stop_sends_todos_before_stopped():
    """After stop, server sends todos then stopped — verifying the protocol sequence."""
    mock_todos = [Todo(text="Buy groceries", priority="high")]

    with (
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=mock_todos),
    ):
        # Fake Soniox connection that immediately signals "finished"
        mock_soniox = AsyncMock()
        mock_soniox.send = AsyncMock()
        mock_soniox.close = AsyncMock()

        async def soniox_messages():
            yield '{"finished": true}'

        mock_soniox.__aiter__ = lambda self: soniox_messages()
        mock_connect.return_value = mock_soniox

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json()["type"] == "started"

            ws.send_json({"type": "stop"})

            # Verify protocol: todos arrives before stopped
            todos_msg = ws.receive_json()
            assert todos_msg["type"] == "todos"
            assert len(todos_msg["items"]) == 1
            assert todos_msg["items"][0]["text"] == "Buy groceries"

            stopped_msg = ws.receive_json()
            assert stopped_msg["type"] == "stopped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_stop_sends_todos_before_stopped -v`
Expected: FAIL — `extract_todos` not imported in `ws.py`, no `todos` message sent

- [ ] **Step 3: Implement — modify ws.py**

Changes to `backend/app/ws.py`:

1. Add import for `extract_todos` at the top:
```python
from app.extract import extract_todos
```

2. Modify `_relay_soniox_to_browser` to accumulate final text. Change its signature to accept a mutable list for transcript accumulation:
```python
async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
    transcript_parts: list[str],
):
```

Inside the token processing loop, accumulate final token text:
```python
if tokens:
    for t in tokens:
        if t.get("is_final", False):
            transcript_parts.append(t["text"])
```

3. In the `stop` handler (after waiting for relay task), add extraction before sending `stopped`. Remove the `stopped` send from `_relay_soniox_to_browser` — the stop handler will send it instead.

In `_relay_soniox_to_browser`, when `finished` is received, just `return` (don't send `stopped`):
```python
if event.get("finished"):
    return
```

In the stop handler, after relay completes:
```python
elif msg_type == "stop" and soniox_ws:
    await soniox_ws.send(b"")  # Empty frame = end of audio
    if relay_task:
        try:
            await asyncio.wait_for(
                relay_task, timeout=STOP_TIMEOUT_SECONDS
            )
        except TimeoutError:
            logger.warning(
                "Timed out waiting for Soniox relay to finish"
            )
            relay_task.cancel()
        finally:
            relay_task = None

    # Extract todos from accumulated transcript
    full_transcript = "".join(transcript_parts)
    if full_transcript.strip():
        todos = await extract_todos(full_transcript)
        await browser_ws.send_json(
            {
                "type": "todos",
                "items": [
                    t.model_dump(exclude_none=True) for t in todos
                ],
            }
        )
    else:
        await browser_ws.send_json({"type": "todos", "items": []})

    await browser_ws.send_json({"type": "stopped"})

    with contextlib.suppress(Exception):
        await soniox_ws.close()
    soniox_ws = None
```

4. Where `relay_task` is created, pass `transcript_parts`:
```python
transcript_parts: list[str] = []
# ... (in start handler)
relay_task = asyncio.create_task(
    _relay_soniox_to_browser(soniox_ws, browser_ws, transcript_parts)
)
```

Move `transcript_parts` declaration to the top of the endpoint function (alongside `soniox_ws` and `relay_task`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_ws.py -v`
Expected: all tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "feat: wire todo extraction into WebSocket stop flow"
```

---

## Task 6: Install Tailwind CSS + shadcn/ui + Vitest in frontend

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Create: `frontend/src/index.css`
- Create: `frontend/src/test/setup.ts`
- Various shadcn config files

- [ ] **Step 1: Install Tailwind CSS v4**

```bash
cd frontend && pnpm add tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Install Vitest + Testing Library**

```bash
cd frontend && pnpm add -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

- [ ] **Step 3: Create test setup file**

Create `frontend/src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Update vite.config.ts with Tailwind + Vitest**

Update `frontend/vite.config.ts`:

```typescript
/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  server: {
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 5: Update tsconfig.app.json with test types**

In `frontend/tsconfig.app.json`, update the `types` array:

```json
"types": ["vite/client", "vitest/globals", "@testing-library/jest-dom/vitest"]
```

- [ ] **Step 6: Create index.css with Tailwind import**

Create or replace `frontend/src/index.css`:

```css
@import "tailwindcss";
```

Make sure `main.tsx` imports this CSS file. Check if it already does; if not, add:
```typescript
import "./index.css";
```

- [ ] **Step 7: Add test script to package.json**

Add to the `scripts` section of `frontend/package.json`:

```json
"test": "vitest",
"test:run": "vitest run"
```

- [ ] **Step 8: Initialize shadcn/ui**

```bash
cd frontend && pnpm dlx shadcn@latest init -t vite
```

Follow the prompts. This will set up `components.json`, tsconfig path aliases (`@/`), and CSS variables.

- [ ] **Step 9: Add shadcn components**

```bash
cd frontend && pnpm dlx shadcn@latest add card badge
```

- [ ] **Step 10: Verify build and test runner work**

```bash
cd frontend && pnpm build && pnpm test:run
```

Expected: build succeeds, test runner works (0 tests found is fine)

- [ ] **Step 11: Commit**

```bash
cd frontend
git add -A
git commit -m "feat: install Tailwind CSS v4, shadcn/ui, and Vitest with testing-library"
```

---

## Task 7: Create TodoCard component (TDD)

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/components/TodoCard.test.tsx`
- Create: `frontend/src/components/TodoCard.tsx`

- [ ] **Step 1: Define the Todo TypeScript interface**

Create `frontend/src/types.ts`:

```typescript
export interface Todo {
  text: string;
  priority?: "high" | "medium" | "low";
  category?: string;
  dueDate?: string;
  notification?: string;
  assignTo?: string;
}
```

- [ ] **Step 2: Write failing tests for TodoCard**

Create `frontend/src/components/TodoCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { TodoCard } from "./TodoCard";
import type { Todo } from "../types";

describe("TodoCard", () => {
  it("renders todo text", () => {
    const todo: Todo = { text: "Buy groceries" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
  });

  it("renders due date badge when present", () => {
    const todo: Todo = { text: "Call dentist", dueDate: "2026-03-27" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText(/2026-03-27/)).toBeInTheDocument();
  });

  it("renders priority badge when present", () => {
    const todo: Todo = { text: "Fix bug", priority: "high" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText(/high/)).toBeInTheDocument();
  });

  it("renders category badge when present", () => {
    const todo: Todo = { text: "Review PR", category: "work" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText(/work/)).toBeInTheDocument();
  });

  it("renders assignTo badge when present", () => {
    const todo: Todo = { text: "Review budget", assignTo: "Marie" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText(/Marie/)).toBeInTheDocument();
  });

  it("renders notification badge when present", () => {
    const todo: Todo = { text: "Meeting", notification: "2026-03-27T09:00" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText(/2026-03-27T09:00/)).toBeInTheDocument();
  });

  it("does not render optional badges when fields are absent", () => {
    const todo: Todo = { text: "Simple task" };
    render(<TodoCard todo={todo} />);
    expect(screen.getByText("Simple task")).toBeInTheDocument();
    // No badges should be rendered
    expect(screen.queryByText(/📅/)).not.toBeInTheDocument();
    expect(screen.queryByText(/⚡/)).not.toBeInTheDocument();
    expect(screen.queryByText(/📁/)).not.toBeInTheDocument();
    expect(screen.queryByText(/👤/)).not.toBeInTheDocument();
    expect(screen.queryByText(/🔔/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && pnpm test:run src/components/TodoCard.test.tsx`
Expected: FAIL — `TodoCard` module not found

- [ ] **Step 4: Implement TodoCard**

Create `frontend/src/components/TodoCard.tsx`:

```tsx
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Todo } from "../types";

const priorityCircle: Record<string, string> = {
  high: "border-red-500",
  medium: "border-orange-400",
  low: "border-blue-500",
};

interface Props {
  todo: Todo;
}

export function TodoCard({ todo }: Props) {
  const circleColor = todo.priority
    ? priorityCircle[todo.priority]
    : "border-gray-300";

  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardContent className="flex items-start gap-3 p-4">
        <div
          className={`w-5 h-5 rounded-full border-2 shrink-0 mt-0.5 ${circleColor}`}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-snug">{todo.text}</p>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {todo.dueDate && (
              <Badge variant="secondary" className="text-red-600 bg-red-50 text-xs">
                📅 {todo.dueDate}
              </Badge>
            )}
            {todo.priority && (
              <Badge variant="secondary" className="text-orange-600 bg-orange-50 text-xs">
                ⚡ {todo.priority}
              </Badge>
            )}
            {todo.category && (
              <Badge variant="secondary" className="text-blue-600 bg-blue-50 text-xs">
                📁 {todo.category}
              </Badge>
            )}
            {todo.assignTo && (
              <Badge variant="secondary" className="text-purple-600 bg-purple-50 text-xs">
                👤 {todo.assignTo}
              </Badge>
            )}
            {todo.notification && (
              <Badge variant="secondary" className="text-green-600 bg-green-50 text-xs">
                🔔 {todo.notification}
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && pnpm test:run src/components/TodoCard.test.tsx`
Expected: all 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/TodoCard.tsx frontend/src/components/TodoCard.test.tsx
git commit -m "feat: add TodoCard component with priority circle and metadata badges"
```

---

## Task 8: Create TodoList component (TDD)

**Files:**
- Create: `frontend/src/components/TodoList.test.tsx`
- Create: `frontend/src/components/TodoList.tsx`

- [ ] **Step 1: Write failing tests for TodoList**

Create `frontend/src/components/TodoList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { TodoList } from "./TodoList";
import type { Todo } from "../types";

describe("TodoList", () => {
  it("renders nothing when todos array is empty", () => {
    const { container } = render(<TodoList todos={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders count header with correct number", () => {
    const todos: Todo[] = [
      { text: "Task A" },
      { text: "Task B" },
    ];
    render(<TodoList todos={todos} />);
    expect(screen.getByText("Extracted Todos (2)")).toBeInTheDocument();
  });

  it("renders all todo items", () => {
    const todos: Todo[] = [
      { text: "Buy groceries" },
      { text: "Call dentist", priority: "high" },
      { text: "Review PR", assignTo: "Marie" },
    ];
    render(<TodoList todos={todos} />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByText("Call dentist")).toBeInTheDocument();
    expect(screen.getByText("Review PR")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && pnpm test:run src/components/TodoList.test.tsx`
Expected: FAIL — `TodoList` module not found

- [ ] **Step 3: Implement TodoList**

Create `frontend/src/components/TodoList.tsx`:

```tsx
import type { Todo } from "../types";
import { TodoCard } from "./TodoCard";

interface Props {
  todos: Todo[];
}

export function TodoList({ todos }: Props) {
  if (todos.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 mt-4">
      <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
        Extracted Todos ({todos.length})
      </p>
      {todos.map((todo, index) => (
        <TodoCard key={index} todo={todo} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && pnpm test:run src/components/TodoList.test.tsx`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TodoList.tsx frontend/src/components/TodoList.test.tsx
git commit -m "feat: add TodoList component"
```

---

## Task 9: Create TodoSkeleton component (TDD)

**Files:**
- Create: `frontend/src/components/TodoSkeleton.test.tsx`
- Create: `frontend/src/components/TodoSkeleton.tsx`

- [ ] **Step 1: Write failing test for TodoSkeleton**

Create `frontend/src/components/TodoSkeleton.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { TodoSkeleton } from "./TodoSkeleton";

describe("TodoSkeleton", () => {
  it("renders 3 skeleton placeholder cards", () => {
    const { container } = render(<TodoSkeleton />);
    const cards = container.querySelectorAll("[class*='animate-pulse']");
    expect(cards).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test:run src/components/TodoSkeleton.test.tsx`
Expected: FAIL — `TodoSkeleton` module not found

- [ ] **Step 3: Implement TodoSkeleton**

Create `frontend/src/components/TodoSkeleton.tsx`:

```tsx
import { Card, CardContent } from "@/components/ui/card";

export function TodoSkeleton() {
  return (
    <div className="flex flex-col gap-3 mt-4">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="flex items-start gap-3 p-4">
            <div className="w-5 h-5 rounded-full bg-gray-200 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-3/4" />
              <div className="h-3 bg-gray-100 rounded w-1/3" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test:run src/components/TodoSkeleton.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TodoSkeleton.tsx frontend/src/components/TodoSkeleton.test.tsx
git commit -m "feat: add TodoSkeleton component"
```

---

## Task 10: Update RecordButton with extracting state (TDD)

**Files:**
- Create: `frontend/src/components/RecordButton.test.tsx`
- Modify: `frontend/src/components/RecordButton.tsx`

- [ ] **Step 1: Write failing test for extracting state**

Create `frontend/src/components/RecordButton.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { RecordButton } from "./RecordButton";

describe("RecordButton", () => {
  it("renders 'Extracting...' disabled button when status is extracting", () => {
    render(<RecordButton status="extracting" onStart={() => {}} onStop={() => {}} />);
    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("Extracting...");
    expect(button).toBeDisabled();
  });

  it("renders Start button when idle", () => {
    render(<RecordButton status="idle" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Start");
  });

  it("renders Stop button when recording", () => {
    render(<RecordButton status="recording" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Stop");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && pnpm test:run src/components/RecordButton.test.tsx`
Expected: FAIL — `extracting` is not a valid `Status` value yet (type error or missing case)

- [ ] **Step 3: Update RecordButton**

In `frontend/src/components/RecordButton.tsx`, replace the `stopping` case with `extracting`:

```tsx
case "extracting":
  return <button disabled>Extracting...</button>;
```

Also update the `Status` type in `frontend/src/hooks/useTranscript.ts`. **This task only changes the `Status` type definition line** — all other `useTranscript.ts` changes (new state, message handling, stop logic) belong to Task 11.

Change line 3 of `useTranscript.ts` from:
```typescript
export type Status = "idle" | "connecting" | "recording" | "stopping";
```
to:
```typescript
export type Status = "idle" | "connecting" | "recording" | "extracting";
```

Also update the `stop` callback's `setStatus("stopping")` to `setStatus("extracting")` so the existing code compiles. No other changes to this file in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && pnpm test:run src/components/RecordButton.test.tsx`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/RecordButton.tsx frontend/src/components/RecordButton.test.tsx frontend/src/hooks/useTranscript.ts
git commit -m "feat: add extracting state to RecordButton"
```

---

## Task 11: Update useTranscript hook for extraction

**Files:**
- Modify: `frontend/src/hooks/useTranscript.ts`

The `Status` type and `setStatus("extracting")` in `stop` were already updated in Task 10. This task adds: `todos` state, `todos` message handling, and clearing todos on start. The snake_case→camelCase conversion happens inline in the message handler — no extracted function or separate type needed.

- [ ] **Step 1: Update the hook**

Changes to `frontend/src/hooks/useTranscript.ts`:

1. Import `Todo` type:
```typescript
import type { Todo } from "../types";
```

2. Add `todos` state:
```typescript
const [todos, setTodos] = useState<Todo[]>([]);
```

3. Update `TranscriptMessage` interface to include the `todos` message:
```typescript
interface TranscriptMessage {
  type: "started" | "transcript" | "todos" | "stopped" | "error";
  tokens?: Token[];
  items?: Array<{
    text: string;
    priority?: string;
    category?: string;
    due_date?: string;
    notification?: string;
    assign_to?: string;
  }>;
  message?: string;
}
```

The `items` type uses snake_case to match exactly what the backend sends.

4. Add handler for `todos` message in `ws.onmessage`:
```typescript
} else if (msg.type === "todos" && msg.items) {
  setTodos(
    msg.items.map((item) => ({
      text: item.text,
      priority: item.priority as Todo["priority"],
      category: item.category,
      dueDate: item.due_date,
      notification: item.notification,
      assignTo: item.assign_to,
    }))
  );
```

This is the single point where snake_case (backend) becomes camelCase (frontend).

5. Clear todos on start (after `setFinalText("")`):
```typescript
setTodos([]);
```

6. Update return:
```typescript
return { status, finalText, interimText, todos, start, stop };
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && pnpm build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useTranscript.ts
git commit -m "feat: add todos state and extracting status to useTranscript hook"
```

---

## Task 12: Update App.tsx to wire everything together (TDD)

**Files:**
- Create: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing tests for App conditional rendering**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock useTranscript to control state
const mockUseTranscript = vi.fn();
vi.mock("./hooks/useTranscript", () => ({
  useTranscript: () => mockUseTranscript(),
}));

// Must import App after the mock is set up
import App from "./App";

describe("App", () => {
  const baseHook = {
    status: "idle" as const,
    finalText: "",
    interimText: "",
    todos: [],
    start: vi.fn(),
    stop: vi.fn(),
  };

  it("renders TodoSkeleton when status is extracting", () => {
    mockUseTranscript.mockReturnValue({ ...baseHook, status: "extracting" });
    const { container } = render(<App />);
    expect(container.querySelector("[class*='animate-pulse']")).not.toBeNull();
  });

  it("renders TodoList when idle with todos", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "idle",
      todos: [{ text: "Buy groceries" }, { text: "Call dentist" }],
    });
    render(<App />);
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByText("Call dentist")).toBeInTheDocument();
    expect(screen.getByText("Extracted Todos (2)")).toBeInTheDocument();
  });

  it("does not render TodoList when idle with no todos", () => {
    mockUseTranscript.mockReturnValue({ ...baseHook, status: "idle", todos: [] });
    render(<App />);
    expect(screen.queryByText(/Extracted Todos/)).not.toBeInTheDocument();
  });

  it("does not render TodoList while extracting even if todos exist", () => {
    mockUseTranscript.mockReturnValue({
      ...baseHook,
      status: "extracting",
      todos: [{ text: "Stale todo" }],
    });
    render(<App />);
    // Should show skeleton, not the todo list
    expect(screen.queryByText("Extracted Todos")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && pnpm test:run src/App.test.tsx`
Expected: FAIL — App doesn't import or render TodoList/TodoSkeleton yet

- [ ] **Step 3: Update App.tsx**

Replace `frontend/src/App.tsx`:

```tsx
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && pnpm test:run src/App.test.tsx`
Expected: all 4 tests PASS

- [ ] **Step 5: Run all frontend tests**

Run: `cd frontend && pnpm test:run`
Expected: all tests PASS

- [ ] **Step 6: Verify build and lint**

Run: `cd frontend && pnpm build && pnpm lint`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: wire TodoList and TodoSkeleton into App"
```

---

## Task 13: End-to-end manual smoke test

- [ ] **Step 1: Start backend**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && pnpm dev
```

- [ ] **Step 3: Test the flow**

1. Open http://localhost:5173
2. Click Start
3. Speak a few todos: "I need to buy groceries tomorrow, and remind Marie to send the report by Friday"
4. Click Stop
5. Verify: skeleton cards appear briefly, then todo cards appear with extracted items
6. Verify: metadata tags (due dates, assignments) appear when relevant

- [ ] **Step 4: Run all tests (backend + frontend)**

```bash
cd backend && uv run pytest -v
cd frontend && pnpm test:run
```

Expected: all tests PASS

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "feat: item 2 complete — extract todos on stop"
```

---

## Task 14: Audio pipeline integration test (agent-browser)

Verify no audio bytes are dropped between the AudioWorklet and the backend WebSocket during the stop sequence. Uses a real browser — no mocks in the data path.

**Files:**
- Create: `scripts/test_audio_pipeline.sh`

- [ ] **Step 1: Write the test script**

Create `scripts/test_audio_pipeline.sh` that:

1. Ensures both dev servers are running (backend on :8000, frontend on :5173)
2. Clears `sessions/recent/` so we can identify the new session
3. Opens the app with `agent-browser --engine chrome`
4. Injects a fake `getUserMedia` via `agent-browser eval`:

```javascript
navigator.mediaDevices.getUserMedia = async (constraints) => {
  const ctx = new AudioContext({ sampleRate: 16000 });
  const osc = ctx.createOscillator();
  osc.frequency.value = 440;
  osc.start();
  const dest = ctx.createMediaStreamDestination();
  osc.connect(dest);
  return dest.stream;
};
```

5. Clicks Start (via `agent-browser snapshot -i` then `agent-browser click @ref`)
6. Waits 3 seconds for audio to flow
7. Clicks Stop
8. Waits for the button to return to "Start" (poll `agent-browser snapshot -i` until idle)
9. Finds the newest session in `sessions/recent/`
10. Reads `audio.pcm` file size
11. Computes expected bytes: `3 seconds × 16000 × 2 = 96000`
12. Asserts: actual >= 86400 (90% of expected)
13. Closes the browser

- [ ] **Step 2: Run the test — verify it passes with the current code**

```bash
./scripts/test_audio_pipeline.sh
```

Expected: PASS — audio.pcm is ~96KB

- [ ] **Step 3: Temporarily break the stop sequence — verify the test fails**

In `frontend/src/hooks/useTranscript.ts`, move `ws.send(stop)` back to synchronous (before the setTimeout). Run the test again.

Expected: FAIL — audio.pcm is smaller than expected because the backend received stop before all audio arrived, and subsequent audio was ignored.

- [ ] **Step 4: Restore the fix, verify the test passes again**

- [ ] **Step 5: Commit**

```bash
git add scripts/test_audio_pipeline.sh
git commit -m "test: add audio pipeline integration test with agent-browser"
```
