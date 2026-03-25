# Item 4: Voice-Todos UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend UI so the app matches the approved Motion Light reference closely while preserving the existing live recording and incremental todo behavior.

**Architecture:** This is a frontend-only UI rewrite. Keep `useTranscript()` and the current backend protocol intact, rebuild the screen shell in `App.tsx`, turn `RecordButton` into the bottom dock, restyle the todo feed to match the checked-in HTML reference, and keep transcript/debug information outside the main phone-shell UI in a secondary details surface. Use small inline SVG components and CSS keyframes instead of adding a new icon dependency.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, Vitest, Testing Library

**Spec:** `docs/superpowers/specs/2026-03-24-item4-ui-redesign-design.md`

**Reference HTML:** `docs/references/2026-03-24-item4-motion-light-reference.html`

---

## Prerequisites

- Open both the spec and the checked-in reference HTML before starting implementation.
- Treat the reference HTML as the visual source of truth. Use the spec only to resolve real app state mapping.
- Keep changes scoped to the frontend files listed below. The repo may already contain unrelated backend work in progress.
- Do not add a new icon package unless absolutely necessary. The reference can be matched with inline SVG components.

---

## File Map

### Frontend — New files

| File | Responsibility |
|------|---------------|
| `frontend/src/components/AppIcon.tsx` | Small inline SVG icon set matching the reference (`mic`, `calendar`, `tag`, `user`) |
| `frontend/src/components/SessionDetails.tsx` | Secondary post-session debug/details surface for transcript text and raw mic audio |
| `frontend/src/lib/todoDiff.ts` | Best-effort snapshot comparison helper for highlighting new or changed todos |
| `frontend/src/lib/todoDiff.test.ts` | Unit tests for snapshot comparison logic |

### Frontend — Modified files

| File | Change |
|------|--------|
| `frontend/src/App.tsx` | Replace the barebones layout with the phone-shell UI and state routing from the reference |
| `frontend/src/App.test.tsx` | Update app-level state rendering tests for the new shell, empty states, warnings, and post-session result state |
| `frontend/src/components/RecordButton.tsx` | Rebuild as the bottom dock with waveform, state-aware CTA labels, and disabled connect/extract states |
| `frontend/src/components/RecordButton.test.tsx` | Update button copy and recording/extracting behavior tests |
| `frontend/src/components/TodoList.tsx` | Remove the old heading and add transient change highlighting behavior |
| `frontend/src/components/TodoList.test.tsx` | Remove count-heading expectations and add highlight behavior coverage |
| `frontend/src/components/TodoCard.tsx` | Rebuild cards to match the reference card layout and metadata chips |
| `frontend/src/components/TodoCard.test.tsx` | Update rendering expectations for the new card presentation |
| `frontend/src/components/TodoSkeleton.tsx` | Restyle skeletons so they match the new card system |
| `frontend/src/components/TodoSkeleton.test.tsx` | Keep skeleton-count coverage against the new structure |
| `frontend/src/index.css` | Import reference fonts and add shared motion/theme classes (`spring-entry`, `wave-bar`, `flash-orange`, shell styling) |

### Frontend — Leave untouched

| File | Reason |
|------|--------|
| `frontend/src/hooks/useTranscript.ts` | The hook contract already exposes the states and data needed for this redesign |
| `frontend/src/components/TranscriptArea.tsx` | No longer used in the main flow; leave untouched unless cleanup is needed at the end |

---

## Task 1: Rebuild the bottom session dock

**Files:**
- Create: `frontend/src/components/AppIcon.tsx`
- Modify: `frontend/src/components/RecordButton.tsx`
- Modify: `frontend/src/components/RecordButton.test.tsx`
- Modify: `frontend/src/index.css`

`RecordButton` currently renders a plain text button. This task turns it into the bottom dock from the reference HTML and adds the missing `connecting` state treatment.

- [ ] **Step 1: Write the failing dock tests**

Update `frontend/src/components/RecordButton.test.tsx` so it matches the approved state mapping:

