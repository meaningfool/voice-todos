# Item 8: STT Provider Abstraction Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-10-item8-stt-provider-abstraction-design.md`

**Goal:** Refactor the production STT path so `/ws` uses an injectable provider abstraction while preserving the current Soniox behavior.

**Architecture:** Extract a small provider-neutral STT contract into `backend/app/`, move Soniox transport and event translation into its own adapter module, and keep `backend/app/ws.py` focused on browser orchestration plus extraction flow. The default provider remains Soniox, but future providers should be injectable through one factory/settings seam instead of more `if provider == ...` logic in `ws.py`.

**Tech Stack:** FastAPI, websockets, pytest, Pydantic settings, Soniox realtime STT

---

## Scope

This plan covers exactly four deliverables:

1. Lock the current Soniox behavior with adapter-focused and websocket-focused tests.
2. Introduce provider-neutral STT session and event types in `backend/app/`.
3. Move Soniox-specific transport/config/finalization logic into a dedicated adapter.
4. Wire `/ws` through a provider factory while keeping the current production defaults.

Out of scope for this plan:

- WER or latency reporting
- STT benchmark datasets or benchmark files
- top-level `evals/` benchmark execution
- changing the default production provider
- browser contract redesign

---

## File Map

### Backend - New files

| File | Responsibility |
|------|----------------|
| `backend/app/stt.py` | Provider-neutral STT protocols, dataclasses, and normalized event types |
| `backend/app/stt_factory.py` | Central provider-construction path keyed off settings |
| `backend/app/stt_soniox.py` | Soniox adapter implementation, including config payload, session operations, and event translation |
| `backend/tests/test_stt_soniox.py` | Unit tests for Soniox adapter behavior and normalized event translation |

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/ws.py` | Replace direct Soniox websocket handling with provider abstraction calls |
| `backend/app/transcript_accumulator.py` | Accept normalized provider events instead of raw Soniox payloads if needed |
| `backend/app/config.py` | Add explicit provider-selection seam and optional future-provider settings without changing current production requirements |
| `backend/tests/test_ws.py` | Update websocket tests to assert the new abstraction boundary while preserving current behavior |
| `backend/tests/test_config.py` | Verify the provider settings surface stays backward compatible |

### Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/tests/test_soniox_integration.py` | Locks the real finalize-before-end behavior against Soniox |
| `backend/tests/test_replay.py` | Shows how transcript assembly currently behaves against saved Soniox traces |
| `backend/app/extraction_loop.py` | Consumes endpoint and final transcript state after STT events land |

---

## Task 1: Lock current Soniox behavior in tests

**Files:**
- Add: `backend/tests/test_stt_soniox.py`
- Modify: `backend/tests/test_ws.py`

Before refactoring, lock the current behavior in focused tests so the adapter
split is constrained by evidence rather than memory.

- [ ] **Step 1: Add failing adapter-focused tests**

Add tests in `backend/tests/test_stt_soniox.py` that prove:

1. the Soniox config payload still uses `stt-rt-v4`, `pcm_s16le`, `16000`, and `1` channel
2. Soniox `<fin>` and `<end>` markers are translated into normalized app-level flags
3. the adapter exposes the same finalize-then-end behavior the app currently expects

Suggested cases:

```python
def test_build_soniox_config_matches_current_production_defaults():
    ...

def test_translate_soniox_event_sets_fin_and_endpoint_flags():
    ...
```

- [ ] **Step 2: Add failing websocket regression coverage**

Extend `backend/tests/test_ws.py` with focused checks that prove:

1. `/ws` still sends `started` after the upstream session opens
2. `stop` still triggers finalization before end-of-stream
3. the final extraction path still waits for transcript finalization

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_stt_soniox.py tests/test_ws.py -v
```

Expected: FAIL because the adapter module and abstraction seam do not exist yet

- [ ] **Step 4: Commit the characterization tests**

```bash
git add backend/tests/test_stt_soniox.py backend/tests/test_ws.py
git commit -m "test: lock soniox adapter behavior"
```

---

## Task 2: Introduce provider-neutral STT types and the Soniox adapter

**Files:**
- Add: `backend/app/stt.py`
- Add: `backend/app/stt_soniox.py`
- Modify: `backend/app/transcript_accumulator.py`

This task creates the boundary that Item 8 is actually about.

- [ ] **Step 1: Write failing tests for normalized event handling if needed**

If `TranscriptAccumulator` needs a different input type, add or extend tests so
the normalized event contract is explicit.

Suggested shape:

```python
def test_accumulator_accepts_normalized_provider_events():
    ...
```

- [ ] **Step 2: Run the accumulator and adapter tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_transcript_accumulator.py tests/test_stt_soniox.py -v
```

Expected: FAIL because the new event types and adapter are not implemented

- [ ] **Step 3: Add the provider-neutral STT contract**

Create `backend/app/stt.py` with a small set of app-facing types.

Recommended shape:

```python
@dataclass(slots=True)
class SttToken:
    text: str
    is_final: bool


@dataclass(slots=True)
class SttEvent:
    tokens: list[SttToken]
    has_fin: bool = False
    has_endpoint: bool = False
    is_finished: bool = False


class SttSession(Protocol):
    async def send_audio(self, chunk: bytes) -> None: ...
    async def finalize(self) -> None: ...
    async def end_stream(self) -> None: ...
    async def close(self) -> None: ...
    def __aiter__(self) -> AsyncIterator[SttEvent]: ...
```

- [ ] **Step 4: Implement the Soniox adapter**

Create `backend/app/stt_soniox.py` with:

- Soniox websocket URL and config builder
- connection/session setup
- translation from raw Soniox messages into `SttEvent`
- explicit `finalize()` and `end_stream()` methods

Implementation guidance:

- keep the current Soniox payload fields unchanged
- keep control-marker interpretation inside the adapter, not in `ws.py`
- keep adapter naming concrete and Soniox-specific

- [ ] **Step 5: Update transcript assembly if required**

Adjust `backend/app/transcript_accumulator.py` only as much as needed so it
consumes the normalized app contract while preserving current transcript output.

- [ ] **Step 6: Run the focused tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_transcript_accumulator.py tests/test_stt_soniox.py -v
```

Expected: PASS

- [ ] **Step 7: Commit the abstraction layer**

```bash
git add backend/app/stt.py backend/app/stt_soniox.py backend/app/transcript_accumulator.py backend/tests/test_stt_soniox.py backend/tests/test_transcript_accumulator.py
git commit -m "refactor: add stt provider abstraction"
```

---

## Task 3: Wire `/ws` through a provider factory

**Files:**
- Add: `backend/app/stt_factory.py`
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_ws.py`

The websocket endpoint should orchestrate the browser session, not own Soniox
transport details.

- [ ] **Step 1: Write a failing factory test or websocket integration-style test**

Add or extend tests that prove `/ws` now interacts with the provider through the
factory/session seam rather than calling `websockets.connect` directly.

Suggested case:

```python
def test_ws_uses_configured_stt_provider_factory():
    ...
```

- [ ] **Step 2: Run the websocket tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_ws.py -v
```

Expected: FAIL because `ws.py` still opens Soniox directly

- [ ] **Step 3: Implement the factory and refactor `ws.py`**

Create `backend/app/stt_factory.py` and update `backend/app/ws.py` so:

- `start` gets a provider session from the factory
- incoming browser audio is forwarded via `send_audio()`
- `stop` calls `finalize()` and `end_stream()` on the session
- relay logic consumes normalized `SttEvent` objects
- browser messaging and extraction-loop behavior remain unchanged

- [ ] **Step 4: Run websocket tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_ws.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the websocket refactor**

```bash
git add backend/app/stt_factory.py backend/app/ws.py backend/tests/test_ws.py
git commit -m "refactor: route websocket stt through provider factory"
```

---

## Task 4: Add the explicit settings seam and run regression checks

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_config.py`

We need one explicit configuration seam for the provider abstraction, but the
current Soniox production path must remain the default.

- [ ] **Step 1: Add failing config tests**

Extend `backend/tests/test_config.py` with focused cases that prove:

1. the current Soniox + Gemini env still loads unchanged
2. provider selection defaults to `soniox`
3. optional future-provider credentials remain optional

Suggested cases:

```python
def test_settings_default_stt_provider_to_soniox():
    ...

def test_settings_default_optional_future_stt_keys_to_none():
    ...
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_config.py -v
```

Expected: FAIL because the provider-selection seam is not modeled yet

- [ ] **Step 3: Update settings minimally**

Update `backend/app/config.py` so:

- the default provider is explicitly `soniox`
- Soniox credentials stay required
- optional future-provider keys can exist without changing startup requirements

Recommended shape:

```python
class Settings(BaseSettings):
    stt_provider: str = "soniox"
    soniox_api_key: str
    gemini_api_key: str
    google_cloud_project_id: str | None = None
    mistral_api_key: str | None = None
```

- [ ] **Step 4: Run the regression test set**

Run:

```bash
cd backend && uv run pytest tests/test_config.py tests/test_ws.py tests/test_transcript_accumulator.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the settings seam**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "refactor: add explicit stt provider settings seam"
```

---

## Validation Checklist

- [ ] Soniox remains the default production provider
- [ ] `/ws` no longer owns Soniox transport details directly
- [ ] finalize-then-end behavior is locked by tests
- [ ] transcript and extraction behavior remain unchanged for the Soniox path
- [ ] future providers have one clear injection point
- [ ] backend production code stays free of eval-specific logic

---

## Recommended First Execution Order

1. Lock the current Soniox behavior with tests.
2. Add the provider-neutral STT types and Soniox adapter.
3. Refactor `/ws` through the provider factory.
4. Add the settings seam and rerun the regression suite.
