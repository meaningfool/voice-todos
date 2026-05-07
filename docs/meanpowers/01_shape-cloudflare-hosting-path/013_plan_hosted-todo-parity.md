# Plan: Hosted Todo Parity

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [013_spec_hosted-todo-parity.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/013_spec_hosted-todo-parity.md)

**Goal:** Move todo extraction behavior behind a shared coordinator so the local FastAPI `/ws` path and the hosted Cloudflare `/ws` path produce the same live todo updates, final-stop todo handling, fallback resend behavior, warning behavior, and `todos` before `stopped` ordering.

**Architecture:** Keep the shared transcript/session core from `V1` and the hosted runtime from `V2`. Evolve `backend/app/extraction_loop.py` into the shared todo coordinator, keep extraction implementation in `backend/app/extract.py`, refactor `backend/app/ws.py` to consume structured stop outcomes, then wire `cloudflare/src/session_runtime.py` through the same coordinator. The hosted runtime should reuse the real shared extraction stack instead of reimplementing todo policy.

**Tech Stack:** Python 3.12+, FastAPI websocket flow, Cloudflare workers-py / workers-runtime-sdk / pywrangler, pydantic-ai extraction, pytest, pytest-asyncio, ruff, ty, `agent-browser`

---

## Scope

This plan covers exactly five deliverables:

1. Evolve `ExtractionLoop` into a shared todo coordinator with structured stop outcomes that encode final extraction, fallback resend, timeout skip, and warning behavior.
2. Refactor the local FastAPI `/ws` adapter to delegate todo policy to the shared coordinator instead of keeping stop/fallback logic inline.
3. Make the shared todo/extraction stack importable and runnable from the hosted Cloudflare app, including the extraction runtime prerequisites needed for live validation.
4. Wire the hosted Durable Object session runtime through the shared todo coordinator and add hosted acceptance coverage for todo parity.
5. Extend the hosted smoke/browser harnesses and run the full `V3` gate plus live `agent-browser` validation.

Out of scope for this plan:

- changing the `V2` transcript/runtime ownership split
- redesigning the browser `/ws` protocol
- adding hosted provider parity beyond the current extraction default path
- adding todo persistence or storage
- moving the shared core out of `backend/app/`

---

## File Map

### Shared todo core

| File | Responsibility |
|------|----------------|
| `backend/app/extraction_loop.py` | Shared todo trigger policy, background extraction serialization, latest snapshot state, and structured stop outcomes |
| `backend/tests/test_extraction_loop.py` | Unit coverage for trigger policy, final-stop outcomes, resend behavior, warning behavior, and cancellation safety |

### Local adapter and acceptance surface

| File | Responsibility |
|------|----------------|
| `backend/app/ws.py` | Local `/ws` adapter; should send browser messages but stop owning todo-policy branches |
| `backend/tests/test_ws.py` | Local `/ws` acceptance tests that prove live todo updates, final-stop behavior, fallback resend, warning behavior, and ordering |

### Hosted adapter and hosted reuse surface

| File | Responsibility |
|------|----------------|
| `cloudflare/src/session_runtime.py` | Hosted session owner; should mirror local todo behavior through the shared coordinator |
| `cloudflare/tests/test_session_runtime.py` | Hosted acceptance tests for live todos, final-stop behavior, warning behavior, fallback resend, and terminal ordering |
| `cloudflare/src/settings.py` | Hosted runtime config and any extraction-runtime bindings needed by the shared extractor |
| `cloudflare/wrangler.jsonc` | Hosted runtime bindings for transcript + extraction live validation |
| `cloudflare/pyproject.toml` | Hosted dependency surface for the shared extraction stack |
| `cloudflare/src/app/models.py` | Shared module mirror so hosted code can import the real `Todo` / extraction models |
| `cloudflare/src/app/extraction_loop.py` | Shared module mirror for the todo coordinator |
| `cloudflare/src/app/extract.py` | Shared module mirror for the extraction engine seam |
| `cloudflare/src/app/model_providers.py` | Shared module mirror for extraction provider selection |
| `cloudflare/src/app/backend_env.py` | Shared module mirror for extraction env lookup |
| `cloudflare/src/app/config.py` | Shared module mirror for shared extractor settings fallback |
| `cloudflare/src/app/prompts/registry.py` | Shared module mirror for extraction prompt loading |
| `cloudflare/src/app/prompts/todo_extraction/v1.md` | Shared prompt asset required by the hosted extractor |