```tsx
import { render, screen } from "@testing-library/react";
import { RecordButton } from "./RecordButton";

describe("RecordButton", () => {
  it("renders Start Session when idle", () => {
    render(<RecordButton status="idle" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Start Session");
  });

  it("renders Connecting... as a disabled button", () => {
    render(<RecordButton status="connecting" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Connecting...");
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("renders the listening UI and Finish Session while recording", () => {
    render(<RecordButton status="recording" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByText("Listening now...")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveTextContent("Finish Session");
  });

  it("renders Extracting... as a disabled button", () => {
    render(<RecordButton status="extracting" onStart={() => {}} onStop={() => {}} />);
    expect(screen.getByRole("button")).toHaveTextContent("Extracting...");
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the dock tests to verify they fail**

Run: `cd frontend && pnpm test:run -- src/components/RecordButton.test.tsx`

Expected: FAIL because the component still renders `Start` / `Stop` and has no `connecting` dock UI.

- [ ] **Step 3: Implement the dock and shared inline icons**

Create `frontend/src/components/AppIcon.tsx` with a tiny inline SVG switch instead of adding a new package:

```tsx
import { cn } from "@/lib/utils";

type IconName = "mic" | "calendar" | "tag" | "user";

export function AppIcon({
  name,
  className,
}: {
  name: IconName;
  className?: string;
}) {
  const paths = {
    mic: (
      <>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M6 10a6 6 0 0 0 12 0" />
        <path d="M12 16v5" />
        <path d="M8 21h8" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4" />
        <path d="M8 3v4" />
        <path d="M3 10h18" />
      </>
    ),
    tag: (
      <>
        <path d="M20 10.5 12.5 18a2.1 2.1 0 0 1-3 0L4 12.5V4h8.5l7.5 7.5a2.1 2.1 0 0 1 0 3Z" />
        <circle cx="9" cy="9" r="1" fill="currentColor" stroke="none" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20a7 7 0 0 1 14 0" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className={cn("shrink-0", className)}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
```

Replace `frontend/src/components/RecordButton.tsx` with the dock layout from the reference:

```tsx
import type { Status } from "../hooks/useTranscript";
import { AppIcon } from "./AppIcon";

interface Props {
  status: Status;
  onStart: () => void;
  onStop: () => void;
}

export function RecordButton({ status, onStart, onStop }: Props) {
  const isRecording = status === "recording";
  const isDisabled = status === "connecting" || status === "extracting";
  const label =
    status === "idle"
      ? "Start Session"
      : status === "connecting"
        ? "Connecting..."
        : status === "recording"
          ? "Finish Session"
          : "Extracting...";

  const handleClick = status === "idle" ? onStart : status === "recording" ? onStop : undefined;

  return (
    <div className="voice-dock">
      {isRecording && (
        <div className="voice-listening-ui">
          <div className="voice-waveform" aria-hidden="true">
            {Array.from({ length: 9 }).map((_, index) => (
              <span key={index} className="wave-bar" />
            ))}
          </div>
          <p className="voice-listening-copy">Listening now...</p>
        </div>
      )}

      <button
        type="button"
        onClick={handleClick}
        disabled={isDisabled}
        className="voice-primary-button"
      >
        {status === "idle" && <AppIcon name="mic" className="size-5" />}
        <span>{label}</span>
      </button>
    </div>
  );
}
```

Add the shared motion and dock classes to `frontend/src/index.css`:

```css
@import url("https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&family=Manrope:wght@400;500;600&display=swap");
@import "tailwindcss";

:root {
  --voice-bg: #fdf8f6;
  --voice-accent: #e26d5c;
  --voice-accent-hover: #d55f4e;
  --spring-easing: cubic-bezier(0.34, 1.56, 0.64, 1);
}

body {
  font-family: "Manrope", sans-serif;
  background: var(--voice-bg);
}

h1,
h2,
h3 {
  font-family: "Archivo", sans-serif;
}

@keyframes wave {
  0%,
  100% { height: 8px; }
  50% { height: 24px; }
}

.wave-bar {
  width: 3px;
  height: 8px;
  border-radius: 999px;
  background: var(--voice-accent);
  animation: wave 1s ease-in-out infinite;
}
```

- [ ] **Step 4: Run the dock tests to verify they pass**

Run: `cd frontend && pnpm test:run -- src/components/RecordButton.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit the dock slice**

```bash
git add frontend/src/components/AppIcon.tsx frontend/src/components/RecordButton.tsx frontend/src/components/RecordButton.test.tsx frontend/src/index.css
git commit -m "feat: rebuild Voice-Todos session dock UI"
```

---

## Task 2: Rebuild the todo feed and add best-effort change highlighting

**Files:**
- Create: `frontend/src/lib/todoDiff.ts`
- Create: `frontend/src/lib/todoDiff.test.ts`
- Modify: `frontend/src/components/TodoList.tsx`
- Modify: `frontend/src/components/TodoList.test.tsx`
- Modify: `frontend/src/components/TodoCard.tsx`
- Modify: `frontend/src/components/TodoCard.test.tsx`
- Modify: `frontend/src/components/TodoSkeleton.tsx`
- Modify: `frontend/src/components/TodoSkeleton.test.tsx`
- Modify: `frontend/src/index.css`

This task matches the reference card/feed layout and implements the subtle warm highlight when new or changed todos arrive.

- [ ] **Step 1: Write failing helper and component tests**

Create `frontend/src/lib/todoDiff.test.ts`:

```tsx
import { describe, expect, it } from "vitest";
import { getChangedTodoIndices } from "./todoDiff";

describe("getChangedTodoIndices", () => {
  it("marks all todos as changed on first render", () => {
    expect(getChangedTodoIndices([], [{ text: "Buy milk" }])).toEqual([0]);
  });

  it("marks an updated todo at the same index as changed", () => {
    expect(
      getChangedTodoIndices(
        [{ text: "Buy milk" }],
        [{ text: "Buy oat milk" }]
      )
    ).toEqual([0]);
  });

  it("does not mark unchanged todos", () => {
    expect(
      getChangedTodoIndices(
        [{ text: "Buy milk" }],
        [{ text: "Buy milk" }]
      )
    ).toEqual([]);
  });
});
```

Update `frontend/src/components/TodoList.test.tsx`:

```tsx
it("does not render the old extracted count heading", () => {
  render(<TodoList todos={[{ text: "Task A" }]} />);
  expect(screen.queryByText(/Extracted Todos/)).not.toBeInTheDocument();
});

it("briefly highlights changed todos after rerender", () => {
  const { rerender } = render(<TodoList todos={[{ text: "Buy milk" }]} />);
  rerender(<TodoList todos={[{ text: "Buy oat milk" }]} />);
  expect(screen.getByTestId("todo-card-0")).toHaveAttribute("data-highlighted", "true");
});
```

Update `frontend/src/components/TodoCard.test.tsx` so the assertions look for clean chip text instead of emoji prefixes:

```tsx
it("renders metadata chips when fields are present", () => {
  render(
    <TodoCard
      todo={{
        text: "Review budget",
        dueDate: "2026-03-27",
        priority: "high",
        category: "finance",
        assignTo: "Marie",
      }}
    />
  );

  expect(screen.getByText("2026-03-27")).toBeInTheDocument();
  expect(screen.getByText(/high/i)).toBeInTheDocument();
  expect(screen.getByText("finance")).toBeInTheDocument();
  expect(screen.getByText("Marie")).toBeInTheDocument();
});
```

Keep `frontend/src/components/TodoSkeleton.test.tsx` focused on three pulse cards.

- [ ] **Step 2: Run the feed tests to verify they fail**

Run: `cd frontend && pnpm test:run -- src/lib/todoDiff.test.ts src/components/TodoList.test.tsx src/components/TodoCard.test.tsx src/components/TodoSkeleton.test.tsx`

Expected: FAIL because the helper does not exist, the old list heading is still rendered, and todo cards do not expose highlight state.

- [ ] **Step 3: Implement the helper, cards, and skeletons**

Create `frontend/src/lib/todoDiff.ts`:

```tsx
import type { Todo } from "../types";

function todosEqual(left: Todo | undefined, right: Todo | undefined) {
  return (
    left?.text === right?.text &&
    left?.priority === right?.priority &&
    left?.category === right?.category &&
    left?.dueDate === right?.dueDate &&
    left?.notification === right?.notification &&
    left?.assignTo === right?.assignTo
  );
}

export function getChangedTodoIndices(previous: Todo[], next: Todo[]) {
  return next.reduce<number[]>((indices, todo, index) => {
    if (!todosEqual(previous[index], todo)) {
      indices.push(index);
    }
    return indices;
  }, []);
}
```

Update `frontend/src/components/TodoList.tsx` so it owns the transient highlight state:

```tsx
import { useEffect, useRef, useState } from "react";
import type { Todo } from "../types";
import { getChangedTodoIndices } from "../lib/todoDiff";
import { TodoCard } from "./TodoCard";

export function TodoList({ todos }: { todos: Todo[] }) {
  const previousTodosRef = useRef<Todo[]>([]);
  const [highlightedIndices, setHighlightedIndices] = useState<number[]>([]);

  useEffect(() => {
    const nextHighlights = getChangedTodoIndices(previousTodosRef.current, todos);
    previousTodosRef.current = todos;

    if (nextHighlights.length === 0) return;

    setHighlightedIndices(nextHighlights);
    const timeout = window.setTimeout(() => setHighlightedIndices([]), 1000);
    return () => window.clearTimeout(timeout);
  }, [todos]);

  if (todos.length === 0) return null;

  return (
    <div className="mt-4 flex flex-col gap-4">
      {todos.map((todo, index) => (
        <TodoCard
          key={index}
          todo={todo}
          highlighted={highlightedIndices.includes(index)}
          index={index}
        />
      ))}
    </div>
  );
}
```

Update `frontend/src/components/TodoCard.tsx` to match the reference structure:

```tsx
import type { Todo } from "../types";
import { cn } from "@/lib/utils";
import { AppIcon } from "./AppIcon";

interface Props {
  todo: Todo;
  highlighted?: boolean;
  index?: number;
}

export function TodoCard({ todo, highlighted = false, index = 0 }: Props) {
  return (
    <article
      data-testid={`todo-card-${index}`}
      data-highlighted={highlighted ? "true" : "false"}
      className={cn("spring-entry voice-todo-card", highlighted && "flash-orange")}
    >
      <div className="voice-todo-circle" />
      <div className="min-w-0 flex-1 space-y-2">
        <h3 className="voice-todo-title">{todo.text}</h3>
        <div className="flex flex-wrap gap-2">
          {todo.dueDate && <span className="voice-meta-chip"><AppIcon name="calendar" className="size-3.5" />{todo.dueDate}</span>}
          {todo.priority && <span className="voice-meta-chip voice-meta-chip-priority">{todo.priority}</span>}
          {todo.category && <span className="voice-meta-chip"><AppIcon name="tag" className="size-3.5" />{todo.category}</span>}
          {todo.assignTo && <span className="voice-meta-chip"><AppIcon name="user" className="size-3.5" />{todo.assignTo}</span>}
          {todo.notification && <span className="voice-meta-chip voice-meta-chip-notification">{todo.notification}</span>}
        </div>
      </div>
    </article>
  );
}
```

Update `frontend/src/components/TodoSkeleton.tsx` so the skeleton cards visually match `voice-todo-card` rather than shadcn cards.

Add the feed/card classes and highlight animation to `frontend/src/index.css`:

```css
@keyframes spring-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes flash-orange-anim {
  0% { background-color: transparent; }
  30% { background-color: rgb(226 109 92 / 0.15); }
  100% { background-color: transparent; }
}

.spring-entry {
  animation: spring-in 0.6s var(--spring-easing) both;
}

.flash-orange {
  animation: flash-orange-anim 1s ease-out both;
}

.voice-todo-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  border-radius: 24px;
  border: 1px solid rgb(244 244 245);
  background: white;
  padding: 1.25rem;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

.voice-todo-circle {
  margin-top: 0.25rem;
  height: 1.5rem;
  width: 1.5rem;
  flex-shrink: 0;
  border-radius: 999px;
  border: 2px solid rgb(228 228 231);
}

.voice-todo-title {
  color: rgb(39 39 42);
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
}

.voice-meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 0.75rem;
  background: rgb(250 250 250);
  padding: 0.375rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: rgb(113 113 122);
}
```

- [ ] **Step 4: Run the feed tests to verify they pass**

Run: `cd frontend && pnpm test:run -- src/lib/todoDiff.test.ts src/components/TodoList.test.tsx src/components/TodoCard.test.tsx src/components/TodoSkeleton.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit the feed slice**

```bash
git add frontend/src/lib/todoDiff.ts frontend/src/lib/todoDiff.test.ts frontend/src/components/TodoList.tsx frontend/src/components/TodoList.test.tsx frontend/src/components/TodoCard.tsx frontend/src/components/TodoCard.test.tsx frontend/src/components/TodoSkeleton.tsx frontend/src/components/TodoSkeleton.test.tsx frontend/src/index.css
git commit -m "feat: match Voice-Todos feed to reference cards"
```

---

## Task 3: Rebuild the app shell and add the secondary session details surface

**Files:**
- Create: `frontend/src/components/SessionDetails.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/index.css`

This task rebuilds the screen shell in `App.tsx`, removes the transcript from the main flow, keeps warnings in the feed, and puts transcript/raw audio behind a secondary details surface outside the phone-shell UI.

- [ ] **Step 1: Write the failing app-shell tests**

Update `frontend/src/App.test.tsx` to reflect the approved design:

```tsx
const baseHook = {
  status: "idle" as const,
  finalText: "",
  interimText: "",
  todos: [],
  micRecordingUrl: null,
  warningMessage: null,
  start: vi.fn(),
  stop: vi.fn(),
};

it("renders the phone-shell empty state on first load", () => {
  mockUseTranscript.mockReturnValue(baseHook);
  render(<App />);
  expect(screen.getByText("Voice-Todos")).toBeInTheDocument();
  expect(screen.getByText("Start speaking...")).toBeInTheDocument();
  expect(screen.getByRole("button")).toHaveTextContent("Start Session");
});

it("keeps todos visible while recording", () => {
  mockUseTranscript.mockReturnValue({
    ...baseHook,
    status: "recording",
    todos: [{ text: "Draft agenda" }],
  });
  render(<App />);
  expect(screen.getByText("Draft agenda")).toBeInTheDocument();
  expect(screen.getByText("Listening now...")).toBeInTheDocument();
});

it("shows skeleton cards only when extracting without todos", () => {
  mockUseTranscript.mockReturnValue({
    ...baseHook,
    status: "extracting",
    todos: [],
  });
  const { container } = render(<App />);
  expect(container.querySelectorAll("[class*='animate-pulse']")).toHaveLength(3);
  expect(screen.getByRole("button")).toHaveTextContent("Extracting...");
});

it("shows a post-session no-todos state after a finished recording", () => {
  mockUseTranscript.mockReturnValue({
    ...baseHook,
    finalText: "Remember to think about the roadmap",
  });
  render(<App />);
  expect(screen.getByText("No todos found in this recording.")).toBeInTheDocument();
});

it("renders session details when a recording URL exists", () => {
  mockUseTranscript.mockReturnValue({
    ...baseHook,
    micRecordingUrl: "blob:recording",
    finalText: "Call Marie tomorrow",
  });
  render(<App />);
  expect(screen.getByText("Session details")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the app-shell tests to verify they fail**

Run: `cd frontend && pnpm test:run -- src/App.test.tsx`

Expected: FAIL because `App.tsx` still renders the old prototype layout and inline transcript/debug sections.

- [ ] **Step 3: Implement the phone-shell app and the details surface**

Create `frontend/src/components/SessionDetails.tsx`:

```tsx
interface Props {
  finalText: string;
  micRecordingUrl: string | null;
}

export function SessionDetails({ finalText, micRecordingUrl }: Props) {
  if (!finalText && !micRecordingUrl) return null;

  return (
    <details className="voice-session-details">
      <summary>Session details</summary>
      {finalText && <p className="voice-session-transcript">{finalText}</p>}
      {micRecordingUrl && <audio controls src={micRecordingUrl} className="w-full" />}
    </details>
  );
}
```

Replace `frontend/src/App.tsx` with the reference-driven shell:

```tsx
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

  const hasSessionArtifacts = Boolean(finalText || micRecordingUrl || warningMessage || todos.length);
  const showInitialEmptyState = status === "idle" && !hasSessionArtifacts;
  const showNoTodosState = status === "idle" && hasSessionArtifacts && todos.length === 0 && !warningMessage;

  return (
    <main className="voice-page-shell">
      <section className="voice-device-shell">
        <header className="voice-header">
          <h1>Voice-Todos</h1>
        </header>

        <div id="task-container" className="voice-task-container">
          {showInitialEmptyState && (
            <div className="voice-empty-state">
              <div className="voice-empty-illustration">
                <AppIcon name="mic" className="size-10 text-[var(--voice-accent)]" />
              </div>
              <h2>Start speaking...</h2>
              <p>Your voice will be turned into tasks in real time.</p>
            </div>
          )}

          {warningMessage && <div className="voice-warning-card">{warningMessage}</div>}
          {todos.length > 0 && <TodoList todos={todos} />}
          {status === "extracting" && todos.length === 0 && <TodoSkeleton />}
          {showNoTodosState && <div className="voice-result-state">No todos found in this recording.</div>}
        </div>

        <RecordButton status={status} onStart={start} onStop={stop} />
      </section>

      <SessionDetails finalText={finalText} micRecordingUrl={micRecordingUrl} />
    </main>
  );
}
```

Add the shell classes to `frontend/src/index.css`:

```css
.voice-page-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.voice-device-shell {
  position: relative;
  display: flex;
  height: 800px;
  width: 100%;
  max-width: 28rem;
  flex-direction: column;
  overflow: hidden;
  border-radius: 40px;
  border: 1px solid white;
  background: white;
  box-shadow: 0 20px 50px rgb(0 0 0 / 0.05);
}

.voice-header {
  padding: 3rem 2rem 1.5rem;
}

.voice-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: rgb(39 39 42);
  letter-spacing: -0.02em;
}

.voice-task-container {
  flex: 1;
  overflow-y: auto;
  padding: 0 2rem 8rem;
}

.voice-empty-state,
.voice-result-state {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.voice-empty-illustration {
  margin-bottom: 0.5rem;
  display: flex;
  height: 6rem;
  width: 6rem;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgb(255 247 237);
}

.voice-warning-card,
.voice-session-details {
  width: 100%;
  max-width: 28rem;
  border-radius: 1rem;
  background: rgb(255 247 237);
  color: rgb(154 52 18);
  padding: 1rem;
}
```

- [ ] **Step 4: Run the app-shell tests to verify they pass**

Run: `cd frontend && pnpm test:run -- src/App.test.tsx`

Expected: PASS

- [ ] **Step 5: Run the focused frontend suite for the full item**

Run: `cd frontend && pnpm test:run -- src/App.test.tsx src/components/RecordButton.test.tsx src/components/TodoList.test.tsx src/components/TodoCard.test.tsx src/components/TodoSkeleton.test.tsx src/lib/todoDiff.test.ts`

Expected: PASS

- [ ] **Step 6: Commit the app-shell slice**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/SessionDetails.tsx frontend/src/index.css
git commit -m "feat: rebuild Voice-Todos app shell from reference"
```

---

## Task 4: Full verification against the approved reference

**Files:**
- Verify: `docs/superpowers/specs/2026-03-24-item4-ui-redesign-design.md`
- Verify: `docs/references/2026-03-24-item4-motion-light-reference.html`
- Verify: `frontend/src/App.tsx`
- Verify: `frontend/src/components/RecordButton.tsx`
- Verify: `frontend/src/components/TodoList.tsx`
- Verify: `frontend/src/components/TodoCard.tsx`
- Verify: `frontend/src/components/TodoSkeleton.tsx`
- Verify: `frontend/src/index.css`
- Modify as needed: the frontend files above if any mismatch or test failure remains

This final task is the guardrail against drift. The engineer should explicitly compare the implemented UI against the checked-in HTML reference before calling the work done.

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd frontend && pnpm test:run`

Expected: PASS

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && pnpm build`

Expected: PASS

- [ ] **Step 3: Compare the implementation against the checked-in reference HTML**

Open and compare:

- `docs/references/2026-03-24-item4-motion-light-reference.html`
- `docs/superpowers/specs/2026-03-24-item4-ui-redesign-design.md`
- the live implementation in `frontend/src/App.tsx`, `frontend/src/components/RecordButton.tsx`, `frontend/src/components/TodoList.tsx`, and `frontend/src/components/TodoCard.tsx`

Check specifically:

- page framing and phone-shell proportions
- header simplicity
- empty-state copy
- bottom dock structure
- waveform treatment
- card shape and metadata chips
- warm palette and motion classes
- `Voice-Todos` title adaptation
- absence of the decorative top-right button

- [ ] **Step 4: Fix any mismatch found during verification and rerun tests/build**

If Step 3 exposes a visual or state-mapping drift, patch the relevant frontend file, then rerun:

```bash
cd frontend && pnpm test:run && pnpm build
```

Expected: PASS

- [ ] **Step 5: Commit the finished UI refresh**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/AppIcon.tsx frontend/src/components/RecordButton.tsx frontend/src/components/RecordButton.test.tsx frontend/src/components/SessionDetails.tsx frontend/src/components/TodoList.tsx frontend/src/components/TodoList.test.tsx frontend/src/components/TodoCard.tsx frontend/src/components/TodoCard.test.tsx frontend/src/components/TodoSkeleton.tsx frontend/src/components/TodoSkeleton.test.tsx frontend/src/lib/todoDiff.ts frontend/src/lib/todoDiff.test.ts frontend/src/index.css
git commit -m "feat: implement item 4 Voice-Todos UI redesign"
```

---

## Notes For The Implementer

- Keep `RecordButton` waveform visible only while `status === "recording"` so the UI does not imply active listening during `connecting` or `extracting`.
- Use best-effort index-based diffing for highlight behavior. Do not try to invent stable todo identities on the frontend.
- Keep warnings inside the phone-shell feed, but keep transcript/raw audio outside the shell in `SessionDetails`.
- Do not reintroduce the old transcript-first layout or the `Extracted Todos (N)` heading.
