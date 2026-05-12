# Plan: Real Frontend Runtime Switching For Local FastAPI And Cloudflare

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [016_spec_real-frontend-runtime-switching.md](016_spec_real-frontend-runtime-switching.md)

**Goal:** Make the real frontend app UI runnable against either local FastAPI or local Cloudflare without editing frontend websocket code, while preserving the existing `/ws` contract and making real-UI browser validation deterministic.

**Architecture:** Keep [frontend/src/hooks/useTranscript.ts](../../../frontend/src/hooks/useTranscript.ts) runtime-agnostic and still opening `/ws`. Add explicit dev-time backend selection in [frontend/vite.config.ts](../../../frontend/vite.config.ts), make [cloudflare/src/entry.py](../../../cloudflare/src/entry.py) accept plain `/ws`, and add a dev-only fixture-audio path in the real app UI so `agent-browser` can exercise the actual app deterministically without a live microphone.

**Tech Stack:** React 19, Vite 8, Vitest, FastAPI, Cloudflare workers-py / pywrangler, uv, pytest, `agent-browser`

---

## Scope

This plan covers exactly four deliverables:

1. Add explicit frontend websocket runtime selection for local dev.
2. Make the Cloudflare Worker accept plain `/ws` while preserving optional explicit-session support for smoke tooling.
3. Add a dev-only fixture-audio path to the real app UI so the actual frontend can drive deterministic websocket sessions in browser automation.
4. Run the `016` acceptance gates through the real app UI in both FastAPI and Cloudflare modes, plus the config/compatibility gate.

Out of scope for this plan:

- remote Cloudflare deployment
- transcript/todo/finalization behavior changes beyond connection/bootstrap compatibility
- websocket protocol redesign
- removal of existing smoke scripts or debug harnesses
- product-facing runtime-selection UI

---

## File Map

### Frontend runtime switching and real-UI validation surface

| File | Responsibility |
|------|----------------|
| `frontend/vite.config.ts` | Explicit local websocket backend selection via `WS_BACKEND`, including clear failure on invalid values |
| `frontend/vite.config.test.ts` | Focused config tests for FastAPI routing, Cloudflare routing, and invalid `WS_BACKEND` handling |
| `frontend/src/hooks/useTranscript.ts` | Keep websocket URL runtime-agnostic and add dev-only fixture-audio mode for deterministic browser validation through the real app UI |
| `frontend/src/hooks/useTranscript.test.tsx` | Hook-level tests for fixture mode, including unchanged websocket URL shape and chunk streaming behavior |
| `frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm` | Deterministic PCM asset served by Vite for real-UI browser validation |

### Cloudflare compatibility surface

| File | Responsibility |
|------|----------------|
| `cloudflare/src/entry.py` | Accept plain `/ws` from the frontend, derive or allocate session ids internally, and preserve optional `?session=...` support |
| `cloudflare/tests/test_entry.py` | Focused Worker entry tests for plain `/ws`, explicit-session compatibility, and non-websocket rejection behavior |
| `cloudflare/tests/test_ws_smoke.py` | Preserve direct smoke-script assumptions if any helper behavior changes |

### Existing runtime surfaces used as acceptance backends

| File | Why it matters |
|------|----------------|
| `backend/app/ws.py` | Existing FastAPI websocket path the real frontend must keep working against |
| `cloudflare/src/session_runtime.py` | Existing Cloudflare session owner that should stay behaviorally intact beyond bootstrap compatibility |
| `backend/tests/fixtures/while-speaking-two-todos/audio.pcm` | Source fixture for the frontend dev copy and browser-visible todo/transcript expectations |
| `frontend/src/App.tsx` | Real app UI surface exercised by `agent-browser` acceptance proof |
| `frontend/src/components/RecordButton.tsx` | Start/stop control used during browser validation |
| `frontend/src/components/SessionDetails.tsx` | Transcript surface asserted during browser validation |
| `frontend/src/components/TodoCard.tsx` | Todo text surface asserted during browser validation |

---

## Acceptance Gates From Spec

## Acceptance Gate: Real App UI Works Against Both Local Runtimes

**Why this gate matters:**
This is the missing product-level proof. If the real frontend still cannot run unchanged against both backends, then local Cloudflare support remains a harness-only capability rather than a true alternate runtime for the app.