### Hosted smoke and browser validation

| File | Responsibility |
|------|----------------|
| `cloudflare/scripts/ws_smoke.py` | Hosted websocket smoke driver; add todo-parity mode and ordering assertions |
| `cloudflare/dev/todo_parity_browser_check.html` | Tracked browser harness for final `agent-browser` validation against the hosted `/ws` path |

---

## Acceptance Gates From Spec

## Acceptance Gate: Local And Hosted Todo Behavior Are Identical

**Why this gate matters:**
This is the actual delta from `V2`. If local and hosted todo behavior are still materially different, then `V3` has not delivered its slice.

**Criteria:**

- Given the same transcript/extraction conditions, the local `/ws` path and the hosted `/ws` path produce the same todo behavior.
- "Same todo behavior" means:
  - the same live `todos` updates are emitted when extraction triggers fire
  - on `stop`, both use the finalized transcript for final todo handling
  - if no new final todo send occurs but the latest snapshot must be preserved, both resend the latest `todos` snapshot before `stopped`
  - both attach the same warning behavior for transcript timeout and final extraction failure
  - both preserve `todos` before `stopped` ordering when a todo send is required

**Proof:**

- **Local proof:** focused FastAPI `/ws` acceptance tests
- **Hosted proof:** focused Cloudflare acceptance tests or smoke/harness proof
- **Assertions:** verify live todo updates, final-stop extraction behavior, fallback resend behavior, warning behavior, and terminal message ordering are the same in both runtimes for the covered conditions
- **Structural proof:** inspect the code to show both adapters delegate todo behavior to the shared todo core instead of carrying separate todo-policy branches
- **Expected evidence:** local acceptance output, hosted acceptance or smoke output, and code references to the shared todo-core boundary

---

## Gate Execution

### Behavioral proof for `Local And Hosted Todo Behavior Are Identical`

Local proof:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  tests/test_ws.py::test_ws_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

Hosted proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_session_runtime.py::test_hosted_session_stop_surfaces_final_extraction_failure \
  tests/test_session_runtime.py::test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

Hosted smoke / harness proof:

In terminal A:

```bash
cd cloudflare && SONIOX_API_KEY="$SONIOX_API_KEY" GEMINI_API_KEY="$GEMINI_API_KEY" uv run pywrangler dev --port 8788
```

In terminal B:

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

Expected: PASS

Structural proof:

```bash
rg -n "ExtractionLoop|on_endpoint\\(|on_transcript_changed\\(|on_stop\\(" backend/app/ws.py cloudflare/src/session_runtime.py
rg -n "latest_todo_items|todo_send_count|Todo extraction failed|Timed out waiting for the final transcript; todos were not extracted\\." backend/app/ws.py cloudflare/src/session_runtime.py
```

Expected:

- first command shows both adapters using the shared todo coordinator API
- second command returns no matches after the refactor, proving adapter-local todo-policy state and warning strings were removed from the adapters

Evidence to collect:

- local acceptance output
- hosted acceptance output
- hosted smoke output from `scripts/ws_smoke.py`
- code references to [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extraction_loop.py), [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py), and [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)

---

## Supporting Verification

Shared todo-core verification:

```bash
cd backend && uv run pytest tests/test_extraction_loop.py -v
```

