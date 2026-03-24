# Item 3: Todos While Speaking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Todos appear on screen while the user is still speaking, extracted incrementally from the accumulating transcript.

**Architecture:** A new `ExtractionLoop` class watches for Soniox endpoint tokens and token-count thresholds, triggering LLM extraction on the full transcript with previous todos as context. The extraction prompt instructs Gemini to return updated snapshots. Logfire provides full server-side tracing. The frontend receives `todos` messages during recording (not just on stop).

**Tech Stack:** FastAPI, PydanticAI, Gemini 3 Flash, Logfire, Soniox, React 19, Vitest

**Spec:** `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`

---

## Prerequisites

**Fixtures to record before starting:** The following audio fixtures must exist in `backend/tests/fixtures/`. Ask the user to record them if missing.

| Fixture | What to say | Purpose |
|---|---|---|
| `call-mom-memo-supplier` | Already exists | Multiple distinct todos with natural pauses |
| `refine-todo` | Say a todo, pause, then add detail to it. E.g., "I need to buy milk... actually make that oat milk from the organic store" | Tests refinement |
| `continuous-speech` | ~30s of uninterrupted speech with todos, minimal pauses | Tests token-count fallback |

---

## File Map

### Backend — New files

| File | Responsibility |
|------|---------------|
| `backend/app/extraction_loop.py` | `ExtractionLoop` class — trigger logic, dirty flag, concurrent extraction guard |
| `backend/tests/test_extraction_loop.py` | Unit tests for ExtractionLoop (mocked extract_todos) |
| `backend/tests/test_e2e.py` | End-to-end behavioral tests (real Soniox + Gemini, opt-in) |

### Backend — Modified files

| File | Change |
|------|--------|
| `backend/app/transcript_accumulator.py` | Detect `<end>` tokens, return structured result from `apply_event` |
| `backend/app/extract.py` | Accept `previous_todos` parameter, update prompt for incremental extraction |
| `backend/app/ws.py` | Instantiate ExtractionLoop, add Soniox endpoint config, wire triggers, update stop flow |
| `backend/app/main.py` | Add Logfire setup (configure, instrument FastAPI + PydanticAI) |
| `backend/pyproject.toml` | Add `logfire[fastapi]` dependency |
| `backend/tests/test_ws.py` | Update stop tests for new ExtractionLoop-based flow |
| `backend/tests/test_extract.py` | Add tests for previous_todos parameter |
| `backend/tests/test_replay.py` | Verify `<end>` token handling in replay fixtures |

### Frontend — Modified files

| File | Change |
|------|--------|
| `frontend/src/hooks/useTranscript.ts` | Remove `"extracting"` from mid-session flow, keep for final sweep only |

---

## Task 1: Extend TranscriptAccumulator to detect `<end>` tokens

**Files:**
- Modify: `backend/app/transcript_accumulator.py`
- Modify: `backend/tests/test_replay.py`

The accumulator currently detects `<fin>` tokens but not `<end>` tokens. We need `apply_event` to return structured information including whether an endpoint was detected.

- [ ] **Step 1: Write failing test for `<end>` detection**

Create a new test file `backend/tests/test_transcript_accumulator.py`:

```python
from app.transcript_accumulator import TranscriptAccumulator


class TestApplyEvent:
    def test_end_token_is_detected(self):
        """apply_event returns has_endpoint=True when <end> token is present."""
        acc = TranscriptAccumulator()
        result = acc.apply_event({
            "tokens": [
                {"text": "hello ", "is_final": True},
                {"text": "<end>", "is_final": True},
            ]
        })
        assert result.has_endpoint is True

    def test_end_token_is_filtered_from_tokens(self):
        """<end> token does not appear in the returned token list."""
        acc = TranscriptAccumulator()
        result = acc.apply_event({
            "tokens": [
                {"text": "hello ", "is_final": True},
                {"text": "<end>", "is_final": True},
            ]
        })
        assert all(t["text"] != "<end>" for t in result.tokens)

    def test_end_token_is_not_accumulated(self):
        """<end> token text does not end up in the transcript."""
        acc = TranscriptAccumulator()
        acc.apply_event({
            "tokens": [
                {"text": "hello ", "is_final": True},
                {"text": "<end>", "is_final": True},
            ]
        })
        assert acc.full_text == "hello "

    def test_no_endpoint_without_end_token(self):
        """Regular tokens do not set has_endpoint."""
        acc = TranscriptAccumulator()
        result = acc.apply_event({
            "tokens": [{"text": "hello ", "is_final": True}]
        })
        assert result.has_endpoint is False

    def test_final_token_count(self):
        """Result includes count of new final tokens (excluding <end>)."""
        acc = TranscriptAccumulator()
        result = acc.apply_event({
            "tokens": [
                {"text": "hello ", "is_final": True},
                {"text": "world ", "is_final": True},
                {"text": "<end>", "is_final": True},
            ]
        })
        assert result.final_token_count == 2

    def test_fin_behavior_preserved(self):
        """Existing <fin> handling still works."""
        acc = TranscriptAccumulator()
        acc.apply_event({
            "tokens": [{"text": "interim", "is_final": False}]
        })
        assert acc.interim_parts == ["interim"]

        result = acc.apply_event({
            "tokens": [{"text": "<fin>", "is_final": True}]
        })
        assert acc.interim_parts == []
        assert result.has_endpoint is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_transcript_accumulator.py -v`
Expected: FAIL — `apply_event` returns a list, not an object with `has_endpoint`