**Criteria**
- The real app UI can be launched locally in FastAPI mode and complete the accepted websocket flow through the FastAPI backend.
- The real app UI can be launched locally in Cloudflare mode and complete the same accepted websocket flow through the Cloudflare backend.
- Switching between FastAPI mode and Cloudflare mode does not require editing frontend application code or changing the frontend websocket URL shape.

**Proof**
- **FastAPI setup:** run the local backend and frontend with `WS_BACKEND=fastapi`
- **FastAPI action:** use the real app UI in a browser to start recording, stream audio, and stop
- **FastAPI assertions:** verify the UI reaches the accepted browser-visible behavior already expected locally, including transcript activity and clean stop behavior
- **Cloudflare setup:** run the local Worker and frontend with `WS_BACKEND=cloudflare`
- **Cloudflare action:** use the same real app UI in a browser to start recording, stream audio, and stop
- **Cloudflare assertions:** verify the same UI reaches transcript activity, todo behavior where applicable, and clean stop behavior through the hosted runtime
- **Shared assertion:** no frontend websocket code edits or runtime-specific URL changes are required between the two runs; only local runtime configuration changes

**Expected evidence**
- exact local commands used to run:
  - FastAPI backend
  - Cloudflare Worker
  - frontend in both modes
- `agent-browser` commands used against the real app UI
- observed browser-visible outcomes for both modes

## Acceptance Gate: Local Runtime Selection And Worker Compatibility Are Explicit And Correct

**Why this gate matters:**
Even if one manual run works, the slice is incomplete if runtime switching is ambiguous or if Cloudflare still requires a frontend-specific compatibility hack outside the real UI contract.

**Criteria**
- Local frontend runtime selection is explicit through dev configuration rather than hidden code edits.
- `WS_BACKEND=fastapi` routes `/ws` to the FastAPI backend.
- `WS_BACKEND=cloudflare` routes `/ws` to the Cloudflare Worker backend.
- The Cloudflare Worker accepts plain `/ws` from the frontend instead of requiring a frontend-supplied `session` query parameter.

**Proof**
- **Config proof:** inspect [frontend/vite.config.ts](../../../frontend/vite.config.ts) and show explicit runtime-selection behavior
- **Worker proof:** inspect [cloudflare/src/entry.py](../../../cloudflare/src/entry.py) and show plain `/ws` compatibility for real frontend requests
- **Negative-config proof:** run the frontend with an invalid `WS_BACKEND` value and assert startup fails clearly rather than silently proxying to an unintended target

**Expected evidence**
- code references showing explicit Vite runtime selection and Cloudflare plain `/ws` handling
- exact failing startup output for invalid backend selection
- brief note on whether optional `?session=...` compatibility was preserved for smoke tooling

---

## Gate Execution

### Behavioral proof for `Real App UI Works Against Both Local Runtimes`

The browser proof needs deterministic audio through the **real app UI**, not the standalone harness page. Implement a dev-only fixture mode in the actual frontend, triggered by a frontend URL such as:

```text
http://127.0.0.1:5173/?fixture=while-speaking-two-todos
```

The fixture mode must keep the websocket target as `/ws`; it only replaces the microphone source with deterministic PCM chunk streaming inside the real app UI.

#### FastAPI mode

In terminal A:

```bash
cd backend && set -a && source .env && set +a && uv run uvicorn app.main:app --reload --port 8000 --log-level info
```

In terminal B:

```bash
cd frontend && WS_BACKEND=fastapi BACKEND_PORT=8000 FRONTEND_PORT=5173 pnpm dev --host 127.0.0.1 --port 5173
```

In terminal C:

```bash
agent-browser open http://127.0.0.1:5173/?fixture=while-speaking-two-todos
agent-browser snapshot -i
```

Use the snapshot output to identify the `Start Session` button id, then:

```bash
agent-browser click <start-button-id>
agent-browser wait --text "Listening now..."
agent-browser wait --text "Buy oat milk"
agent-browser snapshot -i
```

Use the second snapshot output to identify the `Finish Session` button id, then:

