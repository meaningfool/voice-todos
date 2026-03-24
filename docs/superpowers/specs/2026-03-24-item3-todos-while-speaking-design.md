# Item 3 Design: Todos Appear While Speaking

Scope: add incremental todo extraction during recording so todos appear on screen while the user is still speaking, without waiting for the Stop button.

## Why this exists

Item 2 extracts todos only when the user clicks Stop. This means the user must finish speaking, click Stop, wait for extraction, and then see results. Item 3 removes that delay by extracting incrementally during recording. The Stop button remains as a "final sweep" to catch any trailing speech.

## Prerequisites: fixtures to record

Before implementation begins, the following audio fixtures must be recorded and placed in `backend/tests/fixtures/`. Each fixture needs `audio.pcm` (16kHz mono PCM), `soniox.jsonl` (recorded Soniox messages), and `result.json` (expected transcript and todos).

| Fixture | What to say | Purpose |
|---|---|---|
| `call-mom-memo-supplier` | Already exists | Multiple distinct todos with natural pauses |
| `refine-todo` | Say a todo, pause, then add detail to the same todo. E.g., "I need to buy milk... actually make that oat milk from the organic store" | Tests that later speech updates an earlier todo |
| `continuous-speech` | ~30s of uninterrupted speech containing multiple todos with minimal pauses | Tests the token-count fallback trigger |

## Goals

- Todos appear on screen while the user is still speaking
- Later speech can refine or add detail to earlier todos
- Later speech can merge or remove earlier todos when added context shows the earlier extraction was wrong
- Stop button triggers a final extraction sweep
- Full server-side observability via Logfire
- Deterministic CI coverage plus opt-in end-to-end behavioral tests with real Soniox and Gemini

## Non-goals

- Visual treatment of todo updates (animations, highlights) — deferred to a later spec
- Browser-side latency measurement
- Pipecat or LiveKit integration
- VAD — Soniox endpoint detection is sufficient

## Architecture: keep current stack, add ExtractionLoop

No new frameworks. The current architecture (browser → WebSocket → FastAPI → Soniox) stays. The new piece is an `ExtractionLoop` class that sits alongside the existing Soniox relay and decides when to call the LLM.

```
Browser                      FastAPI                          External
  │                             │                                │
  ├── audio frames ──────────►  ws.py                            │
  │                             ├── forward to Soniox ─────────► Soniox
  │                             │                                │
  │                             ├── _relay_soniox_to_browser     │
  │                             │   ├── transcript.apply_event() │
  │◄── transcript tokens ──────│   ├── send tokens to browser   │
  │                             │   ├── if <end>: loop.on_endpoint()
  │                             │   └── else: loop.on_tokens(n)  │
  │                             │                                │
  │                             │   ExtractionLoop               │
  │                             │   ├── check trigger conditions │
  │                             │   ├── extract_todos() ────────► Gemini
  │◄── todos ───────────────────│   └── send_fn(todos)           │
  │                             │                                │
  ├── stop ──────────────────►  ws.py                            │
  │                             ├── loop.on_stop() ────────────► Gemini
  │◄── todos (final) ──────────│                                │
  │◄── stopped ────────────────│                                │
```

## Extraction trigger logic

Two triggers, plus a final sweep on stop:

**Trigger 1 — Soniox `<end>` token (primary).** When Soniox emits an endpoint marker, the loop triggers extraction. This is Soniox's built-in utterance boundary detection. `ws.py` must explicitly enable this in the Soniox config via `enable_endpoint_detection: true`. The `max_endpoint_delay_ms` setting can be tuned (default 2000ms, can lower to 700-1000ms) for faster triggers; the initial implementation should set it explicitly rather than relying on a server default.

**Trigger 2 — Token count fallback.** If N new finalized tokens accumulate without an `<end>`, trigger anyway. Starting value: 30 tokens (tunable). This handles continuous speech without pauses.

**On stop:** One final extraction on the complete finalized transcript.

### Concurrency: dirty flag, not a queue

If an extraction is already in flight when a new trigger fires, don't start another. Set a dirty flag. When the current extraction completes, check the flag — if dirty, run again with the latest transcript. Multiple intermediate signals collapse into one run. There is no queue — just a single "needs re-extraction" flag.

**Stop behavior is special.** `on_stop()` does not cancel an in-flight extraction. It waits for the current extraction to finish, then runs exactly one final pass on the fully finalized transcript after Soniox finalize/finish has completed. Only after that final pass completes may the stop flow send `stopped`. This guarantees the session ends from a finalized transcript, not a speculative interim snapshot.

## ExtractionLoop interface

```python
ExtractionLoop(
    transcript: TranscriptAccumulator,
    send_fn: Callable[[list[Todo]], Awaitable[None]],
    token_threshold: int = 30,
)
```

