# Item 5: Stop On `<fin>` And Retune Extraction Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce stop-time latency by treating Soniox `<fin>` as the signal that final transcript finalization is complete, capture exact stop timing in Logfire, skip redundant stop-time extraction when the finalized transcript has not changed, lower the fallback extraction threshold from `25` to `15`, and reduce Gemini 3 Flash reasoning overhead during extraction.

**Architecture:** The websocket stop flow should stop waiting on Soniox `finished` / socket shutdown once `<fin>` confirms transcript finalization. We will add explicit stop lifecycle telemetry (`ws.stop_received` and `ws.stopped_sent`) so Logfire shows true click-to-idle timing, and we will teach `ExtractionLoop` to remember the last successfully extracted transcript so stop can reuse the latest snapshot instead of rerunning Gemini on identical text. Separately, we will lower the fallback extraction threshold to `15` based on the March 26 trace, while leaving endpoint-triggered extraction enabled, and configure Gemini 3 Flash with minimal thinking to trim stop-time model latency and token waste without changing providers.

**Tech Stack:** FastAPI, websockets, Soniox realtime WebSocket API, PydanticAI, Gemini 3 Flash, Logfire, pytest, Starlette TestClient

**References:** `docs/references/logfire-trace-analysis.md`, `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`, `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`, `sessions/recent/2026-03-26T16-10-23/soniox.jsonl`, `https://ai.google.dev/gemini-api/docs/gemini-3`

---

## Scope

This plan covers five product changes:

1. Stop-time finalization should wait for Soniox `<fin>` instead of waiting for the full Soniox `finished` / close sequence.
2. Stop handling should emit explicit Logfire timing events for when stop is received and when `stopped` is sent.
3. Stop should skip the final Gemini extraction when the latest successful extraction already used the same transcript snapshot.
4. The fallback extraction threshold should decrease from `25` to `15` while leaving endpoint-triggered extraction enabled.
5. Gemini 3 Flash extraction should run with minimal thinking.

Out of scope for this plan:

- model/provider comparisons
- prompt changes
- optimistic stop extraction before `<fin>`
- frontend UX copy or visual changes

---

## File Map

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/transcript_accumulator.py` | Expose whether a Soniox event contained `<fin>` so the websocket layer can treat finalization completion separately from endpoint detection |
| `backend/app/ws.py` | Replace stop-time waiting on relay completion with waiting on an explicit finalization event; emit stop timing telemetry; lower `TOKEN_THRESHOLD` to `15`; keep timeout and fallback behavior |
| `backend/app/extraction_loop.py` | Track the last successfully extracted transcript snapshot and skip redundant stop-time extraction when the transcript is unchanged |
| `backend/app/extract.py` | Configure Gemini 3 Flash extraction with minimal thinking |
| `backend/tests/test_transcript_accumulator.py` | Add coverage for `<fin>` detection in the structured event result |
| `backend/tests/test_ws.py` | Update stop-path tests for `<fin>`-driven completion, stop telemetry events, and the new threshold value |
| `backend/tests/test_extraction_loop.py` | Add coverage for stop-time dedupe when the transcript is unchanged |
| `backend/tests/test_extract.py` | Add coverage for Gemini minimal-thinking agent configuration |

### Backend - Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
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

## Task 3: Add explicit stop timing telemetry

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

The latest trace still required manual reconstruction to answer the user-visible question: "How long did stop take from the moment the browser sent stop to the moment the backend sent `stopped`?" Add explicit Logfire events at those exact lifecycle points so future analysis does not depend on inferred timing.

- [ ] **Step 1: Write the failing websocket telemetry test**

Add a focused test that patches `app.ws.logfire.info` and verifies the stop flow emits both lifecycle events:

```python
def test_ws_stop_emits_stop_timing_events():
    with (
        patch("app.ws.logfire.info") as mock_logfire_info,
        ...
    ):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json()["type"] == "started"

            ws.send_json({"type": "stop"})
            _ = ws.receive_json()
            _ = ws.receive_json()

    event_names = [call.args[0] for call in mock_logfire_info.call_args_list]
    assert "ws.stop_received" in event_names
    assert "ws.stopped_sent" in event_names
```

- [ ] **Step 2: Run the telemetry test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_stop_emits_stop_timing_events -v`

Expected: FAIL because the websocket stop flow does not emit explicit timing events yet

- [ ] **Step 3: Emit exact stop lifecycle events**

In `backend/app/ws.py`, emit a Logfire event as soon as the browser stop control message is received:

```python
logfire.info("ws.stop_received", connection_id=connection_id)
```

Immediately before sending the final `stopped` payload, emit:

```python
logfire.info(
    "ws.stopped_sent",
    connection_id=connection_id,
    transcript_chars=len(full_transcript),
    warning=warning_message,
)
```

- [ ] **Step 4: Run websocket tests to verify the telemetry passes**

Run: `cd backend && uv run pytest tests/test_ws.py -k "stop and timing" -v`

Expected: PASS

- [ ] **Step 5: Commit the stop telemetry change**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "feat: add explicit stop timing telemetry"
```

---

## Task 4: Skip redundant stop-time extraction when the transcript is unchanged

**Files:**
- Modify: `backend/app/extraction_loop.py`
- Modify: `backend/tests/test_extraction_loop.py`
- Modify: `backend/tests/test_ws.py`

The March 26 trace showed a stop-time extraction running on the exact same 132-character transcript that had already completed in the preceding endpoint extraction. Preserve the safe stop semantics while avoiding that extra Gemini call when the finalized transcript snapshot has not changed.

- [ ] **Step 1: Write the failing ExtractionLoop dedupe test**

Add a unit test in `backend/tests/test_extraction_loop.py` that proves stop does not call `extract_fn` twice for the same transcript:

```python
@pytest.mark.asyncio
async def test_on_stop_skips_redundant_final_extraction_when_transcript_unchanged():
    transcript = TranscriptAccumulator(final_parts=["Buy flowers."])
    extract_fn = AsyncMock(return_value=[Todo(text="Buy flowers")])
    send_fn = AsyncMock()
    loop = ExtractionLoop(transcript, send_fn, extract_fn, token_threshold=15)

    await loop.on_endpoint()
    await asyncio.sleep(0)
    await loop.on_stop()

    assert extract_fn.await_count == 1
```

Also add a websocket-level regression test that stop still emits `todos` before `stopped`, even when no new Gemini call ran and the latest snapshot must be reused.

- [ ] **Step 2: Run the dedupe tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_extraction_loop.py tests/test_ws.py -k "redundant or reused" -v`

Expected: FAIL because `ExtractionLoop.on_stop()` always runs another extraction today

- [ ] **Step 3: Track the last successfully extracted transcript**

In `backend/app/extraction_loop.py`, add state such as:

```python
self._last_successful_transcript = ""
```

Update `_run_extraction()` so after a successful send it records the transcript text that produced the latest todo snapshot.

- [ ] **Step 4: Skip stop extraction when the transcript matches the last successful snapshot**

In `ExtractionLoop.on_stop()`, keep the current behavior of awaiting any in-flight extraction first. After that wait, compare the current transcript text to the stored last-successful snapshot:

```python
if self._transcript_text() == self._last_successful_transcript:
    return
```

If the transcript differs, keep the existing final extraction path.

Do not remove the websocket fallback send in `backend/app/ws.py`; it should continue to re-send the latest todo snapshot so the protocol still ends with `todos` then `stopped`.

- [ ] **Step 5: Run the dedupe tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_extraction_loop.py tests/test_ws.py -k "redundant or reused" -v`

Expected: PASS

- [ ] **Step 6: Commit the stop dedupe change**

```bash
git add backend/app/extraction_loop.py backend/tests/test_extraction_loop.py backend/tests/test_ws.py
git commit -m "perf: skip redundant stop extraction when transcript is unchanged"
```

---

## Task 5: Lower the fallback extraction threshold to 15

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

The latest March 26 recording never triggered the fallback threshold because only 18 finalized token pieces accumulated between the first and second endpoint markers. Lowering the threshold to `15` should let at least one mid-utterance fallback extraction happen in traces shaped like that recording, while leaving endpoint-triggered extraction enabled.

- [ ] **Step 1: Write or update the threshold expectation test**

In `backend/tests/test_ws.py`, tighten the wiring assertion:

```python
def test_ws_start_configures_extraction_loop_with_token_threshold():
    ...
    assert mock_loop_cls.call_args.kwargs["token_threshold"] == 15
```

Keep importing `TOKEN_THRESHOLD` if you want the test to assert both the constant and the wiring:

```python
assert TOKEN_THRESHOLD == 15
assert mock_loop_cls.call_args.kwargs["token_threshold"] == TOKEN_THRESHOLD
```

- [ ] **Step 2: Run the threshold test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_start_configures_extraction_loop_with_token_threshold -v`

Expected: FAIL because `TOKEN_THRESHOLD` is still `25`

- [ ] **Step 3: Update the threshold constant**

In `backend/app/ws.py`, change:

```python
TOKEN_THRESHOLD = 25
```

to:

```python
TOKEN_THRESHOLD = 15
```

- [ ] **Step 4: Run the threshold test to verify it passes**