```bash
agent-browser click <finish-button-id>
agent-browser wait --text "Session details"
agent-browser click <session-details-summary-id>
agent-browser wait --text "By oat milk tonight. Zen email Sarah the revised budget."
agent-browser snapshot -i
```

Expected:
- the real app UI shows recording state
- at least one todo card appears containing `Buy oat milk`
- after stop, the transcript details contain `By oat milk tonight. Zen email Sarah the revised budget.`

#### Cloudflare mode

In terminal A:

```bash
cd cloudflare && set -a && source .dev.vars && set +a && uv run pywrangler dev --port 8788
```

In terminal B:

```bash
cd frontend && WS_BACKEND=cloudflare BACKEND_PORT=8000 CLOUDFLARE_PORT=8788 FRONTEND_PORT=5173 pnpm dev --host 127.0.0.1 --port 5173
```

In terminal C, repeat the same real-UI browser procedure:

```bash
agent-browser open http://127.0.0.1:5173/?fixture=while-speaking-two-todos
agent-browser snapshot -i
agent-browser click <start-button-id>
agent-browser wait --text "Listening now..."
agent-browser wait --text "Buy oat milk"
agent-browser snapshot -i
agent-browser click <finish-button-id>
agent-browser wait --text "Session details"
agent-browser click <session-details-summary-id>
agent-browser wait --text "By oat milk tonight. Zen email Sarah the revised budget."
agent-browser snapshot -i
```

Expected:
- the same real UI behavior appears through the Cloudflare runtime
- no frontend websocket URL change or frontend code edit is required between modes

Evidence to collect:
- exact backend / worker / frontend startup commands used
- exact `agent-browser` commands used
- browser snapshots showing the todo card and transcript details in both modes

### Behavioral proof for `Local Runtime Selection And Worker Compatibility Are Explicit And Correct`

Config proof:

```bash
rg -n "WS_BACKEND|BACKEND_PORT|CLOUDFLARE_PORT" frontend/vite.config.ts
cd frontend && pnpm test:run vite.config.test.ts
```

Expected:
- the code shows explicit runtime selection
- the config tests pass for FastAPI routing, Cloudflare routing, and invalid config handling

Worker proof:

```bash
rg -n "session|uuid|parse_qs|urlparse" cloudflare/src/entry.py
cd cloudflare && uv run pytest tests/test_entry.py::test_worker_accepts_plain_ws_without_session_query tests/test_entry.py::test_worker_preserves_explicit_session_query -v
```

Expected:
- the code shows plain `/ws` compatibility
- the targeted entry tests pass

Negative-config proof:

```bash
cd frontend && WS_BACKEND=bogus pnpm dev --host 127.0.0.1 --port 5173
```

Expected:
- process exits non-zero
- startup fails clearly with an error such as `Unsupported WS_BACKEND: bogus`

Evidence to collect:
- `rg` output from `frontend/vite.config.ts`
- `rg` output from `cloudflare/src/entry.py`
- targeted test output from `vite.config.test.ts` and `cloudflare/tests/test_entry.py`
- exact startup error output for invalid `WS_BACKEND`
- short note confirming whether explicit `?session=...` smoke compatibility was preserved

---

## Supporting Verification

Frontend verification:

```bash
cd frontend && pnpm test:run frontend/src/hooks/useTranscript.test.tsx vite.config.test.ts
cd frontend && pnpm build
cd frontend && pnpm lint
```

Cloudflare verification:

```bash
cd cloudflare && uv run pytest tests/test_entry.py tests/test_ws_smoke.py -v
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
```

Focused smoke preservation:

```bash
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --fixture-path ../backend/tests/fixtures/while-speaking-two-todos/audio.pcm \
  --mode todo-stop \
  --session-id smoke-todo-stop \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1 \
  --expect-todos-min 1 \
  --expect-terminal-type stopped
```

Expected:
- frontend unit tests PASS
- frontend build PASS
- frontend lint PASS
- Cloudflare entry and smoke-script tests PASS
- Cloudflare static checks PASS
- direct hosted smoke still PASS if explicit-session compatibility was preserved

---

## Checkpoint

Do not start any later slice until both `016` acceptance gates pass:

1. `Real App UI Works Against Both Local Runtimes`
2. `Local Runtime Selection And Worker Compatibility Are Explicit And Correct`

