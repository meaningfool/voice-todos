# Plan: Shared Session Core In The Local Path

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [011_spec_shared-session-core-local-path.md](011_spec_shared-session-core-local-path.md)

**Goal:** Extract a shared live session controller out of the local FastAPI `/ws` path so transcript and finalization lifecycle are reusable across runtimes, while preserving the existing local browser contract and keeping todo extraction orchestration local to the FastAPI adapter.

**Architecture:** Add one runtime-neutral controller module in `backend/app/` that owns STT session lifecycle, transcript accumulation, relay consumption, stop coordination, and cleanup. Keep `backend/app/ws.py` as the local adapter that still owns browser protocol parsing, todo extraction timing, todo snapshot sending, invalid-control-message handling, and optional session recording.

**Tech Stack:** Python 3.14, FastAPI, websockets, pytest, uv, ruff, ty

---

## Scope

This plan covers exactly three deliverables:

1. Add shared controller coverage that locks the session relay, stop, timeout, and cleanup contract outside FastAPI.
2. Introduce a shared live session controller module in `backend/app/`.
3. Refactor `backend/app/ws.py` into a thin adapter over the shared controller while preserving the local `/ws` browser workflow.

Out of scope for this plan:

- Cloudflare Worker or Durable Object runtime code
- shared todo/extraction core work
- browser protocol redesign
- STT provider transport rewrites
- deploy-path or packaging changes

---

## File Map

### Backend - New files

| File | Responsibility |
|------|----------------|
| `backend/app/live_session.py` | Runtime-neutral live session controller, stop result, relay consumption, finalization wait path, and idempotent cleanup |
| `backend/tests/test_live_session.py` | Unit tests for controller relay behavior, stop sequencing, timeout outcome, final transcript selection, and cleanup safety |

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/ws.py` | Replace inline session lifecycle ownership with controller usage while keeping browser protocol, todo orchestration, and recorder behavior local |
| `backend/tests/test_ws.py` | Preserve `/ws` behavioral coverage and add seam-focused checks that the FastAPI adapter routes session lifecycle through the shared controller |

### Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/app/stt.py` | Existing shared STT contract used by the controller |
| `backend/app/stt_factory.py` | Existing provider factory seam the local adapter should continue to use |
| `backend/app/transcript_accumulator.py` | Existing normalized transcript state and update result contract |
| `backend/app/extraction_loop.py` | Stays adapter-owned in `V1`; do not pull it into the controller |
| `backend/app/session_recorder.py` | Remains local-only and optional in `V1` |
| `backend/tests/test_ws.py` | Current acceptance-shaped local `/ws` coverage that should stay small and current |
| `backend/tests/test_stt_factory.py` | Existing factory seam tests that should keep passing without widening scope |

---

## Acceptance Gates From Spec

## Acceptance Gate: Local Live Session Workflow Is Preserved Through The Shared Controller Boundary

**Why this gate matters:**
This slice is only complete if the local browser workflow still behaves the same while the session lifecycle has actually moved behind a reusable shared boundary. Either half failing makes the slice incomplete.

**Criteria:**

- When the local browser client starts a session over `/ws`, the system still returns `started` and streams transcript token updates using the existing browser message contract.
- When the local browser client stops a session, the system still requests provider finalization before end-of-stream, resolves the final transcript using the current finalization rules, sends todo output before `stopped`, and preserves the current warning behavior for timeout and final extraction failure.
- When the configured provider exposes `final_transcript_text`, the stop path still uses that text for the final transcript payload and final extraction input.
- The local FastAPI adapter depends on a shared live session controller boundary, and the shared controller does not import FastAPI, browser WebSocket types, `ExtractionLoop`, or session-recording modules.

**Proof:**

- **Setup:** Run backend integration tests against the existing FastAPI app with fake `SttSession` implementations that cover normal transcript streaming, provider final transcript override, stop timeout, and final extraction failure.
- **Action:** Drive the `/ws` route through `start`, transcript relay, binary audio frames where relevant, and `stop`.
- **Assertions:** Verify `started` is sent, transcript messages stream in order, stop triggers finalize before EOS, final transcript output matches the current rules, todo messages are sent before `stopped`, timeout and extraction-failure warnings match the current contract, and provider final transcript override is preserved.
- **Structural assertions:** Inspect the code boundary to show the FastAPI route uses the shared controller interface and the shared controller module does not import FastAPI, browser WebSocket types, local todo orchestration, or recording code.
- **Evidence:** Named integration tests covering the preserved `/ws` contract, their asserted ordering and payload expectations, and code references showing the new controller boundary and forbidden dependency absence.

---

## Gate Execution

### Behavioral proof