Hosted runtime verification:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -v
```

Focused shared-session regression checks if touched incidentally:

```bash
cd backend && uv run pytest tests/test_live_session.py -v
```

Static checks:

```bash
cd backend && uv run ruff check app/extraction_loop.py app/ws.py tests/test_extraction_loop.py tests/test_ws.py
cd backend && uv run ty check app/extraction_loop.py app/ws.py
cd cloudflare && uv run ruff check src tests scripts dev
cd cloudflare && uv run ty check src
```

Expected:

- focused shared todo-core tests PASS
- hosted session-runtime suite PASS
- local shared-session regressions PASS if run
- `ruff check` clean in both apps
- `ty check` exits `0`; existing Worker fallback `unsupported-base` warnings may remain unless this slice removes them

Live browser validation before claiming completion:

In terminal C:

```bash
python3 -m http.server 8790
```

In terminal D:

```bash
agent-browser open http://127.0.0.1:8790/cloudflare/dev/todo_parity_browser_check.html
agent-browser snapshot -i
agent-browser click @e1
agent-browser wait --text PASS
agent-browser snapshot -i
```

Expected: the harness reports `PASS` after the hosted `/ws` path emits transcript activity, at least one `todos` message, and terminal `stopped`

---

## Task 3.1: Add structured stop outcomes to the shared todo coordinator

**Purpose:**
Move final-stop todo policy into `ExtractionLoop` so both adapters can consume the same stop semantics instead of rebuilding warning, fallback resend, and unchanged-transcript logic themselves.

**Files:**
- Modify: `backend/app/extraction_loop.py`
- Modify: `backend/tests/test_extraction_loop.py`

**Supports:**
- Acceptance Gate: `Local And Hosted Todo Behavior Are Identical`
- Supporting Verification: `cd backend && uv run pytest tests/test_extraction_loop.py -v`

- [ ] **Step 1: Write the failing stop-outcome tests**

Add focused tests in `backend/tests/test_extraction_loop.py` for:
- `test_on_stop_returns_resend_outcome_when_final_transcript_is_unchanged`
- `test_on_stop_returns_timeout_outcome_without_running_extraction`
- `test_on_stop_returns_warning_outcome_on_final_extraction_failure`

Model the new return type explicitly, for example:

```python
outcome = await loop.on_stop(
    final_transcript_text="Buy milk tomorrow",
    transcript_timed_out=False,
)

assert outcome.items_to_send == [Todo(text="Buy milk tomorrow")]
assert outcome.warning is None
assert outcome.should_resend_latest_snapshot is False
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_extraction_loop.py -k "resend_outcome or timeout_outcome or warning_outcome" -v
```

Expected: FAIL because `ExtractionLoop.on_stop` does not yet accept finalized transcript inputs or return a structured outcome

- [ ] **Step 3: Implement the minimal shared stop outcome**

In `backend/app/extraction_loop.py`:
- add a small dataclass such as `TodoStopOutcome`
- change `on_stop` to accept `final_transcript_text` and `transcript_timed_out`
- skip extraction and return a timeout warning outcome when the transcript timed out
- skip re-extraction and request resend when the final transcript is unchanged
- run final extraction against the finalized transcript when needed
- return warning/fallback metadata instead of making adapters reconstruct it

- [ ] **Step 4: Run the extraction-loop suite**

Run:

```bash
cd backend && uv run pytest tests/test_extraction_loop.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction_loop.py backend/tests/test_extraction_loop.py
git commit -m "refactor: add shared todo stop outcomes"
```

---

## Task 3.2: Refactor the local `/ws` adapter through the shared todo coordinator

**Purpose:**
Keep the local behavior intact while removing local-only todo-policy branches from `backend/app/ws.py`.

**Files:**
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

**Supports:**
- Acceptance Gate: `Local And Hosted Todo Behavior Are Identical`
- Supporting Verification: local proof command in `Gate Execution`

- [ ] **Step 1: Write the failing local adapter mapping test**

Add a focused adapter test in `backend/tests/test_ws.py` that patches `ExtractionLoop.on_stop` to return a structured stop outcome and asserts the adapter:
- sends `todos` before `stopped` when `items_to_send` is present
- resends the latest snapshot when the outcome requests it
- forwards the structured warning onto `stopped`

Use a dedicated name such as:

```python
def test_ws_stop_uses_shared_todo_stop_outcome_for_fallback_and_warning():
    ...