- [ ] **Step 3: Implement structured return type**

Modify `backend/app/transcript_accumulator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApplyEventResult:
    tokens: list[dict[str, str | bool]]
    has_endpoint: bool
    final_token_count: int


@dataclass
class TranscriptAccumulator:
    final_parts: list[str] = field(default_factory=list)
    interim_parts: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.final_parts.clear()
        self.interim_parts.clear()

    def apply_event(self, event: dict[str, Any]) -> ApplyEventResult:
        raw_tokens = [
            token
            for token in event.get("tokens", [])
            if isinstance(token, dict) and isinstance(token.get("text"), str)
        ]
        has_fin = any(token["text"] == "<fin>" for token in raw_tokens)
        has_end = any(token["text"] == "<end>" for token in raw_tokens)
        tokens = [
            token for token in raw_tokens
            if token["text"] not in ("<fin>", "<end>")
        ]

        if has_fin:
            self.interim_parts.clear()

        final_token_count = 0
        if tokens:
            for token in tokens:
                if token.get("is_final", False):
                    self.final_parts.append(token["text"])
                    final_token_count += 1

            interim_text = "".join(
                token["text"] for token in tokens if not token.get("is_final", False)
            )
            if interim_text:
                self.interim_parts.clear()
                self.interim_parts.append(interim_text)

        return ApplyEventResult(
            tokens=[
                {"text": token["text"], "is_final": token.get("is_final", False)}
                for token in tokens
            ],
            has_endpoint=has_end,
            final_token_count=final_token_count,
        )

    @property
    def full_text(self) -> str:
        transcript = "".join(self.final_parts)
        if self.interim_parts:
            transcript += "".join(self.interim_parts)
        return transcript
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_transcript_accumulator.py -v`
Expected: all 6 PASS

- [ ] **Step 5: Update callers for new return type**

`ws.py` line 37 calls `transcript.apply_event(event)` and expects a list of tokens. Update `_relay_soniox_to_browser` in `backend/app/ws.py`:

Change line 37:
```python
            tokens = transcript.apply_event(event)
```
to:
```python
            result = transcript.apply_event(event)
            tokens = result.tokens
```

Also update `_accumulate_transcript` in `backend/tests/test_replay.py` line 37-40 — it calls `apply_event` but discards the return value, so no change needed there.

- [ ] **Step 6: Run all existing tests to verify nothing breaks**

Run: `cd backend && uv run pytest -v`
Expected: all existing tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/transcript_accumulator.py backend/app/ws.py backend/tests/test_transcript_accumulator.py
git commit -m "feat: extend TranscriptAccumulator to detect <end> tokens"
```

---

## Task 2: Add `previous_todos` to extract.py

**Files:**
- Modify: `backend/app/extract.py`
- Modify: `backend/tests/test_extract.py`

- [ ] **Step 1: Write failing test for previous_todos in prompt**

Add to `backend/tests/test_extract.py`:

```python
@pytest.mark.asyncio
async def test_extract_todos_includes_previous_todos_in_prompt():
    """When previous_todos is provided, they appear in the prompt sent to the agent."""
    from app.extract import extract_todos

    previous = [
        Todo(text="Buy milk", priority="high"),
        Todo(text="Call the dentist", due_date="2026-03-25"),
    ]
    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=previous)))
    )
    reference_dt = datetime(2026, 3, 24, 10, 0, tzinfo=UTC)

    with patch("app.extract._get_agent", return_value=fake_agent):
        await extract_todos(
            "I need to buy milk and call the dentist.",
            previous_todos=previous,
            reference_dt=reference_dt,
        )

    sent_prompt = fake_agent.run.await_args.args[0]
    assert "Previously extracted todos:" in sent_prompt
    assert "Buy milk" in sent_prompt
    assert "priority: high" in sent_prompt
    assert "Call the dentist" in sent_prompt
    assert "due: 2026-03-25" in sent_prompt


