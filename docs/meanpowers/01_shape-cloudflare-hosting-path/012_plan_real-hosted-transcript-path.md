# Plan: Real Hosted Transcript Path

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [012_spec_real-hosted-transcript-path.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/012_spec_real-hosted-transcript-path.md)

**Goal:** Add the first real Cloudflare Worker + Durable Object hosted transcript path, reusing the `V1` shared session core, preserving the browser `/ws` transcript protocol, and proving real Soniox stop/finalization behavior plus hosted session-cap teardown.

**Architecture:** Keep the shared session/transcript/finalization core in `backend/app/` for `V2`. Add a sibling `cloudflare/` app boundary with a thin Worker ingress, a session-owned Durable Object runtime, a hosted STT factory seam, and a Cloudflare-specific Soniox `SttSession` adapter. Keep hosted todo extraction intentionally out of parity until `V3`.

**Tech Stack:** Python 3.12+, workers-py, workers-runtime-sdk, pywrangler, Soniox, uv, pytest, pytest-asyncio, ruff, ty

---

## Scope

This plan covers exactly four deliverables:

1. Add a real `cloudflare/` app boundary with local Worker + Durable Object development support and a repeatable websocket smoke harness.
2. Add a hosted session runtime that reuses the shared `LiveSessionController` and preserves the browser websocket transcript contract.
3. Add a Cloudflare-specific Soniox `SttSession` adapter and hosted STT factory seam, proving the real hosted transcript/stop contract.
4. Add hosted session-cap enforcement and idempotent teardown, then run the full `V2` gates.

Out of scope for this plan:

- hosted todo extraction parity
- hosted STT provider parity beyond Soniox
- hosted LLM/extraction provider parity
- moving the shared core out of `backend/app/`
- publishability/deployment docs or deploy-button packaging

---

## File Map

### Cloudflare app - New files

| File | Responsibility |
|------|----------------|
| `cloudflare/pyproject.toml` | Dedicated Cloudflare app dependency set and test tooling for the hosted runtime |
| `cloudflare/wrangler.jsonc` | Worker entrypoint, Durable Object binding, compatibility flags, and required hosted secrets/config |
| `cloudflare/src/repo_bootstrap.py` | Repo-relative shared-core import bootstrap for `V2`, so hosted code can import `backend/app` without moving the shared core yet |
| `cloudflare/src/settings.py` | Hosted runtime config such as session-cap milliseconds and hosted STT provider selection |
| `cloudflare/src/entry.py` | Thin Worker `/ws` ingress and Durable Object routing |
| `cloudflare/src/session_runtime.py` | Durable Object wrapper plus hosted session actor that owns the browser websocket, shared controller, cap, and teardown |
| `cloudflare/src/stt_factory_cf.py` | Hosted STT factory seam that preserves provider selection shape but only implements Soniox in `V2` |
| `cloudflare/src/stt_soniox_cf.py` | Cloudflare Soniox `SttSession` adapter using the Python Worker websocket mechanics proven in `X7` |
| `cloudflare/tests/test_session_runtime.py` | Focused hosted session actor tests for start, invalid control messages, stop flow, relay failure, cap expiry, and cleanup |
| `cloudflare/tests/test_stt_soniox_cf.py` | Focused Cloudflare Soniox adapter tests for connect/send/receive/finalization behavior |
| `cloudflare/scripts/ws_smoke.py` | Browser-style websocket smoke driver for the hosted `/ws` endpoint using a real PCM fixture |

### Backend - Existing files expected to remain shared

| File | Why it matters |
|------|----------------|
| `backend/app/live_session.py` | Shared session/transcript/finalization core reused by both adapters |
| `backend/app/stt.py` | Existing `SttSession`, `SttEvent`, and capability contracts that the hosted adapter must preserve |
| `backend/app/transcript_accumulator.py` | Existing transcript state contract reused by the hosted path |
| `backend/app/ws.py` | Local FastAPI adapter that should remain behaviorally intact in `V2` |
| `backend/app/stt_factory.py` | Current local provider seam reference for preserving hosted factory shape |
| `backend/tests/fixtures/stop-the-button/audio.pcm` | Deterministic audio fixture for hosted live smoke and stop-contract proof |
| `frontend/src/hooks/useTranscript.ts` | Browser websocket contract the hosted path must preserve |
| `research/x6-cloudflare-session-skeleton/src/entry.py` | Worker + Durable Object routing and session-cap proof reference |
| `research/x7-soniox-provider-transport/src/entry.py` | Cloudflare Soniox websocket mechanics and finalize/EOS proof reference |