```

- [ ] **Step 2: Run the targeted local test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_ws.py::test_ws_stop_uses_shared_todo_stop_outcome_for_fallback_and_warning -v
```

Expected: FAIL because `backend/app/ws.py` still owns `latest_todo_items`, `todo_send_count`, and stop-warning branches directly

- [ ] **Step 3: Implement the local adapter refactor**

In `backend/app/ws.py`:
- keep `send_todos` for live/background updates
- remove `latest_todo_items` and `todo_send_count` from the adapter
- call the new `ExtractionLoop.on_stop(...)` with the finalized transcript and controller timeout status
- map the returned `TodoStopOutcome` into browser `todos` and `stopped`
- keep recorder behavior intact

- [ ] **Step 4: Run the local acceptance proof**

Run:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  tests/test_ws.py::test_ws_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ws.py backend/tests/test_ws.py
git commit -m "refactor: route local ws todos through shared coordinator"
```

---

## Task 3.3: Make the shared extraction stack reusable from the hosted app

**Purpose:**
The hosted runtime cannot use the shared todo core until the Cloudflare app can import the shared extraction modules and see the extraction provider credentials during live validation.

**Files:**
- Modify: `cloudflare/pyproject.toml`
- Modify: `cloudflare/wrangler.jsonc`
- Modify: `cloudflare/src/settings.py`
- Create: `cloudflare/src/app/models.py`
- Create: `cloudflare/src/app/extraction_loop.py`
- Create: `cloudflare/src/app/extract.py`
- Create: `cloudflare/src/app/model_providers.py`
- Create: `cloudflare/src/app/backend_env.py`
- Create: `cloudflare/src/app/config.py`
- Create: `cloudflare/src/app/prompts/registry.py`
- Create: `cloudflare/src/app/prompts/todo_extraction/v1.md`
- Create: `cloudflare/tests/test_shared_todo_imports.py`

**Supports:**
- Acceptance Gate: `Local And Hosted Todo Behavior Are Identical`
- Supporting Verification: hosted import sanity before adapter integration

- [ ] **Step 1: Write the failing hosted import test**

Create `cloudflare/tests/test_shared_todo_imports.py` with assertions that:
- `from app.extraction_loop import ExtractionLoop` succeeds under the Cloudflare test environment
- `from app.extract import extract_todos` succeeds
- `from app.prompts.registry import get_prompt_ref` returns the `todo_extraction/v1.md` prompt

- [ ] **Step 2: Run the hosted import test to verify it fails**

Run:

```bash
cd cloudflare && uv run pytest tests/test_shared_todo_imports.py -v
```

Expected: FAIL because the hosted `app/` mirror and/or hosted dependencies do not yet include the shared extraction stack

- [ ] **Step 3: Implement the hosted reuse surface**

Make the smallest coherent hosted changes:
- extend `cloudflare/src/app/` with symlinks to the shared extraction modules and prompt asset
- add the hosted dependencies needed by the shared extraction path to `cloudflare/pyproject.toml` to match the reused backend modules
- extend `cloudflare/src/settings.py` and `cloudflare/wrangler.jsonc` so local hosted dev can provide at least `GEMINI_API_KEY` to the shared extractor during live smoke/browser validation
- if the Worker environment does not expose bindings through `os.getenv`, add the smallest hosted helper needed to mirror the extraction keys into the process environment before the shared extractor runs

- [ ] **Step 4: Run the hosted import test again**

Run:

```bash
cd cloudflare && uv run pytest tests/test_shared_todo_imports.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  cloudflare/pyproject.toml \
  cloudflare/wrangler.jsonc \
  cloudflare/src/settings.py \
  cloudflare/src/app/models.py \
  cloudflare/src/app/extraction_loop.py \
  cloudflare/src/app/extract.py \
  cloudflare/src/app/model_providers.py \
  cloudflare/src/app/backend_env.py \
  cloudflare/src/app/config.py \
  cloudflare/src/app/prompts/registry.py \
  cloudflare/src/app/prompts/todo_extraction/v1.md \
  cloudflare/tests/test_shared_todo_imports.py