@pytest.mark.asyncio
async def test_extract_todos_no_previous_section_when_empty():
    """When previous_todos is empty or None, no 'Previously extracted' section appears."""
    from app.extract import extract_todos

    fake_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output=ExtractionResult(todos=[])))
    )
    reference_dt = datetime(2026, 3, 24, 10, 0, tzinfo=UTC)

    with patch("app.extract._get_agent", return_value=fake_agent):
        await extract_todos("Buy milk.", previous_todos=[], reference_dt=reference_dt)

    sent_prompt = fake_agent.run.await_args.args[0]
    assert "Previously extracted todos:" not in sent_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_extract.py::test_extract_todos_includes_previous_todos_in_prompt tests/test_extract.py::test_extract_todos_no_previous_section_when_empty -v`
Expected: FAIL — `extract_todos` does not accept `previous_todos`

- [ ] **Step 3: Implement previous_todos support**

Modify `backend/app/extract.py`:

Update `_SYSTEM_PROMPT` — append these rules:

```python
_SYSTEM_PROMPT = (
    "You extract actionable todo items from a voice transcript.\n\n"
    "Rules:\n"
    "- Extract only clearly actionable tasks, not observations or commentary.\n"
    "- Write each todo as a clean, concise imperative sentence (not verbatim speech).\n"
    "- Only set optional fields "
    "(priority, category, due_date, notification, assign_to) "
    "when the speaker clearly indicates them.\n"
    "- priority: 'high' for urgent/important emphasis, 'medium' for moderate, "
    "'low' for minor.\n"
    "- due_date: extract dates/deadlines as ISO format (YYYY-MM-DD). "
    "Resolve relative dates "
    "(e.g., 'tomorrow', 'next Friday') relative to the current date.\n"
    "- notification: extract reminder times as ISO datetime "
    "(YYYY-MM-DDTHH:MM:SS).\n"
    "- assign_to: extract person names when the speaker delegates a task.\n"
    "- category: infer a short category label only when the context is clear.\n"
    "- If no actionable todos are found, return an empty list.\n"
    "\n"
    "Incremental extraction rules:\n"
    "- You may receive a list of previously extracted todos. "
    "Return the updated complete list.\n"
    "- Preserve the order of existing todos where that order still makes sense. "
    "Append genuinely new todos at the end.\n"
    "- If new speech adds details to an existing todo, update it in place.\n"
    "- If later context shows an earlier todo was over-split, duplicated, misheard, "
    "or should be absorbed into another todo, merge or remove it.\n"
    "- Explicit cancellation is one reason to remove a todo, but not the only one.\n"
    "- If no previous todos are provided, extract from scratch.\n"
)
```

Add a helper to format previous todos:

```python
def _format_previous_todos(todos: list[Todo]) -> str:
    lines = []
    for i, todo in enumerate(todos, 1):
        parts = [todo.text]
        if todo.priority:
            parts.append(f"priority: {todo.priority}")
        if todo.due_date:
            parts.append(f"due: {todo.due_date.isoformat()}")
        if todo.category:
            parts.append(f"category: {todo.category}")
        if todo.assign_to:
            parts.append(f"assign to: {todo.assign_to}")
        if todo.notification:
            parts.append(f"notification: {todo.notification.isoformat()}")
        text = parts[0]
        meta = ", ".join(parts[1:])
        if meta:
            lines.append(f"{i}. {text} ({meta})")
        else:
            lines.append(f"{i}. {text}")
    return "\n".join(lines)
```

Update `_build_extraction_input`:

```python
def _build_extraction_input(
    transcript: str,
    reference_dt: datetime,
    previous_todos: list[Todo] | None = None,
) -> str:
    timezone_name = reference_dt.tzname() or "UTC"
    parts = [
        f"Current local datetime: {reference_dt.isoformat()}",
        f"Current local date: {reference_dt.date().isoformat()}",
        f"Current timezone: {timezone_name}",
        "",
    ]
    if previous_todos:
        parts.append("Previously extracted todos:")
        parts.append(_format_previous_todos(previous_todos))
        parts.append("")
    parts.append("Transcript:")
    parts.append(transcript)
    return "\n".join(parts)
```

Update `extract_todos` signature:

```python
async def extract_todos(
    transcript: str,
    *,
    previous_todos: list[Todo] | None = None,
    reference_dt: datetime | None = None,
) -> list[Todo]:
    """Extract structured todos from a transcript using Gemini."""
    if not transcript.strip():
        return []

    if reference_dt is None:
        reference_dt = datetime.now().astimezone()

    agent = _get_agent()
    result = await agent.run(
        _build_extraction_input(transcript, reference_dt, previous_todos)
    )
    return result.output.todos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_extract.py -v`
Expected: all tests pass (new + existing)

- [ ] **Step 5: Commit**

```bash
git add backend/app/extract.py backend/tests/test_extract.py
git commit -m "feat: add previous_todos support to extract_todos for incremental extraction"
```

---

## Task 3: Build ExtractionLoop

**Files:**
- Create: `backend/app/extraction_loop.py`
- Create: `backend/tests/test_extraction_loop.py`

This is the core new component. All tests use a mock `extract_todos` — no API keys needed.

- [ ] **Step 1: Write failing test — endpoint triggers extraction**

Create `backend/tests/test_extraction_loop.py`:

```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from app.extraction_loop import ExtractionLoop
from app.models import Todo
from app.transcript_accumulator import TranscriptAccumulator


@pytest.fixture
def transcript():
    acc = TranscriptAccumulator()
    return acc


@pytest.fixture
def send_fn():
    return AsyncMock()


@pytest.fixture
def mock_extract():
    return AsyncMock(return_value=[Todo(text="Buy milk")])


@pytest.mark.asyncio
async def test_endpoint_triggers_extraction(transcript, send_fn, mock_extract):
    """on_endpoint triggers extraction and sends todos."""
    transcript.final_parts.append("I need to buy milk. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=mock_extract,
        token_threshold=30,
    )
    await loop.on_endpoint()
    # Allow the extraction task to complete
    await asyncio.sleep(0.05)

    mock_extract.assert_awaited_once()
    call_kwargs = mock_extract.await_args
    assert "buy milk" in call_kwargs.args[0].lower()
    send_fn.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_extraction_loop.py::test_endpoint_triggers_extraction -v`
Expected: FAIL — `ExtractionLoop` does not exist

- [ ] **Step 3: Implement minimal ExtractionLoop**

Create `backend/app/extraction_loop.py`:

```python
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.models import Todo
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)


