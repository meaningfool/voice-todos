# Stop On `<fin>` And Retune Extraction Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce stop-time latency by treating Soniox `<fin>` as the signal that final transcript finalization is complete, and reduce redundant mid-speech LLM calls by raising the fallback extraction threshold from `10` to `25`.

**Architecture:** The websocket stop flow currently blocks on the Soniox relay task finishing, which means waiting for Soniox `finished` and socket shutdown even after the transcript may already be finalized. We will surface `<fin>` explicitly from transcript processing, use an `asyncio.Event` to unblock stop-time extraction as soon as finalization completes, and keep the existing timeout/fallback behavior as a safety net. Separately, we will retune the fallback extraction threshold to `25` without changing endpoint-triggered extraction.

**Tech Stack:** FastAPI, websockets, Soniox realtime WebSocket API, PydanticAI, Gemini 3 Flash, Logfire, pytest, Starlette TestClient

**References:** `docs/references/logfire-trace-analysis.md`, `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`, `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`

---

## Scope

This plan covers exactly two product changes:

1. Stop-time finalization should wait for Soniox `<fin>` instead of waiting for the full Soniox `finished` / close sequence.
2. The fallback extraction threshold should increase from `10` to `25`.

Out of scope for this plan:

- model/provider comparisons
- prompt changes
- final-extraction dedupe gates
- optimistic stop extraction before `<fin>`
- frontend UX copy or visual changes

---

## File Map

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/transcript_accumulator.py` | Expose whether a Soniox event contained `<fin>` so the websocket layer can treat finalization completion separately from endpoint detection |
| `backend/app/ws.py` | Replace stop-time waiting on relay completion with waiting on an explicit finalization event; raise `TOKEN_THRESHOLD` to `25`; keep timeout and fallback behavior |
| `backend/tests/test_transcript_accumulator.py` | Add coverage for `<fin>` detection in the structured event result |
| `backend/tests/test_ws.py` | Update stop-path tests for `<fin>`-driven completion and the new threshold value |

### Backend - Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/app/extraction_loop.py` | Stop still delegates the final extraction through `ExtractionLoop.on_stop()` after transcript finalization is complete |
| `backend/tests/test_extraction_loop.py` | Confirms stop waits for in-flight extraction and still performs a final pass |
| `backend/tests/test_soniox_integration.py` | Documents current Soniox finalize semantics and should stay logically consistent |

---

## Task 1: Surface Soniox `<fin>` in transcript processing

**Files:**
- Modify: `backend/app/transcript_accumulator.py`
- Modify: `backend/tests/test_transcript_accumulator.py`

The websocket stop flow needs a reliable signal for "all audio sent before `finalize` is now final." `TranscriptAccumulator.apply_event()` already detects `<fin>` internally, but it throws that information away. Expose it so the websocket layer can coordinate stop-time behavior without parsing Soniox events twice.

- [ ] **Step 1: Write the failing test for `<fin>` detection in the accumulator result**

Add a new assertion in `backend/tests/test_transcript_accumulator.py`:

```python
def test_fin_token_is_reported_in_result(self):
    accumulator = TranscriptAccumulator()

    result = accumulator.apply_event(
        {"tokens": [{"text": "<fin>", "is_final": True}]}
    )

    assert result.has_fin is True
    assert result.has_endpoint is False
    assert result.final_token_count == 0
```

- [ ] **Step 2: Run the accumulator test to verify it fails**

Run: `cd backend && uv run pytest tests/test_transcript_accumulator.py::TestApplyEvent::test_fin_token_is_reported_in_result -v`

Expected: FAIL because `TranscriptAccumulatorResult` does not expose `has_fin`

- [ ] **Step 3: Update the accumulator result shape**

Extend `backend/app/transcript_accumulator.py` so the result object includes `has_fin`:

```python
@dataclass(slots=True)
class TranscriptAccumulatorResult:
    tokens: list[dict[str, str | bool]]
    has_endpoint: bool
    has_fin: bool
    final_token_count: int
```