Supporting verification does not replace either gate.

---

## Task 1.1: Add explicit frontend websocket runtime selection

**Purpose:**
Make local runtime selection explicit and testable in Vite rather than hidden in one hardcoded backend proxy target.

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/vite.config.test.ts`

**Supports:**
- Acceptance Gate: `Local Runtime Selection And Worker Compatibility Are Explicit And Correct`
- Supporting Verification: `cd frontend && pnpm test:run vite.config.test.ts`

- [ ] **Step 1: Write the failing config tests**

Create `frontend/vite.config.test.ts` with focused tests for:
- `WS_BACKEND=fastapi` -> `ws://localhost:${BACKEND_PORT}`
- `WS_BACKEND=cloudflare` -> `ws://localhost:${CLOUDFLARE_PORT}`
- invalid `WS_BACKEND` throws a clear error

- [ ] **Step 2: Run the config tests to verify they fail**

Run:

```bash
cd frontend && pnpm test:run vite.config.test.ts
```

Expected: FAIL because runtime selection is still hardcoded.

- [ ] **Step 3: Implement the minimal config resolver**

Update `frontend/vite.config.ts` to:
- read `WS_BACKEND`
- default it explicitly to `fastapi`
- resolve FastAPI target from `BACKEND_PORT` with default `8000`
- resolve Cloudflare target from `CLOUDFLARE_PORT` with default `8788`
- throw a clear error on unsupported values

- [ ] **Step 4: Re-run the config tests**

Run:

```bash
cd frontend && pnpm test:run vite.config.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/vite.config.ts frontend/vite.config.test.ts
git commit -m "feat: add explicit frontend ws backend selection"
```

## Task 1.2: Make the Cloudflare Worker accept plain `/ws`

**Purpose:**
Remove the frontend-only incompatibility so the real app UI can connect to Cloudflare without appending `?session=...`, while preserving explicit-session support for smoke tools.

**Files:**
- Modify: `cloudflare/src/entry.py`
- Create: `cloudflare/tests/test_entry.py`
- Modify: `cloudflare/tests/test_ws_smoke.py` only if helper compatibility needs a test update

**Supports:**
- Acceptance Gate: `Local Runtime Selection And Worker Compatibility Are Explicit And Correct`
- Supporting Verification: `cd cloudflare && uv run pytest tests/test_entry.py tests/test_ws_smoke.py -v`

- [ ] **Step 1: Write the failing Worker entry tests**

Create `cloudflare/tests/test_entry.py` with at least:
- `test_worker_accepts_plain_ws_without_session_query`
- `test_worker_preserves_explicit_session_query`

The first test should assert that a plain `/ws` websocket request reaches `SESSION_RUNTIME.getByName(...)` with a non-empty derived session id.

- [ ] **Step 2: Run the Worker entry tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_entry.py -v
```

Expected: FAIL because `entry.py` still rejects missing `session`.

- [ ] **Step 3: Implement minimal plain-`/ws` compatibility**

Update `cloudflare/src/entry.py` so:
- `?session=...` still works unchanged
- plain `/ws` allocates or derives a non-empty session id internally
- non-websocket requests and wrong paths keep current rejection behavior

Use a simple generated id such as `uuid.uuid4().hex` unless the runtime already provides a better request identifier without extra coupling.

- [ ] **Step 4: Re-run the Worker entry tests and smoke-script tests**

Run:

```bash
cd cloudflare && uv run pytest tests/test_entry.py tests/test_ws_smoke.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/entry.py cloudflare/tests/test_entry.py cloudflare/tests/test_ws_smoke.py
git commit -m "feat: accept plain ws requests in cloudflare worker"
```

## Task 1.3: Add deterministic fixture audio to the real app UI

**Purpose:**
Make real-UI browser validation reproducible without requiring a live microphone, while keeping the frontend websocket URL and UI controls unchanged.

**Files:**
- Modify: `frontend/src/hooks/useTranscript.ts`
- Modify: `frontend/src/hooks/useTranscript.test.tsx`
- Create: `frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm`

**Supports:**
- Acceptance Gate: `Real App UI Works Against Both Local Runtimes`
- Supporting Verification: `cd frontend && pnpm test:run frontend/src/hooks/useTranscript.test.tsx`

- [ ] **Step 1: Write the failing hook tests**

Add focused tests to `frontend/src/hooks/useTranscript.test.tsx` for:
- fixture mode still opens `ws://<host>/ws` with no runtime-specific websocket URL shape
- fixture mode skips `getUserMedia` and streams deterministic PCM chunks over the websocket