class ExtractionLoop:
    def __init__(
        self,
        transcript: TranscriptAccumulator,
        send_fn: Callable[[list[Todo]], Awaitable[None]],
        extract_fn: Callable[..., Awaitable[list[Todo]]],
        token_threshold: int = 30,
    ) -> None:
        self._transcript = transcript
        self._send_fn = send_fn
        self._extract_fn = extract_fn
        self._token_threshold = token_threshold

        self._previous_todos: list[Todo] = []
        self._tokens_since_last_extraction = 0
        self._extraction_task: asyncio.Task | None = None
        self._dirty = False

    async def _run_extraction(self, trigger_reason: str = "unknown") -> None:
        """Run one extraction cycle."""
        transcript_text = self._transcript.full_text
        if not transcript_text.strip():
            return

        try:
            todos = await self._extract_fn(
                transcript_text,
                previous_todos=self._previous_todos or None,
            )
            self._previous_todos = todos
            self._tokens_since_last_extraction = 0
            await self._send_fn(todos)
        except Exception:
            logger.exception("Extraction failed")

    async def _maybe_extract(self, trigger_reason: str = "unknown") -> None:
        """Start extraction if not already running, otherwise set dirty flag."""
        if self._extraction_task and not self._extraction_task.done():
            self._dirty = True
            self._pending_trigger_reason = trigger_reason
            return

        self._dirty = False
        self._extraction_task = asyncio.create_task(
            self._extraction_cycle(trigger_reason)
        )

    async def _extraction_cycle(self, trigger_reason: str) -> None:
        """Run extraction, then re-run if dirty flag was set during execution."""
        await self._run_extraction(trigger_reason)
        while self._dirty:
            self._dirty = False
            reason = getattr(self, "_pending_trigger_reason", "dirty")
            await self._run_extraction(reason)

    async def on_endpoint(self) -> None:
        """Called when Soniox <end> token is received."""
        await self._maybe_extract(trigger_reason="endpoint")

    def on_tokens(self, count: int) -> None:
        """Called after apply_event with count of new final tokens."""
        self._tokens_since_last_extraction += count
        if self._tokens_since_last_extraction >= self._token_threshold:
            asyncio.create_task(self._maybe_extract(trigger_reason="token_threshold"))

    async def on_stop(self) -> None:
        """Wait for in-flight extraction, then run one final pass."""
        if self._extraction_task and not self._extraction_task.done():
            await self._extraction_task

        # Final pass on the fully finalized transcript
        self._dirty = False
        await self._run_extraction(trigger_reason="stop")

    def cancel(self) -> None:
        """Cancel in-flight extraction and reset state."""
        if self._extraction_task and not self._extraction_task.done():
            self._extraction_task.cancel()
        self._extraction_task = None
        self._dirty = False
        self._previous_todos = []
        self._tokens_since_last_extraction = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_extraction_loop.py::test_endpoint_triggers_extraction -v`
Expected: PASS

- [ ] **Step 5: Write remaining ExtractionLoop tests**

Add to `backend/tests/test_extraction_loop.py`:

```python
@pytest.mark.asyncio
async def test_token_threshold_triggers_extraction(transcript, send_fn, mock_extract):
    """Accumulating tokens beyond threshold triggers extraction."""
    transcript.final_parts.append("word " * 30)

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=mock_extract,
        token_threshold=30,
    )
    loop.on_tokens(30)
    await asyncio.sleep(0.05)

    mock_extract.assert_awaited_once()
    send_fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_token_threshold_not_reached(transcript, send_fn, mock_extract):
    """Below threshold, no extraction is triggered."""
    transcript.final_parts.append("hello ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=mock_extract,
        token_threshold=30,
    )
    loop.on_tokens(5)
    await asyncio.sleep(0.05)

    mock_extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_dirty_flag_collapses_multiple_triggers(transcript, send_fn):
    """Multiple triggers during in-flight extraction collapse into one re-run."""
    call_count = 0
    results = [
        [Todo(text="First")],
        [Todo(text="First"), Todo(text="Second")],
    ]

    async def slow_extract(*args, **kwargs):
        nonlocal call_count
        idx = call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return results[min(idx, len(results) - 1)]

    transcript.final_parts.append("I need to do stuff. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=slow_extract,
        token_threshold=30,
    )

    # First trigger starts extraction
    await loop.on_endpoint()
    await asyncio.sleep(0.02)  # let task start

    # Two more triggers while in-flight — should collapse
    await loop.on_endpoint()
    await loop.on_endpoint()

    # Wait for all to complete
    await asyncio.sleep(0.3)

    # Should have been called exactly twice (initial + one dirty re-run)
    assert call_count == 2
    assert send_fn.await_count == 2


@pytest.mark.asyncio
async def test_on_stop_waits_for_inflight_then_runs_final(transcript, send_fn):
    """on_stop waits for in-flight extraction, then runs one final pass."""
    call_count = 0

    async def tracked_extract(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(0.1)
        return [Todo(text=f"Todo {call_count}")]

    transcript.final_parts.append("Buy milk. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=tracked_extract,
        token_threshold=30,
    )

    # Start an extraction
    await loop.on_endpoint()
    await asyncio.sleep(0.02)

    # on_stop waits for it, then does final pass
    await loop.on_stop()

    # Should have 2 calls: in-flight + final
    assert call_count == 2
    assert send_fn.await_count == 2


@pytest.mark.asyncio
async def test_on_stop_without_inflight(transcript, send_fn, mock_extract):
    """on_stop with no in-flight extraction runs exactly one pass."""
    transcript.final_parts.append("Buy milk. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=mock_extract,
        token_threshold=30,
    )

    await loop.on_stop()

    mock_extract.assert_awaited_once()
    send_fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_previous_todos_forwarded(transcript, send_fn):
    """ExtractionLoop passes previous_todos to extract_fn."""
    first_todos = [Todo(text="Buy milk")]

    call_kwargs_list = []

    async def tracking_extract(*args, **kwargs):
        call_kwargs_list.append(kwargs)
        return first_todos

    transcript.final_parts.append("Buy milk. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=tracking_extract,
        token_threshold=30,
    )

    await loop.on_endpoint()
    await asyncio.sleep(0.05)

    # Second extraction should receive previous todos
    transcript.final_parts.append("Call dentist. ")
    await loop.on_endpoint()
    await asyncio.sleep(0.05)

    assert call_kwargs_list[0].get("previous_todos") is None
    assert call_kwargs_list[1]["previous_todos"] == first_todos


@pytest.mark.asyncio
async def test_cancel_stops_inflight(transcript, send_fn):
    """cancel() cancels in-flight extraction task."""
    async def slow_extract(*args, **kwargs):
        await asyncio.sleep(10)
        return []

    transcript.final_parts.append("Buy milk. ")

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=slow_extract,
        token_threshold=30,
    )

    await loop.on_endpoint()
    await asyncio.sleep(0.02)

    loop.cancel()

    assert loop._extraction_task is None
    assert loop._dirty is False