And return it from `apply_event()`:

```python
return TranscriptAccumulatorResult(
    tokens=[...],
    has_endpoint=has_endpoint,
    has_fin=has_fin,
    final_token_count=final_token_count,
)
```

- [ ] **Step 4: Run the accumulator test to verify it passes**

Run: `cd backend && uv run pytest tests/test_transcript_accumulator.py -v`

Expected: PASS

- [ ] **Step 5: Commit the accumulator change**

```bash
git add backend/app/transcript_accumulator.py backend/tests/test_transcript_accumulator.py
git commit -m "feat: expose soniox fin signal in transcript accumulator"
```

---

## Task 2: Make stop wait for `<fin>` instead of waiting for relay shutdown

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

Today the stop path sends Soniox `finalize`, sends an empty frame, and then blocks on `relay_task` finishing. That couples transcript readiness to Soniox socket shutdown. We want to decouple them: wait for finalization completion, run final extraction, then clean up the relay/socket as best effort.

- [ ] **Step 1: Write the failing websocket tests for `<fin>`-driven stop completion**

Add a focused test in `backend/tests/test_ws.py` that proves stop can proceed after finalization even if the relay would otherwise still be running:

```python
def test_ws_stop_waits_for_fin_not_finished():
    release_relay = asyncio.Event()

    async def relay_with_fin(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()
        await release_relay.wait()

    ...

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        assert ws.receive_json()["type"] == "started"

        ws.send_json({"type": "stop"})
        todos_msg = ws.receive_json()
        stopped_msg = ws.receive_json()

    assert todos_msg["type"] == "todos"
    assert stopped_msg["type"] == "stopped"
```

Also add or update a timeout-path test so if `<fin>` never arrives, the backend still returns the existing warning and fallback behavior instead of hanging forever.

- [ ] **Step 2: Run the websocket tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_ws.py -k "fin or stop" -v`

Expected: FAIL because `ws.py` still waits on `relay_task` completion instead of a finalization signal

- [ ] **Step 3: Introduce an explicit finalization event in the websocket layer**

In `backend/app/ws.py`, create an `asyncio.Event()` for the active session:

```python
finalized_event = asyncio.Event()
```

Reset it on each new `start`, and pass it into `_relay_soniox_to_browser(...)`.

Update the relay signature:

```python
async def _relay_soniox_to_browser(
    soniox_ws,
    browser_ws,
    transcript,
    extraction_loop,
    recorder=None,
    *,
    finalized_event: asyncio.Event,
):
```

When a Soniox event includes `<fin>`, set the event:

```python
if result.has_fin:
    finalized_event.set()
```

- [ ] **Step 4: Replace stop-time waiting on relay shutdown with waiting on finalization**

In the stop branch of `backend/app/ws.py`, keep:

```python
await soniox_ws.send(json.dumps({"type": "finalize"}))
await soniox_ws.send(b"")
```

But replace:

```python
await asyncio.wait_for(relay_task, timeout=settings.soniox_stop_timeout_seconds)
```

with:

```python
await asyncio.wait_for(
    finalized_event.wait(),
    timeout=settings.soniox_stop_timeout_seconds,
)
```

If it times out, preserve the current warning path:

```python
warning_message = (
    "Timed out waiting for the final transcript; "
    "todos were not extracted."
)
```

After sending `stopped`, do best-effort cleanup:

- close `soniox_ws`
- cancel `relay_task` if it is still running
- suppress `CancelledError` exactly as the current cleanup flow does

This preserves current robustness while removing the user-visible dependency on Soniox `finished`.

- [ ] **Step 5: Add a code comment explaining `<fin>` vs `finished`**

Add a short comment near the stop wait logic in `backend/app/ws.py`:

```python
# <fin> means all audio sent before finalize is now final.
# We do not need to wait for the later Soniox finished/close sequence
# before running the final extraction.
```

- [ ] **Step 6: Run the websocket tests to verify the new stop path**

Run: `cd backend && uv run pytest tests/test_ws.py -v`

Expected: PASS

- [ ] **Step 7: Commit the websocket stop-flow change**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "feat: stop on soniox fin instead of relay shutdown"
```