### Existing files to modify only if narrowly required

| File | Reason |
|------|--------|
| `backend/app/live_session.py` | Only if a small hosted integration seam is required |
| `backend/app/stt.py` | Only if a tiny contract clarification is required for the hosted adapter |

---

## Acceptance Gates From Spec

## Acceptance Gate: Hosted Transcript Session Works End To End Through The Real Cloudflare Runtime

**Why this gate matters:**
This is the core blocking outcome of `V2`. If the real hosted runtime cannot own a browser session, stream transcript updates, and return a finalized transcript on stop, then the slice has not delivered the first real Cloudflare path.

**Criteria:**

- When a browser-style client connects to the hosted `/ws` endpoint, the Cloudflare runtime accepts the session and returns the existing browser `started` message.
- While the client streams audio, the hosted runtime emits browser-compatible `transcript` messages driven by the real Soniox path rather than local stubs.
- When the client stops the session, the hosted runtime preserves the app's current stop contract: request finalization, send EOS, wait for final transcript completion/finalization, and return `stopped` with the finalized transcript.
- The hosted runtime keeps session ownership inside one Durable Object rather than splitting transcript/finalization state across the Worker and another layer.

**Proof:**

- **Setup:** Run the real Cloudflare app locally in the supported Worker + Durable Object dev runtime with valid Soniox credentials and a known PCM fixture or equivalent deterministic audio input.
- **Action:** Open a websocket session to the hosted `/ws` endpoint, send the browser `start` control, stream the test audio as browser binary frames, then send `stop`.
- **Assertions:** Verify the browser-visible message sequence includes `started`, one or more `transcript` messages, and a terminal `stopped` containing the finalized transcript; verify the stop path matches the current finalize-then-EOS contract through the hosted Soniox adapter; verify the transcript is produced by the real hosted path rather than a local fake.
- **Structural assertions:** Inspect the hosted implementation to show the Worker handles upgrade/routing only, while the Durable Object owns the session controller and transcript/finalization state.
- **Expected evidence:** command or procedure output from the local Cloudflare runtime test, the observed browser-message sequence, and code references showing the Worker/DO ownership boundary.

## Acceptance Gate: Hosted Session Cap And Teardown Are Enforced Intentionally

**Why this gate matters:**
`V2` includes session policy and teardown as a first-class hosted requirement. A transcript path that only works when stopped manually is incomplete for the public demo shape.

**Criteria:**

- When a hosted session exceeds the configured cap, the runtime terminates it server-side without requiring the browser to stop first.
- Cap expiry follows an intentional terminal path: the browser receives the appropriate terminal session message behavior for this slice, and the websocket closes cleanly instead of hanging or dying implicitly.
- Browser disconnect, manual stop, provider failure, and cap expiry all converge on an idempotent hosted cleanup path.

**Proof:**

- **Setup:** Run the local Cloudflare app with a short configured session cap.
- **Action:** Open a websocket session to the hosted `/ws` endpoint and keep it open past the cap without sending `stop`; separately exercise manual stop, browser disconnect, and a provider/relay failure path.
- **Assertions:** Verify cap expiry produces the intended terminal behavior and close path; verify repeated or competing teardown triggers do not double-close or leave the session running; verify hosted cleanup remains stable across the exercised end states.
- **Expected evidence:** local runtime logs or observed browser events from the cap-expiry session, plus targeted hosted tests or inspections proving idempotent cleanup across the teardown cases.

---

## Gate Execution

### Behavioral proof for `Hosted Transcript Session Works End To End Through The Real Cloudflare Runtime`

Run:

```bash
cd cloudflare && uv sync
```

In terminal A:

```bash
cd cloudflare && SONIOX_API_KEY="$SONIOX_API_KEY" uv run pywrangler dev --port 8788
```

In terminal B:

```bash
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --fixture-path ../backend/tests/fixtures/stop-the-button/audio.pcm \
  --mode transcript-stop \
  --session-id smoke-transcript-stop \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1 \
  --expect-final-transcript "Stop the button."
```

Expected: PASS

Structural proof:

```bash
cd cloudflare && uv run python - <<'PY'
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


entry_imports = module_imports("src/entry.py")
assert "app.live_session" not in entry_imports, entry_imports
assert any("session_runtime" in name for name in entry_imports), entry_imports

runtime_imports = module_imports("src/session_runtime.py")
assert "app.live_session" in runtime_imports, runtime_imports

print("boundary-ok")
PY
```

Expected: prints `boundary-ok`

Evidence to collect:

- `pywrangler dev` output showing the local Worker + Durable Object runtime started
- smoke-script output showing `started`, transcript activity, and terminal `stopped`
- code references to `cloudflare/src/entry.py` and `cloudflare/src/session_runtime.py`

### Behavioral proof for `Hosted Session Cap And Teardown Are Enforced Intentionally`

In terminal A:

```bash
cd cloudflare && SONIOX_API_KEY="$SONIOX_API_KEY" SESSION_CAP_MS=5000 uv run pywrangler dev --port 8788
```

In terminal B:

```bash
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --mode cap-expiry \
  --session-id smoke-cap-expiry \
  --hold-open-ms 6500 \
  --expect-terminal-type stopped \
  --expect-close-code 1000
```

Expected: PASS

Teardown-path proof:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "manual_stop or browser_disconnect or provider_failure or cap_expiry" -v
```

Expected: PASS

Evidence to collect:

- smoke-script output showing terminal behavior and clean close after cap expiry
- targeted hosted test output covering manual stop, disconnect, provider failure, and cap-expiry cleanup convergence

---

## Supporting Verification

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py tests/test_stt_soniox_cf.py -v
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
cd backend && uv run pytest \
  tests/test_live_session.py \
  tests/test_ws.py::test_ws_start_sends_started_when_soniox_connects \
  tests/test_ws.py::test_soniox_transcript_state_acceptance \
  tests/test_ws.py::test_ws_stop_requests_final_transcript_before_end_of_stream \
  tests/test_ws.py::test_ws_stop_surfaces_final_extraction_failure \
  -v
```

Expected:

- hosted session-runtime unit tests PASS
- hosted Soniox adapter unit tests PASS
- `ruff check` clean for the hosted app
- `ty check` clean for the hosted app
- focused local shared-core / FastAPI regression checks PASS

---

## Task 2.1: Scaffold the hosted app boundary and hosted session actor test surface

**Purpose:**
Create the real `cloudflare/` app area, make shared-core imports possible without relocating the shared core yet, and establish a hosted session actor seam that can be tested below full local-runtime acceptance.

**Files:**
- Create: `cloudflare/pyproject.toml`
- Create: `cloudflare/wrangler.jsonc`
- Create: `cloudflare/src/repo_bootstrap.py`
- Create: `cloudflare/src/settings.py`
- Create: `cloudflare/src/entry.py`
- Create: `cloudflare/src/session_runtime.py`
- Create: `cloudflare/scripts/ws_smoke.py`
- Create: `cloudflare/tests/test_session_runtime.py`

**Supports:**
- Acceptance Gate: Hosted Session Cap And Teardown Are Enforced Intentionally
- Supporting Verification: hosted session-runtime unit tests, hosted app static checks

- [ ] **Step 1: Write the failing hosted session actor tests**

Add focused tests such as:

```python
@pytest.mark.asyncio
async def test_hosted_session_start_sends_started_message():
    ...


@pytest.mark.asyncio
async def test_hosted_session_unknown_control_message_returns_browser_error():
    ...
```

- [ ] **Step 2: Run the hosted session actor tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "start_sends_started or unknown_control_message" -v
```

Expected: FAIL because the hosted app files do not exist yet

- [ ] **Step 3: Implement the minimal hosted app scaffold**

Create:

- `pyproject.toml` with `workers-py`, `workers-runtime-sdk`, `pytest`, `pytest-asyncio`, `ruff`, `ty`, and `websockets` in the appropriate dependency groups
- `wrangler.jsonc` with a single Durable Object binding and `python_workers` compatibility
- `repo_bootstrap.py` to expose `backend/app` imports to the hosted runtime without copying shared-core code
- `settings.py` for hosted env/config access
- `entry.py` with a thin `/ws` upgrade + routing boundary
- `session_runtime.py` with a plain hosted session actor plus the Durable Object wrapper
- `scripts/ws_smoke.py` skeleton that can connect to a hosted websocket endpoint and print the observed message sequence

- [ ] **Step 4: Run the focused hosted session tests to verify they pass**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "start_sends_started or unknown_control_message" -v
```