**Methods:**
- `on_endpoint()` — called when `<end>` token received from Soniox
- `on_tokens(count: int)` — called after each `apply_event`, with the number of new final tokens
- `on_stop()` — waits for any in-flight extraction, then performs exactly one final extraction on the finalized transcript and awaits that result. Calls `send_fn` internally (same path as mid-session extractions). The caller does not use a return value.
- `cancel()` — cancels any in-flight extraction `asyncio.Task` and resets internal state. Called when the session ends abruptly (e.g., WebSocket disconnect without stop).

**Internal state:**
- `_previous_todos: list[Todo]` — starts empty, updated after each extraction
- `_tokens_since_last_extraction: int` — reset after each extraction
- `_extraction_running: bool` — guards concurrent execution
- `_dirty: bool` — set when a trigger fires during an in-flight extraction
- `_stop_requested: bool` — set by `on_stop()` so the loop knows it must perform one final finalized pass before the session can end

**Data flow:**
1. `_relay_soniox_to_browser` calls `transcript.apply_event()` as today
2. `apply_event` is extended to return endpoint information: it detects `<end>` tokens (same pattern as existing `<fin>` handling) and returns a result that indicates whether an endpoint was present, along with the filtered tokens
3. Based on the return value: if endpoint detected, call `loop.on_endpoint()`. Otherwise call `loop.on_tokens(n)` with the count of new final tokens. `<end>` tokens do not count toward the token threshold.
4. When triggered, `ExtractionLoop` calls `extract_todos(transcript.full_text, previous_todos=self._previous_todos)`
5. On result: updates `_previous_todos`, calls `send_fn(todos)`, checks dirty flag

## Changes to extract.py

The extraction function accepts the previous todo list and instructs the LLM to return an updated complete list.

**New signature:**
```python
async def extract_todos(
    transcript: str,
    *,
    previous_todos: list[Todo] | None = None,
    reference_dt: datetime | None = None,
) -> list[Todo]:
```

**Prompt additions:**
- "You may receive a list of previously extracted todos. Return the updated complete list."
- "Preserve the order of existing todos where that order still makes sense. Append genuinely new todos at the end."
- "If new speech adds details to an existing todo, update it in place."
- "If later context shows an earlier todo was over-split, duplicated, misheard, or should be absorbed into another todo, merge or remove it."
- "Explicit cancellation is one reason to remove a todo, but not the only one."
- "If no previous todos are provided, extract from scratch."

**Input format when previous todos exist:**
```
Current local datetime: 2026-03-24T14:30:00+02:00
Current local date: 2026-03-24
Current timezone: CEST

Previously extracted todos:
1. Buy milk (priority: high, due: 2026-03-25)
2. Call the dentist

Transcript:
I need to buy milk, it's urgent, I need it by tomorrow...
```

The LLM always returns the full current list. This is a snapshot, not a patch. The frontend replaces the whole list on each `todos` message and must not assume stable item identity across extractions.

## Changes to ws.py

Minimal changes:
- Instantiate `ExtractionLoop` on `start`, passing `transcript` and a `send_fn` that sends `{"type": "todos", "items": [...]}` to the browser
- Add Soniox endpoint detection settings to the start config: `enable_endpoint_detection: true` and an explicit `max_endpoint_delay_ms`
- In `_relay_soniox_to_browser`: after `transcript.apply_event()`, call `loop.on_endpoint()` or `loop.on_tokens(n)` as appropriate
- In the `stop` handler: call `await loop.on_stop()` instead of calling `extract_todos` directly. `stopped` is sent only after `loop.on_stop()` completes its guaranteed final finalized pass.

## Frontend changes

**Status flow:**
- Current: `idle → connecting → recording → extracting → idle`
- New: `idle → connecting → recording → idle` (during normal flow)
- The `"extracting"` state is used only briefly for the final sweep after Stop

**Todo updates during recording:**
- Every `todos` message replaces the full list via `setTodos()` (same mechanism as today)
- The list is treated as a full snapshot, not an append-only stream. Items may be refined, merged, removed, or reordered slightly as the model's understanding improves.
- Optional future work: track which todos are new or changed by comparing incoming list against previous. Not required for this spec — can be added when the visual treatment spec is designed.

**Stop behavior:**
- User clicks Stop → status becomes `"extracting"` → backend finishes any in-flight extraction, runs one final pass on finalized transcript, and the final message sequence ends with `todos` then `stopped` → status becomes `"idle"`
- If an extraction is already running when Stop is clicked, that extraction is allowed to finish first; then one final pass runs on the finalized transcript; then `stopped` is sent

**Skeleton cards:**
- Shown only if status is `"extracting"` and no todos exist yet (edge case: user says nothing, clicks stop immediately)
- During recording, no skeletons — todos appear directly as they're extracted