---

## Task 3: Raise the fallback extraction threshold to 25

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

The current fallback threshold of `10` is low relative to Soniox's token granularity and leads to redundant extraction calls during continuous speech. The agreed change is to raise it to `25` and leave endpoint-triggered extraction unchanged.

- [ ] **Step 1: Write or update the threshold expectation test**

In `backend/tests/test_ws.py`, tighten the wiring assertion:

```python
def test_ws_start_configures_extraction_loop_with_token_threshold():
    ...
    assert mock_loop_cls.call_args.kwargs["token_threshold"] == 25
```

Keep importing `TOKEN_THRESHOLD` if you want the test to assert both the constant and the wiring:

```python
assert TOKEN_THRESHOLD == 25
assert mock_loop_cls.call_args.kwargs["token_threshold"] == TOKEN_THRESHOLD
```

- [ ] **Step 2: Run the threshold test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_start_configures_extraction_loop_with_token_threshold -v`

Expected: FAIL because `TOKEN_THRESHOLD` is still `10`

- [ ] **Step 3: Update the threshold constant**

In `backend/app/ws.py`, change:

```python
TOKEN_THRESHOLD = 10
```

to:

```python
TOKEN_THRESHOLD = 25
```

- [ ] **Step 4: Run the threshold test to verify it passes**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_start_configures_extraction_loop_with_token_threshold -v`

Expected: PASS

- [ ] **Step 5: Commit the threshold tuning**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "tune: raise fallback extraction threshold to 25"
```

---

## Task 4: Run focused regression verification

**Files:**
- Verify only: `backend/tests/test_transcript_accumulator.py`
- Verify only: `backend/tests/test_ws.py`
- Verify only: `backend/tests/test_extraction_loop.py`

Before handing off or continuing into model comparisons, verify that the stop flow, transcript semantics, and extraction loop behavior still hold.

- [ ] **Step 1: Run the focused backend regression suite**

Run:

```bash
cd backend && uv run pytest \
  tests/test_transcript_accumulator.py \
  tests/test_ws.py \
  tests/test_extraction_loop.py -v
```

Expected: PASS

- [ ] **Step 2: Sanity-check that no unrelated files were changed**

Run:

```bash
git status --short
git diff -- backend/app/transcript_accumulator.py backend/app/ws.py backend/tests/test_transcript_accumulator.py backend/tests/test_ws.py
```

Expected: only the planned files show intended changes

- [ ] **Step 3: Record follow-up observations for the next iteration**

Write down, in the implementation handoff or PR description, the specific behaviors to watch after deployment:

- stop latency from button press to final `stopped`
- time between `finalize` send and `<fin>` receive
- whether any stop sessions now return partial transcripts
- whether the fallback threshold reduction noticeably lowers duplicate `todos` messages

- [ ] **Step 4: Commit any final polish if needed**

```bash
git add backend/app/transcript_accumulator.py backend/app/ws.py backend/tests/test_transcript_accumulator.py backend/tests/test_ws.py
git commit -m "test: verify fin-based stop flow and threshold tuning"
```

---

## Notes For The Implementer

- Keep the existing `soniox_stop_timeout_seconds` config in `backend/app/config.py`; this plan changes what we wait on, not the timeout source of truth.
- Do not change `ExtractionLoop.on_stop()` in this plan. It should keep running one final extraction after the transcript has been finalized.
- Do not change frontend stop timing in `frontend/src/hooks/useTranscript.ts`; the current `MIC_TAIL_MS = 200` is intentionally left untouched here.
- Be careful with relay cleanup ordering. Since stop will no longer await relay completion, cleanup needs to avoid leaving a background task running after `stopped` is sent.