@pytest.mark.asyncio
async def test_empty_transcript_skips_extraction(send_fn, mock_extract):
    """No extraction is run when the transcript is empty."""
    transcript = TranscriptAccumulator()

    loop = ExtractionLoop(
        transcript=transcript,
        send_fn=send_fn,
        extract_fn=mock_extract,
        token_threshold=30,
    )

    await loop.on_endpoint()
    await asyncio.sleep(0.05)

    mock_extract.assert_not_awaited()
```

- [ ] **Step 6: Run all ExtractionLoop tests**

Run: `cd backend && uv run pytest tests/test_extraction_loop.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/extraction_loop.py backend/tests/test_extraction_loop.py
git commit -m "feat: add ExtractionLoop with trigger logic, dirty flag, and stop semantics"
```

---

## Task 4: Add Logfire instrumentation

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add logfire dependency**

Add `"logfire[fastapi]>=3.0.0"` to `backend/pyproject.toml` dependencies list.

Run: `cd backend && uv sync`

- [ ] **Step 2: Add Logfire setup to main.py**

Modify `backend/app/main.py` — add Logfire initialization before the app:

```python
import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ws import router as ws_router

logfire.configure()
logfire.instrument_pydantic_ai()

app = FastAPI()
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # Starlette typing gap
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Verify the app starts**

Run: `cd backend && uv run python -c "from app.main import app; print('OK')"`
Expected: prints "OK" (logfire.configure() should not fail even without a token — it falls back to local/no-op mode)

- [ ] **Step 4: Run existing tests to verify nothing breaks**

Run: `cd backend && uv run pytest -v`
Expected: all existing tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/main.py backend/uv.lock
git commit -m "feat: add Logfire instrumentation for FastAPI and PydanticAI"
```

---

## Task 5: Wire ExtractionLoop into ws.py

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

This is where the pieces come together. The WebSocket handler instantiates `ExtractionLoop` and calls it from the relay function.

- [ ] **Step 1: Write failing test — mid-session todos are sent**

Add to `backend/tests/test_ws.py`:

```python
import json


def _mock_soniox_with_endpoints(transcripts_and_endpoints):
    """Create a mock Soniox that emits tokens and <end> markers.

    transcripts_and_endpoints is a list of (text, has_endpoint) tuples.
    """
    mock = AsyncMock()
    mock.send = AsyncMock()
    mock.close = AsyncMock()

    messages = []
    for text, has_endpoint in transcripts_and_endpoints:
        tokens = [{"text": text, "is_final": True}]
        if has_endpoint:
            tokens.append({"text": "<end>", "is_final": True})
        messages.append(json.dumps({"tokens": tokens}))
    messages.append(json.dumps({"finished": True}))

    async def iterator():
        for msg in messages:
            yield msg

    mock.__aiter__ = lambda self: iterator()
    return mock