git commit -m "build: expose shared extraction stack to cloudflare"
```

---

## Task 3.4: Route the hosted session runtime through the shared todo coordinator

**Purpose:**
Bring the hosted runtime to todo parity by making `HostedSessionActor` mirror the local todo behavior through the shared coordinator.

**Files:**
- Modify: `cloudflare/src/session_runtime.py`
- Modify: `cloudflare/tests/test_session_runtime.py`

**Supports:**
- Acceptance Gate: `Local And Hosted Todo Behavior Are Identical`
- Supporting Verification: hosted proof command in `Gate Execution`

- [ ] **Step 1: Write the failing hosted todo acceptance tests**

Add hosted tests in `cloudflare/tests/test_session_runtime.py` named:
- `test_hosted_session_sends_todos_during_recording`
- `test_hosted_session_stop_uses_finalized_transcript_for_final_pass`
- `test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction`
- `test_hosted_session_stop_surfaces_final_extraction_failure`
- `test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning`
- `test_hosted_session_stop_sends_todos_before_stopped`

Use fake controller / fake extraction behavior so the tests prove hosted policy mapping, not external provider variance.

- [ ] **Step 2: Run the targeted hosted tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_session_runtime.py::test_hosted_session_stop_surfaces_final_extraction_failure \
  tests/test_session_runtime.py::test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped \
  -v
```

Expected: FAIL because the hosted actor currently has no todo coordinator, no live todo sends, and no shared stop-outcome mapping

- [ ] **Step 3: Implement hosted todo coordination**

In `cloudflare/src/session_runtime.py`:
- instantiate `ExtractionLoop` when the controller starts
- wire transcript-change and endpoint signals from `LiveSessionController` updates into the coordinator
- provide a hosted `send_todos` callback that emits browser `todos`
- on stop, call the shared `ExtractionLoop.on_stop(...)` and map the returned outcome into browser `todos` then `stopped`
- cancel the coordinator on provider failure, browser disconnect, cap expiry, and cleanup

- [ ] **Step 4: Run the hosted acceptance proof**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_session_runtime.py::test_hosted_session_stop_surfaces_final_extraction_failure \
  tests/test_session_runtime.py::test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/session_runtime.py cloudflare/tests/test_session_runtime.py
git commit -m "feat: add hosted todo parity through shared coordinator"
```

---

## Task 3.5: Extend smoke and browser validation, then run the full gate

**Purpose:**
Finish the slice with repeatable hosted smoke coverage and the required live browser validation.

**Files:**
- Modify: `cloudflare/scripts/ws_smoke.py`
- Create: `cloudflare/dev/todo_parity_browser_check.html`
- Create: `cloudflare/tests/test_ws_smoke.py`

**Supports:**
- Acceptance Gate: `Local And Hosted Todo Behavior Are Identical`
- Supporting Verification: hosted smoke and `agent-browser` live validation

- [ ] **Step 1: Write the failing smoke-driver test**

Create `cloudflare/tests/test_ws_smoke.py` covering the new `todo-stop` mode:
- it counts transcript messages
- it requires at least one `todos` message before `stopped`
- it fails if terminal ordering is wrong

- [ ] **Step 2: Run the smoke-driver test to verify it fails**

Run:

```bash
cd cloudflare && uv run pytest tests/test_ws_smoke.py -v
```

Expected: FAIL because `cloudflare/scripts/ws_smoke.py` does not yet implement `todo-stop`

- [ ] **Step 3: Implement the smoke mode and tracked browser harness**

In `cloudflare/scripts/ws_smoke.py`:
- add `todo-stop` mode
- track `todos` count and terminal ordering
- expose `--expect-todos-min`

In `cloudflare/dev/todo_parity_browser_check.html`:
- connect to `ws://127.0.0.1:8788/ws`
- stream `backend/tests/fixtures/while-speaking-two-todos/audio.pcm`
- require `started`, transcript activity, at least one `todos`, and terminal `stopped`
- print `PASS` / `FAIL` visibly for `agent-browser`