## Logfire observability

**Setup in `main.py`:**
```python
import logfire
logfire.configure()
logfire.instrument_fastapi(app)
logfire.instrument_pydantic_ai()
```

**New dependency:** `logfire[fastapi]`

**Server-side trace structure:**
```
ws_session (entire WebSocket connection)
├── soniox_event (per Soniox message received)
│   ├── transcript_accumulate (apply_event)
│   └── browser_relay (send tokens to browser)
├── extraction_cycle (when triggered)
│   ├── extract_todos (Gemini span auto-nested by PydanticAI)
│   └── ws_send_todos (send result to browser)
└── final_extraction (on stop)
    ├── extract_todos
    └── ws_send_todos
```

**Key attributes on spans:**
- `soniox_event`: has_endpoint, token_count, transcript_length
- `extraction_cycle`: trigger_reason (endpoint / token_threshold / stop), transcript_length, previous_todo_count
- `extract_todos`: todo_count (result), plus auto-captured Gemini latency and token counts
- `ws_send_todos`: todo_count

**WebSocket note:** FastAPI auto-instrumentation creates one span per connection. Per-message timing uses manual `logfire.span()` calls inside `ws.py` and `ExtractionLoop`.

**Browser-side timing:** Out of scope. Documented here as a future addition — could add timestamps to WebSocket messages to compute browser-to-server and server-to-browser latency.

## Testing strategy

### Deterministic component and integration tests (primary)

These tests do not require live vendors and should carry the bulk of CI confidence.

- `TranscriptAccumulator` tests: `<end>` is detected and filtered from browser transcript tokens, `<end>` does not count toward the token threshold, `<fin>` behavior remains correct
- `ExtractionLoop` tests: endpoint trigger, token-threshold trigger, dirty-flag collapse, no concurrent extraction overlap, `on_stop()` waits for the in-flight extraction and then performs exactly one final finalized pass
- WebSocket tests with mocked Soniox / mocked `extract_todos`: endpoint detection config is sent on start, mid-session `todos` messages are forwarded, and `stopped` is sent only after the final pass's `todos`
- Replay tests continue to run the production `TranscriptAccumulator` against recorded Soniox streams

### End-to-end behavioral tests (secondary, opt-in)

These tests use real Soniox and real Gemini. They replay recorded audio through the full pipeline and assert on observable behaviors. Gated behind `RUN_E2E_INTEGRATION=1`.

| # | Behavior | Fixture | Assertion |
|---|---|---|---|
| 1 | Todos appear while the user is still speaking | `call-mom-memo-supplier` | At least one `todos` message arrives before `stop` is sent |
| 2 | All todos are eventually captured | `call-mom-memo-supplier` | Final todo list contains all 3 expected items |
| 3 | Later speech can refine earlier todos | `refine-todo` | A todo's text changes between two successive `todos` messages |
| 4 | Stop uses a finalized transcript for its last pass | `call-mom-memo-supplier` | After `stop`, the last `todos` message before `stopped` reflects the final finalized pass |
| 5 | Stop triggers a final sweep | `call-mom-memo-supplier` | A `todos` message arrives after `stop`, before `stopped` |
| 6 | Token threshold fallback works | `continuous-speech` | A `todos` message arrives despite no `<end>` tokens in a long stretch |

**Test mechanism:** The test starts the real FastAPI app, connects via WebSocket, sends `start`, streams `audio.pcm` frames at realistic 16kHz pacing, collects all server messages, sends `stop`, collects final messages, and asserts on the message sequence.

### Additional targeted tests

The `ExtractionLoop` is the primary unit to test in isolation — it can be tested with a `TranscriptAccumulator` and a mock `extract_todos`, no WebSocket or API keys needed. In particular, deterministic tests should cover the correction cases that are hard to prove with live LLM output alone: later context causing merge/removal, and stop-time behavior when an extraction is already in flight.

### Existing tests

All existing tests must continue passing unless intentionally updated for the new multiple-`todos` behavior. The stop flow must still guarantee that the final message sequence ends with `todos` then `stopped`.

## Protocol changes

No new message types. The existing `{"type": "todos", "items": [...]}` message is now sent multiple times during recording instead of once on stop. This is additive — the frontend already handles this message type.

## New dependencies

- `logfire[fastapi]` (backend)
- No new frontend dependencies

## Notes for future agents

- Fixture recording requires a human with a microphone. Check the prerequisites table at the top before starting implementation.
- The token threshold (30) and Soniox endpoint delay are tunable. Use Logfire traces to inform tuning decisions.
- Visual treatment of todo updates (animations, highlights) is explicitly deferred. Todo diffing on the frontend is not part of this spec.
- Browser-side latency measurement is documented as a future addition in the Logfire section.