def test_ws_sends_todos_during_recording():
    """Todos messages are sent during recording when endpoints are detected."""
    mock_todos = [Todo(text="Buy milk")]

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=mock_todos),
    ):
        mock_connect.return_value = _mock_soniox_with_endpoints([
            ("I need to buy milk. ", True),
            ("And call the dentist. ", True),
        ])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json()["type"] == "started"

            # Collect messages until we see todos or a timeout
            messages = []
            import time
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "todos":
                        break
                except Exception:
                    break

            todo_messages = [m for m in messages if m["type"] == "todos"]
            assert len(todo_messages) >= 1, (
                f"Expected at least one todos message during recording, got: {messages}"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_sends_todos_during_recording -v`
Expected: FAIL — current ws.py only sends todos on stop

- [ ] **Step 3: Wire ExtractionLoop into ws.py**

Modify `backend/app/ws.py`. Key changes:

1. Import `ExtractionLoop` and `logfire`
2. Add `enable_endpoint_detection` and `max_endpoint_delay_ms` to Soniox config
3. Pass `ExtractionLoop` to the relay function
4. In the relay, call `loop.on_endpoint()` or `loop.on_tokens()` based on `apply_event` result
5. In stop handler, call `await loop.on_stop()` instead of `extract_todos` directly
6. Add Logfire spans

```python
import asyncio
import contextlib
import json
import logging

import logfire
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.extract import extract_todos
from app.extraction_loop import ExtractionLoop
from app.models import Todo
from app.session_recorder import SessionRecorder
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
    transcript: TranscriptAccumulator,
    extraction_loop: ExtractionLoop,
    recorder: SessionRecorder | None = None,
):
    """Read transcript events from Soniox and forward to browser."""
    try:
        async for message in soniox_ws:
            if recorder:
                recorder.write_soniox_message(
                    message if isinstance(message, str) else message.decode()
                )
            event = json.loads(message)
            if event.get("finished"):
                return

            with logfire.span(
                "soniox_event",
            ):
                result = transcript.apply_event(event)

                if result.tokens:
                    with logfire.span("browser_relay"):
                        await browser_ws.send_json(
                            {
                                "type": "transcript",
                                "tokens": result.tokens,
                            }
                        )

                if result.has_endpoint:
                    await extraction_loop.on_endpoint()
                elif result.final_token_count > 0:
                    extraction_loop.on_tokens(result.final_token_count)

    except websockets.ConnectionClosed:
        logger.warning("Soniox connection closed unexpectedly during relay")
    except Exception as e:
        logger.exception("Error relaying from Soniox")
        with contextlib.suppress(Exception):
            await browser_ws.send_json({"type": "error", "message": str(e)})


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    settings = get_settings()
    soniox_ws = None
    relay_task = None
    transcript = TranscriptAccumulator()
    extraction_loop: ExtractionLoop | None = None
    recorder = SessionRecorder() if settings.record_sessions else None

    try:
        with logfire.span("ws_session"):
            while True:
                message = await browser_ws.receive()

                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                    except json.JSONDecodeError:
                        await browser_ws.send_json(
                            {"type": "error", "message": "Invalid control message"}
                        )
                        continue

                    msg_type = data.get("type")

                    if msg_type == "start":
                        if soniox_ws is not None:
                            if relay_task:
                                relay_task.cancel()
                                relay_task = None
                            with contextlib.suppress(Exception):
                                await soniox_ws.close()
                            soniox_ws = None
                        if extraction_loop:
                            extraction_loop.cancel()
                        if recorder:
                            recorder.stop()

                        latest_todo_items: list[dict] = []

                        async def send_todos(todos: list[Todo]) -> None:
                            nonlocal latest_todo_items
                            with logfire.span("ws_send_todos", todo_count=len(todos)):
                                latest_todo_items = [
                                    t.model_dump(exclude_none=True, mode="json")
                                    for t in todos
                                ]
                                await browser_ws.send_json(
                                    {"type": "todos", "items": latest_todo_items}
                                )

                        extraction_loop = ExtractionLoop(
                            transcript=transcript,
                            send_fn=send_todos,
                            extract_fn=extract_todos,
                        )

                        soniox_config = {
                            "api_key": settings.soniox_api_key,
                            "model": "stt-rt-v4",
                            "audio_format": "pcm_s16le",
                            "sample_rate": 16000,
                            "num_channels": 1,
                            "enable_endpoint_detection": True,
                            "max_endpoint_delay_ms": 1000,
                            "context": {
                                "general": [
                                    {
                                        "key": "topic",
                                        "value": "The user is dictating tasks and todos "
                                        "into a voice-driven todo list application.",
                                    },
                                ],
                            },
                        }

                        try:
                            soniox_ws = await websockets.connect(SONIOX_WS_URL)
                            await soniox_ws.send(json.dumps(soniox_config))
                            transcript.reset()
                            if recorder:
                                recorder.start()
                            relay_task = asyncio.create_task(
                                _relay_soniox_to_browser(
                                    soniox_ws,
                                    browser_ws,
                                    transcript,
                                    extraction_loop,
                                    recorder,
                                )
                            )
                            await browser_ws.send_json({"type": "started"})
                        except Exception as e:
                            logger.exception("Failed to connect to Soniox")
                            await browser_ws.send_json(
                                {
                                    "type": "error",
                                    "message": f"Soniox connection failed: {e}",
                                }
                            )

                    elif msg_type == "stop" and soniox_ws:
                        await soniox_ws.send(json.dumps({"type": "finalize"}))
                        await soniox_ws.send(b"")
                        warning_message: str | None = None
                        if relay_task:
                            try:
                                await asyncio.wait_for(
                                    relay_task,
                                    timeout=settings.soniox_stop_timeout_seconds,
                                )
                            except TimeoutError:
                                warning_message = (
                                    "Timed out waiting for the final transcript; "
                                    "todos were not extracted."
                                )
                                logger.warning(
                                    "Timed out waiting for Soniox relay to finish"
                                )
                                relay_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await relay_task
                            finally:
                                relay_task = None

                        full_transcript = transcript.full_text
                        logger.info(
                            "Transcript (%d chars): %s",
                            len(full_transcript),
                            full_transcript[:200],
                        )

                        if not warning_message and extraction_loop:
                            try:
                                with logfire.span("final_extraction"):
                                    await extraction_loop.on_stop()
                            except Exception:
                                warning_message = "Todo extraction failed."
                                logger.exception("Todo extraction failed")

                        if recorder:
                            recorder.write_result(full_transcript, latest_todo_items)
                            recorder.stop()

                        stopped_payload = {
                            "type": "stopped",
                            "transcript": full_transcript,
                        }
                        if warning_message:
                            stopped_payload["warning"] = warning_message
                        await browser_ws.send_json(stopped_payload)

                        with contextlib.suppress(Exception):
                            await soniox_ws.close()
                        soniox_ws = None

                elif "bytes" in message:
                    if soniox_ws:
                        if recorder:
                            recorder.write_audio(message["bytes"])
                        await soniox_ws.send(message["bytes"])

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if recorder:
            recorder.stop()
        if extraction_loop:
            extraction_loop.cancel()
        if relay_task:
            relay_task.cancel()
        if soniox_ws:
            with contextlib.suppress(Exception):
                await soniox_ws.close()