Run: `cd backend && uv run pytest tests/test_ws.py::test_ws_start_configures_extraction_loop_with_token_threshold -v`

Expected: PASS

- [ ] **Step 5: Commit the threshold tuning**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "tune: lower fallback extraction threshold to 15"
```

---

## Task 6: Minimize Gemini 3 Flash thinking for extraction

**Files:**
- Modify: `backend/app/extract.py`
- Modify: `backend/tests/test_extract.py`

The latest trace still showed Gemini 3 Flash spending meaningful stop-time latency inside the model call. Google documents that Gemini 3 Flash supports `thinking_level="minimal"`, which is the closest low-latency setting available on the current model without changing providers.

- [ ] **Step 1: Write the failing extractor configuration test**

Add a unit test in `backend/tests/test_extract.py` that verifies the cached agent is constructed with minimal thinking:

```python
def test_get_agent_uses_minimal_google_thinking():
    fake_provider = object()
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract.get_settings", return_value=SimpleNamespace(gemini_api_key="test-key")),
        patch("app.extract.GoogleProvider", return_value=fake_provider),
        patch("app.extract.GoogleModel", return_value=fake_model),
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        _extract_mod._agent = None
        _extract_mod._get_agent()

    assert mock_agent.call_args.kwargs["model_settings"] == {
        "google_thinking_config": {"thinking_level": "minimal"}
    }
```

- [ ] **Step 2: Run the extractor test to verify it fails**

Run: `cd backend && uv run pytest tests/test_extract.py::test_get_agent_uses_minimal_google_thinking -v`

Expected: FAIL because the agent is not yet configured with Google thinking settings

- [ ] **Step 3: Configure minimal thinking on the agent**

In `backend/app/extract.py`, add agent-level model settings:

```python
_agent = Agent(
    GoogleModel(
        "gemini-3-flash-preview",
        provider=GoogleProvider(api_key=settings.gemini_api_key),
    ),
    output_type=ExtractionResult,
    system_prompt=_SYSTEM_PROMPT,
    model_settings={
        "google_thinking_config": {"thinking_level": "minimal"},
    },
)
```

- [ ] **Step 4: Run the extractor tests to verify the configuration passes**

Run: `cd backend && uv run pytest tests/test_extract.py -v`

Expected: PASS

- [ ] **Step 5: Commit the thinking configuration change**

```bash
git add backend/app/extract.py backend/tests/test_extract.py
git commit -m "perf: minimize gemini thinking for todo extraction"
```

---

## Task 7: Run focused regression verification

**Files:**
- Verify only: `backend/tests/test_transcript_accumulator.py`
- Verify only: `backend/tests/test_ws.py`
- Verify only: `backend/tests/test_extraction_loop.py`
- Verify only: `backend/tests/test_extract.py`

Before handing off or continuing into model comparisons, verify that the stop flow, transcript semantics, and extraction loop behavior still hold.

- [ ] **Step 1: Run the focused backend regression suite**

Run:

```bash
cd backend && uv run pytest \
  tests/test_transcript_accumulator.py \
  tests/test_ws.py \
  tests/test_extraction_loop.py \
  tests/test_extract.py -v
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
- timestamp gap between `ws.stop_received` and `ws.stopped_sent`
- whether any stop sessions now return partial transcripts
- whether the fallback threshold reduction noticeably adds useful mid-utterance `todos` updates
- whether stop reuses the latest snapshot without rerunning Gemini when the transcript is unchanged
- whether Gemini minimal thinking measurably reduces stop-time model latency and thoughts-token usage

- [ ] **Step 4: Commit any final polish if needed**

```bash
git add backend/app/transcript_accumulator.py backend/app/extraction_loop.py backend/app/extract.py backend/app/ws.py backend/tests/test_transcript_accumulator.py backend/tests/test_extraction_loop.py backend/tests/test_extract.py backend/tests/test_ws.py
git commit -m "test: verify fin-based stop flow and latency follow-ups"
```

---

## Notes For The Implementer

- Keep the existing `soniox_stop_timeout_seconds` config in `backend/app/config.py`; this plan changes what we wait on, not the timeout source of truth.
- Change `ExtractionLoop.on_stop()` only enough to skip the redundant Gemini call when the transcript matches the last successful snapshot; keep the existing "wait for in-flight extraction first" behavior.
- Do not change frontend stop timing in `frontend/src/hooks/useTranscript.ts`; the current `MIC_TAIL_MS = 200` is intentionally left untouched here.
- Be careful with relay cleanup ordering. Since stop will no longer await relay completion, cleanup needs to avoid leaving a background task running after `stopped` is sent.