Expected: PASS

- [ ] **Step 5: Commit the hosted app scaffold**

```bash
git add cloudflare/pyproject.toml cloudflare/wrangler.jsonc cloudflare/src/repo_bootstrap.py cloudflare/src/settings.py cloudflare/src/entry.py cloudflare/src/session_runtime.py cloudflare/scripts/ws_smoke.py cloudflare/tests/test_session_runtime.py
git commit -m "build: scaffold cloudflare hosted app"
```

---

## Task 2.2: Route the hosted session actor through the shared controller and hosted STT factory seam

**Purpose:**
Make the Durable Object runtime reuse the shared `LiveSessionController` instead of owning transcript/finalization logic itself, while preserving a hosted provider seam even though only Soniox is implemented in `V2`.

**Files:**
- Create: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/src/session_runtime.py`
- Modify: `cloudflare/tests/test_session_runtime.py`

**Supports:**
- Acceptance Gate: Hosted Transcript Session Works End To End Through The Real Cloudflare Runtime
- Supporting Verification: hosted session-runtime unit tests

- [ ] **Step 1: Write the failing controller-wiring tests**

Add focused tests such as:

```python
@pytest.mark.asyncio
async def test_hosted_session_start_builds_controller_with_hosted_factory():
    ...


@pytest.mark.asyncio
async def test_hosted_session_binary_audio_frames_forward_to_controller():
    ...


@pytest.mark.asyncio
async def test_hosted_session_relay_errors_return_browser_error():
    ...
```

- [ ] **Step 2: Run the controller-wiring tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "builds_controller or forward_to_controller or relay_errors_return_browser_error" -v
```

Expected: FAIL because the hosted session actor is not yet wired through the shared controller

- [ ] **Step 3: Implement minimal controller integration**

Add:

- a hosted STT factory seam in `stt_factory_cf.py`
- hosted session actor integration with `app.live_session.LiveSessionController`
- browser `started`, `transcript`, `error`, and `stopped` mapping in the hosted session actor
- explicit unsupported-provider errors for hosted providers other than Soniox in `V2`

- [ ] **Step 4: Run the controller-wiring tests to verify they pass**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "builds_controller or forward_to_controller or relay_errors_return_browser_error" -v
```

Expected: PASS

- [ ] **Step 5: Commit the shared-controller hosted runtime wiring**

```bash
git add cloudflare/src/stt_factory_cf.py cloudflare/src/session_runtime.py cloudflare/tests/test_session_runtime.py
git commit -m "refactor: route hosted sessions through shared controller"
```

---

## Task 2.3: Add the Cloudflare Soniox adapter and prove the real hosted transcript path

**Purpose:**
Implement the real hosted Soniox transport under the existing `SttSession` contract and prove the actual hosted transcript + stop contract end to end through the local Cloudflare runtime.

**Files:**
- Create: `cloudflare/src/stt_soniox_cf.py`
- Create: `cloudflare/tests/test_stt_soniox_cf.py`
- Modify: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/scripts/ws_smoke.py`

**Supports:**
- Acceptance Gate: Hosted Transcript Session Works End To End Through The Real Cloudflare Runtime
- Supporting Verification: hosted Soniox adapter unit tests, hosted app static checks

- [ ] **Step 1: Write the failing Cloudflare Soniox adapter tests**

Add focused tests such as:

```python
@pytest.mark.asyncio
async def test_cf_soniox_connect_uses_fetch_upgrade_websocket():
    ...


@pytest.mark.asyncio
async def test_cf_soniox_session_preserves_finalize_then_eos_calls():
    ...


@pytest.mark.asyncio
async def test_cf_soniox_session_sets_finalization_event_on_fin_token():
    ...
```