Run:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_start_sends_started_when_soniox_connects \
  tests/test_ws.py::test_soniox_transcript_state_acceptance \
  tests/test_ws.py::test_ws_audio_frames_forward_without_session_recorder \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  tests/test_ws.py::test_ws_stop_requests_final_transcript_before_end_of_stream \
  tests/test_ws.py::test_ws_stop_uses_session_final_transcript_text_for_extraction_and_payload \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  tests/test_ws.py::test_ws_stop_timeout_skips_extraction_and_surfaces_warning \
  -v
```

Expected: PASS

Evidence to collect:

- pytest output showing each named test passes
- any updated test names if one existing assertion needs to be renamed during the refactor, while keeping the acceptance surface equivalent and small

### Structural proof

Run:

```bash
cd backend && uv run python - <<'PY'
import ast
from pathlib import Path


def module_imports(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


live_imports = module_imports("app/live_session.py")
forbidden = {
    name
    for name in live_imports
    if name == "fastapi"
    or name.startswith("fastapi.")
    or name == "app.extraction_loop"
    or name.startswith("app.extraction_loop.")
    or name == "app.session_recorder"
    or name.startswith("app.session_recorder.")
}
assert not forbidden, f"forbidden imports in app/live_session.py: {sorted(forbidden)}"

ws_imports = module_imports("app/ws.py")
assert "app.live_session" in ws_imports, ws_imports

print("boundary-ok")
PY
```

Expected: prints `boundary-ok`

Evidence to collect:

- command output showing `boundary-ok`
- code references to `backend/app/live_session.py` and `backend/app/ws.py`

---

## Supporting Verification

Run:

```bash
cd backend && uv run pytest tests/test_live_session.py -v
cd backend && uv run pytest tests/test_ws.py -k "invalid_json or unknown_message or disconnect or audio_frames_forward" -v
cd backend && uv run ruff check app/live_session.py app/ws.py tests/test_live_session.py tests/test_ws.py
cd backend && uv run ty check app/live_session.py app/ws.py
```

Expected:

- controller unit tests PASS
- focused websocket regression checks PASS
- `ruff check` clean
- `ty check` clean

---

## Task 1.1: Add controller relay coverage and a minimal shared controller scaffold

**Purpose:**
Define the new controller boundary with tests before moving any logic out of `ws.py`.

**Files:**
- Create: `backend/tests/test_live_session.py`
- Create: `backend/app/live_session.py`
- Test: `backend/tests/test_live_session.py`

**Supports:**
- Supporting Verification: controller unit tests

- [ ] **Step 1: Write the failing controller relay tests**

Add `backend/tests/test_live_session.py` with focused cases that prove:

- `test_controller_start_emits_transcript_tokens_in_order`
- `test_controller_send_audio_forwards_bytes_to_active_session`

Use a fake `SttSession` patterned after the existing fake session helpers in `backend/tests/test_ws.py`.

- [ ] **Step 2: Run the controller relay tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_live_session.py::test_controller_start_emits_transcript_tokens_in_order \
  tests/test_live_session.py::test_controller_send_audio_forwards_bytes_to_active_session \
  -v
```

Expected: FAIL because `app.live_session` and `LiveSessionController` do not exist yet

- [ ] **Step 3: Implement the smallest shared controller scaffold**

Create `backend/app/live_session.py` with:

- a `LiveSessionController` class
- injected session-factory dependency
- internal `TranscriptAccumulator`
- a transcript/update callback that surfaces normalized token updates without browser JSON formatting
- `start()` to open the STT session and begin the relay task
- `send_audio()` to forward bytes to the active provider session

Keep this module free of FastAPI, `ExtractionLoop`, and `SessionRecorder` imports.

- [ ] **Step 4: Run the relay-focused controller tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_live_session.py -k "transcript_tokens_in_order or send_audio_forwards" -v
```

Expected: PASS

- [ ] **Step 5: Commit the controller scaffold**

```bash
git add backend/app/live_session.py backend/tests/test_live_session.py
git commit -m "refactor: add live session controller scaffold"
```

---

## Task 1.2: Add stop, timeout, and cleanup coverage to the shared controller

**Purpose:**
Move the highest-risk shared behavior out of `ws.py`: stop sequencing, final transcript selection, timeout handling, and idempotent cleanup.

**Files:**
- Modify: `backend/tests/test_live_session.py`
- Modify: `backend/app/live_session.py`
- Test: `backend/tests/test_live_session.py`

**Supports:**
- Acceptance Gate: Local Live Session Workflow Is Preserved Through The Shared Controller Boundary
- Supporting Verification: controller unit tests

- [ ] **Step 1: Write the failing controller stop-path tests**

Extend `backend/tests/test_live_session.py` with:

- `test_controller_stop_requests_finalize_before_end_stream`
- `test_controller_stop_prefers_provider_final_transcript_text_when_available`
- `test_controller_stop_returns_timeout_result_without_raising`
- `test_controller_close_is_idempotent_after_stop_or_relay_cancel`

- [ ] **Step 2: Run the stop-path controller tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_live_session.py::test_controller_stop_requests_finalize_before_end_stream \
  tests/test_live_session.py::test_controller_stop_prefers_provider_final_transcript_text_when_available \
  tests/test_live_session.py::test_controller_stop_returns_timeout_result_without_raising \
  tests/test_live_session.py::test_controller_close_is_idempotent_after_stop_or_relay_cancel \
  -v
```

Expected: FAIL because the controller does not yet own stop sequencing or cleanup outcomes

- [ ] **Step 3: Implement the stop result and cleanup path**

Update `backend/app/live_session.py` to add:

- a `StopResult` value object that returns at least the final transcript text and timeout status
- controller-owned finalization wait logic equivalent to the current `_wait_for_final_transcript()` behavior
- `stop(timeout_seconds=...)` that requests final transcript before end-of-stream
- selection of `final_transcript_text` over accumulated transcript text when the provider exposes it
- relay-task cancellation and session close behavior that can be called repeatedly without double-close noise

- [ ] **Step 4: Run the full controller test file to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/test_live_session.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the shared stop path**

```bash
git add backend/app/live_session.py backend/tests/test_live_session.py
git commit -m "refactor: move stop lifecycle into live session controller"
```

---

## Task 1.3: Refactor the FastAPI `/ws` adapter through the shared controller and run the gate

**Purpose:**
Preserve the local browser-visible workflow while moving session lifecycle ownership behind the shared controller boundary.

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`
- Test: `backend/tests/test_ws.py`

**Supports:**
- Acceptance Gate: Local Live Session Workflow Is Preserved Through The Shared Controller Boundary
- Supporting Verification: focused websocket regressions

- [ ] **Step 1: Add failing seam-focused websocket tests**

Extend `backend/tests/test_ws.py` with:

- `test_ws_start_builds_live_session_controller`
- `test_ws_stop_uses_controller_stop_result_for_warning_and_transcript`

Keep the existing local contract tests intact; only change them where the internal seam needs to be asserted through the controller instead of through inline route state.

- [ ] **Step 2: Run the seam-focused websocket tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_start_builds_live_session_controller \
  tests/test_ws.py::test_ws_stop_uses_controller_stop_result_for_warning_and_transcript \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  tests/test_ws.py::test_ws_stop_requests_final_transcript_before_end_of_stream \
  -v
```

Expected: FAIL because `ws.py` still owns session lifecycle directly

- [ ] **Step 3: Refactor `ws.py` into a thin adapter over the controller**

Update `backend/app/ws.py` so:

- `start` constructs a `LiveSessionController` with the existing local `create_stt_session()` wrapper
- transcript updates from the controller are mapped into browser `transcript` messages
- endpoint and transcript-changed signals still drive the local `ExtractionLoop`
- `stop` delegates transcript/finalization lifecycle to the controller, then keeps final extraction, todo fallback, recorder writes, warning text, and `stopped` payload emission local
- invalid JSON handling, unknown control messages, browser disconnect behavior, and binary audio forwarding remain adapter concerns

- [ ] **Step 4: Run the focused websocket suite to verify it passes**

Run:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_start_builds_live_session_controller \
  tests/test_ws.py::test_ws_stop_uses_controller_stop_result_for_warning_and_transcript \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  tests/test_ws.py::test_ws_stop_requests_final_transcript_before_end_of_stream \
  tests/test_ws.py::test_ws_stop_uses_session_final_transcript_text_for_extraction_and_payload \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  tests/test_ws.py::test_ws_stop_timeout_skips_extraction_and_surfaces_warning \
  -v
```

Expected: PASS

- [ ] **Step 5: Run the acceptance gate and supporting verification**

Run the exact commands from:

- `Gate Execution`
- `Supporting Verification`

Expected:

- acceptance gate behavioral suite PASS
- structural boundary script prints `boundary-ok`
- supporting verification clean

- [ ] **Step 6: Commit the slice implementation**

```bash
git add backend/app/ws.py backend/tests/test_ws.py backend/app/live_session.py backend/tests/test_live_session.py
git commit -m "refactor: route local ws through live session controller"
```

---

## Checkpoint

Do not start `V2` until the acceptance gate and supporting verification above all pass.

Required evidence before moving on:

- PASS output for the named acceptance tests
- `boundary-ok` from the structural proof command
- PASS output for `tests/test_live_session.py`
- clean `ruff check`
- clean `ty check`

---

## Recommended First Execution Order

1. Lock the controller relay contract with tests and add the minimal controller scaffold.
2. Move stop sequencing, final transcript selection, and cleanup into the controller.
3. Route the FastAPI adapter through the controller and run the acceptance gate.

REQUIRED HANDOFF: superpowers:executing-plans

OPTIONAL HANDOFF: superpowers:subagent-driven-development