```

- [ ] **Step 4: Run the new test**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_sends_todos_during_recording -v`
Expected: PASS

- [ ] **Step 5: Update existing ws tests for new relay signature**

The existing `test_ws_stop_sends_todos_before_stopped` test patches `extract_todos` at the module level. With ExtractionLoop, the stop flow now uses `extraction_loop.on_stop()` which calls `extract_todos` internally. The patch target stays the same (`app.ws.extract_todos`) because `ExtractionLoop` receives `extract_fn=extract_todos` from `ws.py`.

Run all ws tests to verify:

Run: `cd backend && uv run pytest tests/test_ws.py -v`

If any tests fail due to the new `extraction_loop` parameter on `_relay_soniox_to_browser`, update the test that patches `_relay_soniox_to_browser` (`test_ws_stop_timeout_skips_extraction_and_surfaces_warning`) to match the new signature.

- [ ] **Step 6: Run full test suite**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "feat: wire ExtractionLoop into WebSocket handler for mid-session extraction"
```

---

## Task 6: Add Logfire spans to ExtractionLoop

**Files:**
- Modify: `backend/app/extraction_loop.py`

- [ ] **Step 1: Add spans to _run_extraction and _maybe_extract**

Modify `backend/app/extraction_loop.py` — wrap extraction calls with Logfire spans:

```python
import logfire

# In _run_extraction:
async def _run_extraction(self, trigger_reason: str = "unknown") -> None:
    transcript_text = self._transcript.full_text
    if not transcript_text.strip():
        return

    with logfire.span(
        "extraction_cycle",
        trigger_reason=trigger_reason,
        transcript_length=len(transcript_text),
        previous_todo_count=len(self._previous_todos),
    ):
        try:
            todos = await self._extract_fn(
                transcript_text,
                previous_todos=self._previous_todos or None,
            )
            self._previous_todos = todos
            self._tokens_since_last_extraction = 0
            await self._send_fn(todos)
        except Exception:
            logger.exception("Extraction failed")
```

Update callers to pass `trigger_reason`:
- `on_endpoint`: `trigger_reason="endpoint"`
- `on_tokens` threshold: `trigger_reason="token_threshold"`
- `on_stop`: `trigger_reason="stop"`

- [ ] **Step 2: Run all tests**

Run: `cd backend && uv run pytest -v`
Expected: all pass (logfire spans are no-ops without a configured token)

- [ ] **Step 3: Commit**

```bash
git add backend/app/extraction_loop.py
git commit -m "feat: add Logfire spans to ExtractionLoop for extraction cycle tracing"
```

---

## Task 7: Frontend — handle todos during recording

**Files:**
- Modify: `frontend/src/hooks/useTranscript.ts`

The frontend already handles `todos` messages via `setTodos()`. The main change is that `todos` messages now arrive during `"recording"` status, not just during `"extracting"`.

- [ ] **Step 1: Verify current behavior handles it**

The current `ws.onmessage` handler at `frontend/src/hooks/useTranscript.ts:141-151` already handles `todos` messages unconditionally:

```typescript
} else if (msg.type === "todos" && msg.items) {
    setTodos(msg.items.map(...));
}
```

This means the frontend already works — `setTodos` replaces the list regardless of current status. No code change needed for the basic flow.

- [ ] **Step 2: Verify stop flow still works**

The stop handler at line 229-267 sends `stop`, sets status to `"extracting"`, and waits for `stopped`. The backend still sends `todos` then `stopped` on stop. The frontend handles this correctly.

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && pnpm test:run`
Expected: all pass

- [ ] **Step 4: Commit (only if changes were needed)**

If no code changes are required, skip this commit.

---

## Task 8: End-to-end behavioral tests

**Files:**
- Create: `backend/tests/test_e2e.py`

**Prerequisite:** Fixtures `refine-todo` and `continuous-speech` must be recorded. If they don't exist, ask the user to record them. The test for `call-mom-memo-supplier` can proceed with the existing fixture.

- [ ] **Step 1: Write e2e test infrastructure**

Create `backend/tests/test_e2e.py`:

```python
"""End-to-end behavioral tests — real Soniox + real Gemini.

These tests replay recorded audio through the full pipeline and assert
on observable behaviors. Gated behind RUN_E2E_INTEGRATION=1.

Prerequisite: fixtures must exist in tests/fixtures/ with audio.pcm files.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import time
from pathlib import Path

import pytest
import websockets

requires_e2e = pytest.mark.skipif(
    not (
        os.environ.get("SONIOX_API_KEY")
        and os.environ.get("GEMINI_API_KEY")
        and os.environ.get("RUN_E2E_INTEGRATION") == "1"
    ),
    reason=(
        "E2E tests require SONIOX_API_KEY, GEMINI_API_KEY, "
        "and RUN_E2E_INTEGRATION=1"
    ),
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "ws://localhost:8000/ws")


async def _replay_fixture(fixture_name: str, *, stop_after_audio: bool = True):
    """Replay a fixture through the real backend, collect all messages.

    Returns (messages_before_stop, messages_after_stop).
    """
    audio_path = FIXTURES_DIR / fixture_name / "audio.pcm"
    if not audio_path.exists():
        pytest.skip(f"Fixture {fixture_name} audio.pcm not found")

    audio_bytes = audio_path.read_bytes()
    # 16kHz 16-bit mono = 32000 bytes per second
    chunk_size = 3200  # 100ms of audio
    chunk_interval = 0.1  # seconds

    messages_before_stop = []
    messages_after_stop = []

    async with websockets.connect(BACKEND_URL) as ws:
        await ws.send(json.dumps({"type": "start"}))

        # Collect the "started" message
        started = json.loads(await ws.recv())
        assert started["type"] == "started"

        # Stream audio at realistic pace
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i : i + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(chunk_interval)

            # Non-blocking check for incoming messages
            try:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.01))
                    messages_before_stop.append(msg)
            except (asyncio.TimeoutError, TimeoutError):
                pass

        # Wait a bit for any remaining extractions
        await asyncio.sleep(2)

        # Drain messages
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                messages_before_stop.append(msg)
        except (asyncio.TimeoutError, TimeoutError):
            pass

        if stop_after_audio:
            # Send stop
            await ws.send(json.dumps({"type": "stop"}))

            # Collect messages after stop
            try:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    messages_after_stop.append(msg)
                    if msg["type"] == "stopped":
                        break
            except (asyncio.TimeoutError, TimeoutError):
                pass

    return messages_before_stop, messages_after_stop


@requires_e2e
@pytest.mark.asyncio
async def test_todos_appear_while_speaking():
    """Behavior 1: At least one todos message arrives before stop is sent."""
    before_stop, after_stop = await _replay_fixture("call-mom-memo-supplier")

    todo_messages_before_stop = [m for m in before_stop if m["type"] == "todos"]
    assert len(todo_messages_before_stop) >= 1, (
        f"Expected todos before stop. Messages before stop: "
        f"{[m['type'] for m in before_stop]}"
    )


@requires_e2e
@pytest.mark.asyncio
async def test_all_todos_captured():
    """Behavior 2: Final todo list contains all expected items."""
    before_stop, after_stop = await _replay_fixture("call-mom-memo-supplier")

    # Find the last todos message (from the final sweep)
    all_todo_messages = (
        [m for m in before_stop if m["type"] == "todos"]
        + [m for m in after_stop if m["type"] == "todos"]
    )
    assert len(all_todo_messages) >= 1

    final_todos = all_todo_messages[-1]["items"]
    final_texts = " ".join(t["text"].lower() for t in final_todos)

    # The fixture contains: call mom, finish memo, call supplier
    assert "call" in final_texts and "mom" in final_texts, (
        f"Missing 'call mom' in: {final_texts}"
    )
    assert "memo" in final_texts, f"Missing 'memo' in: {final_texts}"
    assert "supplier" in final_texts or "catering" in final_texts, (
        f"Missing 'supplier/catering' in: {final_texts}"
    )


@requires_e2e
@pytest.mark.asyncio
async def test_stop_triggers_final_sweep():
    """Behavior 5: A todos message arrives after stop, before stopped."""
    before_stop, after_stop = await _replay_fixture("call-mom-memo-supplier")

    after_stop_types = [m["type"] for m in after_stop]
    assert "todos" in after_stop_types, (
        f"Expected todos after stop. Messages after stop: {after_stop_types}"
    )
    # Verify todos comes before stopped
    todos_idx = after_stop_types.index("todos")
    stopped_idx = after_stop_types.index("stopped")
    assert todos_idx < stopped_idx


@requires_e2e
@pytest.mark.asyncio
async def test_refine_todo():
    """Behavior 3: Later speech can refine earlier todos."""
    before_stop, after_stop = await _replay_fixture("refine-todo")

    todo_messages = [m for m in before_stop if m["type"] == "todos"]
    if len(todo_messages) < 2:
        pytest.skip("Need at least 2 todo messages to test refinement")

    # Check that a todo changed between two successive messages
    first_items = [t["text"] for t in todo_messages[0]["items"]]
    last_items = [t["text"] for t in todo_messages[-1]["items"]]
    assert first_items != last_items, (
        f"Expected todo refinement. First: {first_items}, Last: {last_items}"
    )


@requires_e2e
@pytest.mark.asyncio
async def test_token_threshold_fallback():
    """Behavior 6: Todos appear even without <end> tokens (continuous speech)."""
    before_stop, after_stop = await _replay_fixture("continuous-speech")

    todo_messages_before_stop = [m for m in before_stop if m["type"] == "todos"]
    assert len(todo_messages_before_stop) >= 1, (
        f"Expected todos from token threshold fallback. "
        f"Messages before stop: {[m['type'] for m in before_stop]}"
    )
```

- [ ] **Step 2: Verify tests are skipped without env vars**

Run: `cd backend && uv run pytest tests/test_e2e.py -v`
Expected: all tests SKIPPED (no RUN_E2E_INTEGRATION=1)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e.py
git commit -m "feat: add end-to-end behavioral tests for mid-session extraction"
```

---

## Task 9: Verify and clean up

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass (skipping integration tests)

- [ ] **Step 2: Run linters**

Run: `cd backend && uv run ruff check`
Expected: clean

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && pnpm test:run`
Expected: all pass

- [ ] **Step 4: Run frontend lint**

Run: `cd frontend && pnpm lint`
Expected: clean

- [ ] **Step 5: Manual smoke test (if dev servers available)**

Start dev servers with `./scripts/dev.sh start`, open the app, speak, and verify:
- Todos appear while still speaking
- Stop triggers a final sweep
- All todos are captured

- [ ] **Step 6: Final commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore: clean up after item 3 implementation"
```