- [ ] **Step 2: Run the Cloudflare Soniox adapter tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_stt_soniox_cf.py -v
```

Expected: FAIL because the Cloudflare Soniox adapter does not exist yet

- [ ] **Step 3: Implement the Cloudflare Soniox `SttSession` adapter**

Use the `X7` proof as the concrete transport reference and implement:

- outbound websocket connect through the Cloudflare Python Worker surface
- Soniox config send
- binary audio sends
- `request_final_transcript()`
- `end_stream()`
- incoming Soniox event translation into the existing `SttEvent` contract
- finalization-event handling that matches the current `<fin>` stop rule

- [ ] **Step 4: Run the focused Cloudflare Soniox adapter tests to verify they pass**

Run:

```bash
cd cloudflare && uv run pytest tests/test_stt_soniox_cf.py -v
```

Expected: PASS

- [ ] **Step 5: Run the hosted transcript acceptance gate**

Run the Gate 1 commands from `Gate Execution`.

Expected:

- smoke script PASS
- structural proof prints `boundary-ok`

- [ ] **Step 6: Commit the hosted Soniox transport**

```bash
git add cloudflare/src/stt_soniox_cf.py cloudflare/src/stt_factory_cf.py cloudflare/tests/test_stt_soniox_cf.py cloudflare/scripts/ws_smoke.py
git commit -m "feat: add cloudflare soniox stt adapter"
```

---

## Task 2.4: Enforce hosted session cap and idempotent teardown, then run the full slice verification

**Purpose:**
Finish the hosted runtime by adding the public-demo session cap, intentional cap-expiry terminal behavior, and unified teardown across manual stop, disconnect, provider failure, and cap expiry.

**Files:**
- Modify: `cloudflare/src/settings.py`
- Modify: `cloudflare/src/session_runtime.py`
- Modify: `cloudflare/tests/test_session_runtime.py`
- Modify: `cloudflare/scripts/ws_smoke.py`
- Modify: `cloudflare/wrangler.jsonc` if a config binding is needed for local cap control

**Supports:**
- Acceptance Gate: Hosted Session Cap And Teardown Are Enforced Intentionally
- Supporting Verification: hosted session-runtime unit tests, local backend regression checks

- [ ] **Step 1: Write the failing cap/cleanup tests**

Add focused tests such as:

```python
@pytest.mark.asyncio
async def test_hosted_session_cap_expiry_sends_terminal_message_once():
    ...


@pytest.mark.asyncio
async def test_hosted_session_cleanup_is_idempotent_across_disconnect_provider_failure_and_cap():
    ...
```

- [ ] **Step 2: Run the cap/cleanup tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "cap_expiry or cleanup_is_idempotent" -v
```

Expected: FAIL because cap enforcement and unified teardown are not complete yet

- [ ] **Step 3: Implement hosted session cap and unified teardown**

Add:

- hosted session-cap scheduling/alarm behavior
- one cleanup path for manual stop, browser disconnect, provider failure, and cap expiry
- clean websocket close behavior on cap expiry
- smoke-script support for the cap-expiry scenario

- [ ] **Step 4: Run the cap/cleanup tests to verify they pass**

Run:

```bash
cd cloudflare && uv run pytest tests/test_session_runtime.py -k "cap_expiry or cleanup_is_idempotent" -v
```

Expected: PASS

- [ ] **Step 5: Run the hosted cap/teardown acceptance gate**

Run the Gate 2 commands from `Gate Execution`.

Expected: PASS

- [ ] **Step 6: Run the full supporting verification suite**

Run the full `Supporting Verification` commands from this plan.

Expected: PASS

- [ ] **Step 7: Commit the hosted cap/teardown path**

```bash
git add cloudflare/src/settings.py cloudflare/src/session_runtime.py cloudflare/tests/test_session_runtime.py cloudflare/scripts/ws_smoke.py cloudflare/wrangler.jsonc
git commit -m "feat: enforce hosted session cap and teardown"
```

---

## Checkpoint

Do not start `V3` until both `V2` acceptance gates and the supporting verification above all pass.

`V2` is complete only when:

- the hosted transcript smoke path passes against the real local Worker + Durable Object runtime
- the Worker/DO ownership boundary proof passes
- the hosted cap-expiry smoke path passes
- the hosted teardown-path tests pass
- the hosted unit/static checks pass
- the focused local shared-core / FastAPI regression checks pass

---

## Recommended First Execution Order

1. `Task 2.1`
2. `Task 2.2`
3. `Task 2.3`
4. `Task 2.4`

This order keeps the Worker/DO boundary, shared-controller reuse, real Soniox transport, and cap/teardown behavior as separate coherent increments while delaying the only real-credential live proof until the hosted runtime is structurally ready for it.