Use a frontend URL query such as `?fixture=while-speaking-two-todos` to trigger the dev-only path.

- [ ] **Step 2: Run the hook tests to verify they fail**

Run:

```bash
cd frontend && pnpm test:run frontend/src/hooks/useTranscript.test.tsx
```

Expected: FAIL because no fixture mode exists yet.

- [ ] **Step 3: Implement the minimal fixture-audio path**

Update `frontend/src/hooks/useTranscript.ts` so that when the dev-only fixture query param is present:
- websocket connection still targets `/ws`
- microphone capture is bypassed
- the PCM fixture is loaded from `/dev-fixtures/while-speaking-two-todos/audio.pcm`
- chunks are sent on the same websocket flow the real UI already uses
- the UI still transitions through `connecting` -> `recording` -> `idle`
- the user still ends the session with the real `Finish Session` button

Add the fixture asset under `frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm`.

- [ ] **Step 4: Re-run the hook tests**

Run:

```bash
cd frontend && pnpm test:run frontend/src/hooks/useTranscript.test.tsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useTranscript.ts frontend/src/hooks/useTranscript.test.tsx frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm
git commit -m "feat: add dev fixture audio mode to real frontend"
```

## Task 1.4: Run the real-UI gates and final verification

**Purpose:**
Prove the actual app UI works against both local runtimes and that runtime selection / Worker compatibility are explicit and correct.

**Files:**
- No new implementation files required beyond Tasks 1.1-1.3 unless a final narrow fix is discovered during gate execution

**Supports:**
- Acceptance Gate: `Real App UI Works Against Both Local Runtimes`
- Acceptance Gate: `Local Runtime Selection And Worker Compatibility Are Explicit And Correct`
- Supporting Verification: all commands in `Supporting Verification`

- [ ] **Step 1: Run frontend and Cloudflare supporting verification**

Run:

```bash
cd frontend && pnpm test:run frontend/src/hooks/useTranscript.test.tsx vite.config.test.ts
cd frontend && pnpm build
cd frontend && pnpm lint
cd cloudflare && uv run pytest tests/test_entry.py tests/test_ws_smoke.py -v
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
```

Expected: PASS

- [ ] **Step 2: Run the FastAPI real-UI gate**

Run the FastAPI-mode setup and `agent-browser` procedure from `Gate Execution`.

Expected:
- todo card text `Buy oat milk` appears
- transcript details show `By oat milk tonight. Zen email Sarah the revised budget.`

- [ ] **Step 3: Run the Cloudflare real-UI gate**

Run the Cloudflare-mode setup and the same `agent-browser` procedure from `Gate Execution`.

Expected:
- the same real UI behavior appears through the Cloudflare runtime

- [ ] **Step 4: Run the config/compatibility gate**

Run:

```bash
rg -n "WS_BACKEND|BACKEND_PORT|CLOUDFLARE_PORT" frontend/vite.config.ts
rg -n "session|uuid|parse_qs|urlparse" cloudflare/src/entry.py
cd frontend && pnpm test:run vite.config.test.ts
cd cloudflare && uv run pytest tests/test_entry.py::test_worker_accepts_plain_ws_without_session_query tests/test_entry.py::test_worker_preserves_explicit_session_query -v
cd frontend && WS_BACKEND=bogus pnpm dev --host 127.0.0.1 --port 5173
```

Expected:
- explicit routing code is visible
- targeted tests PASS
- invalid config run fails clearly

- [ ] **Step 5: Commit**

```bash
git add frontend/vite.config.ts frontend/vite.config.test.ts frontend/src/hooks/useTranscript.ts frontend/src/hooks/useTranscript.test.tsx frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm cloudflare/src/entry.py cloudflare/tests/test_entry.py cloudflare/tests/test_ws_smoke.py
git commit -m "feat: wire real frontend to fastapi and cloudflare runtimes"
```