- [ ] **Step 4: Run the full acceptance gate and live browser validation**

Run the local proof:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  tests/test_ws.py::test_ws_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  -v
```

Run the hosted proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_reuses_latest_snapshot_without_rerunning_final_extraction \
  tests/test_session_runtime.py::test_hosted_session_stop_surfaces_final_extraction_failure \
  tests/test_session_runtime.py::test_hosted_session_stop_timeout_skips_extraction_and_surfaces_warning \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped \
  -v
```

Start the hosted runtime:

```bash
cd cloudflare && SONIOX_API_KEY="$SONIOX_API_KEY" GEMINI_API_KEY="$GEMINI_API_KEY" uv run pywrangler dev --port 8788
```

Run hosted smoke:

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

Serve the browser harness:

```bash
python3 -m http.server 8790
```

Run the live browser check:

```bash
agent-browser open http://127.0.0.1:8790/cloudflare/dev/todo_parity_browser_check.html
agent-browser snapshot -i
agent-browser click @e1
agent-browser wait --text PASS
agent-browser snapshot -i
```

Run structural proof:

```bash
rg -n "ExtractionLoop|on_endpoint\\(|on_transcript_changed\\(|on_stop\\(" backend/app/ws.py cloudflare/src/session_runtime.py
rg -n "latest_todo_items|todo_send_count|Todo extraction failed|Timed out waiting for the final transcript; todos were not extracted\\." backend/app/ws.py cloudflare/src/session_runtime.py
```

Expected:
- local acceptance PASS
- hosted acceptance PASS
- hosted smoke PASS
- browser harness reaches `PASS`
- first structural command shows both adapters using the shared coordinator
- second structural command returns no matches

- [ ] **Step 5: Run supporting verification**

Run:

```bash
cd backend && uv run pytest tests/test_extraction_loop.py tests/test_live_session.py -v
cd cloudflare && uv run pytest tests/test_session_runtime.py tests/test_shared_todo_imports.py tests/test_ws_smoke.py -v
cd backend && uv run ruff check app/extraction_loop.py app/ws.py tests/test_extraction_loop.py tests/test_ws.py
cd backend && uv run ty check app/extraction_loop.py app/ws.py
cd cloudflare && uv run ruff check src tests scripts dev
cd cloudflare && uv run ty check src
```

Expected: PASS, with `ty check` exiting `0`

- [ ] **Step 6: Commit**

```bash
git add cloudflare/scripts/ws_smoke.py cloudflare/dev/todo_parity_browser_check.html cloudflare/tests/test_ws_smoke.py
git commit -m "test: add hosted todo parity smoke and browser check"
```

---

## Checkpoint

Before any `V4` work begins:

- [ ] The acceptance gate `Local And Hosted Todo Behavior Are Identical` passes exactly as written above.
- [ ] The local proof command passes.
- [ ] The hosted proof command passes.
- [ ] The hosted `todo-stop` smoke passes against local `pywrangler dev`.
- [ ] The structural proof shows both adapters using the shared todo coordinator and no duplicated adapter-local todo-policy branches.
- [ ] The `agent-browser` live browser validation passes against `cloudflare/dev/todo_parity_browser_check.html`.
- [ ] Supporting verification is green or any residual warning is documented explicitly with evidence.

Only after this checkpoint is green should the branch move on to the next slice.
