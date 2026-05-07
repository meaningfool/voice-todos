# Plan: Extract Shared Runtime Package

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [014_spec_extract-shared-runtime-package.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/014_spec_extract-shared-runtime-package.md)

**Goal:** Move the runtime-neutral live-session, transcript, todo, extraction, model, and prompt code into one real top-level `shared/` package; make both the local FastAPI adapter and the hosted Cloudflare runtime import that package directly; remove the `cloudflare/src/app/` mirror; and prove no browser-visible `/ws` regression in either runtime.

**Architecture:** Make `shared/` the single source of truth for runtime-neutral modules. Keep `backend/app/` and `cloudflare/src/` responsible only for runtime-specific transport, bootstrap, and entry concerns. Use thin compatibility wrappers inside `backend/app/` only where they avoid broad unrelated churn. Rewire [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) and [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py) to import `shared` directly. Remove `cloudflare/src/app/` completely.

**Tech Stack:** Python 3.12+, FastAPI websocket flow, Cloudflare workers-py / workers-runtime-sdk / pywrangler, pytest, pytest-asyncio, ruff, ty

---

## Scope

This plan covers exactly four deliverables:

1. Create a real `shared/` package with prompt/env path support and make it importable from both backend and Cloudflare runtimes.
2. Move the session/transcript runtime-neutral modules into `shared/` and keep local behavior intact through narrow compatibility shims where needed.
3. Move the todo/extraction/model runtime-neutral modules and prompt assets into `shared/`, update backend imports, and preserve local `/ws` behavior.
4. Rewire the hosted runtime to import `shared/` directly, remove `cloudflare/src/app/`, and run the full structural and non-regression gates.

Out of scope for this plan:

- hosted STT provider parity
- deployment/documentation work from the original `V4`
- browser websocket protocol changes
- STT transport redesign
- extraction behavior changes
- local/hosted feature expansion

---

## File Map

### Shared package - New source of truth

| File | Responsibility |
|------|----------------|
| `shared/__init__.py` | Shared package marker |
| `shared/backend_env.py` | Shared env lookup and backend `.env` path helper |
| `shared/stt.py` | Shared STT contracts |
| `shared/transcript_accumulator.py` | Shared transcript state and update semantics |
| `shared/live_session.py` | Shared session lifecycle and stop/finalization logic |
| `shared/models.py` | Shared extraction/todo data models |
| `shared/model_providers.py` | Shared extraction model-provider selection |
| `shared/extract.py` | Shared extraction implementation seam |
| `shared/extraction_loop.py` | Shared todo/extraction coordinator |
| `shared/extraction_thresholds.py` | Shared threshold constants |
| `shared/prompts/registry.py` | Shared prompt lookup |
| `shared/prompts/todo_extraction/v1.md` | Shared prompt asset |

### Backend runtime-specific surface

| File | Responsibility |
|------|----------------|
| `backend/app/__init__.py` | Local import bootstrap so `shared` resolves when running from `backend/` |
| `backend/app/ws.py` | Local `/ws` adapter; must import shared runtime modules directly |
| `backend/app/backend_env.py` | Optional compatibility shim if broader backend code still imports `app.backend_env` |
| `backend/app/stt.py` | Optional compatibility shim if broader backend code still imports `app.stt` |
| `backend/app/transcript_accumulator.py` | Optional compatibility shim |
| `backend/app/live_session.py` | Optional compatibility shim |
| `backend/app/models.py` | Optional compatibility shim |
| `backend/app/model_providers.py` | Optional compatibility shim |
| `backend/app/extract.py` | Optional compatibility shim |
| `backend/app/extraction_loop.py` | Optional compatibility shim |
| `backend/app/extraction_thresholds.py` | Optional compatibility shim |
| `backend/app/prompts/registry.py` | Optional compatibility shim |
| `backend/app/repo_env.py` | May need path-helper update if it relies on `backend_env` internals |
| `backend/pyproject.toml` | Test import path support for `shared` |

### Cloudflare runtime-specific surface

| File | Responsibility |
|------|----------------|
| `cloudflare/src/repo_bootstrap.py` | Cloudflare import bootstrap; should expose repo root instead of the backend-only mirror path |
| `cloudflare/src/session_runtime.py` | Hosted `/ws` session owner; must import shared runtime modules directly |
| `cloudflare/src/stt_factory_cf.py` | Hosted STT factory; update imports if it still reaches moved shared contracts through `app.*` |
| `cloudflare/src/settings.py` | Hosted config; keep runtime-only |
| `cloudflare/pyproject.toml` | Test import path support for `shared` |
| `cloudflare/src/app/` | Remove entirely in the final task |

### Tests and verification helpers

| File | Responsibility |
|------|----------------|
| `backend/tests/test_prompt_registry.py` | Prompt path/content regression after moving prompts |
| `backend/tests/test_shared_runtime_package.py` | New structural import/bootstrap checks for the backend side |
| `backend/tests/test_live_session.py` | Shared session regression coverage after moving implementation |
| `backend/tests/test_transcript_accumulator.py` | Shared transcript regression coverage |
| `backend/tests/test_extract.py` | Shared extraction regression coverage |
| `backend/tests/test_extraction_loop.py` | Shared todo coordinator regression coverage |
| `backend/tests/test_models.py` | Shared model regression coverage |
| `backend/tests/test_ws.py` | Local acceptance tests used by the non-regression gate |
| `cloudflare/tests/test_shared_runtime_imports.py` | New structural import checks for the hosted side |
| `cloudflare/tests/test_session_runtime.py` | Hosted acceptance tests used by the non-regression gate |
| `cloudflare/tests/test_shared_todo_imports.py` | May be updated or replaced by the broader shared-runtime import test |

---

## Acceptance Gates From Spec

## Acceptance Gate: Shared Runtime Code Lives In One Real Shared Package

**Why this gate matters:**
This is the actual refactor outcome. If the repo still depends on `backend/app/` as the physical home of shared runtime code, or still depends on the Cloudflare mirror, the slice is incomplete.

**Criteria**

- The runtime-neutral modules now live under one top-level `shared/` package.
- The local adapter and hosted adapter both import that shared runtime code from `shared/`.
- The `cloudflare/src/app/` mirror/symlink layer is removed.
- The shared package does not import local-only or Cloudflare-only runtime modules.

**Proof**

- **Filesystem proof**
  - verify `shared/` exists
  - verify the moved runtime-neutral modules exist under `shared/`
  - verify `cloudflare/src/app/` does not exist
- **Import proof**
  - inspect [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) and [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)
  - assert both import shared runtime modules from `shared/`
- **Neutrality proof**
  - inspect modules under `shared/`
  - assert they do not import FastAPI modules, Cloudflare runtime modules, or local-only recorder/bootstrap modules

**Expected evidence**

```bash
test -d shared
test ! -e cloudflare/src/app
rg -n "from shared\\.|import shared\\." backend/app/ws.py cloudflare/src/session_runtime.py
rg -n "from (fastapi|workers|js|cloudflare)|import (fastapi|workers|js|cloudflare)" shared
```

plus the resulting output, including the absence of forbidden runtime imports in `shared/`.

## Acceptance Gate: No Browser-Visible Runtime Regression Is Introduced

**Why this gate matters:**
This slice is a packaging refactor around live runtime code. If either `/ws` path changes browser-visible behavior, the refactor is not acceptable even if the package layout is cleaner.

**Criteria**

- The local `/ws` path still emits live todo updates during recording.
- The local `/ws` stop path still uses the finalized transcript for final todo handling and still sends `todos` before `stopped`.
- The hosted `/ws` path preserves the same browser-visible behavior: live todo updates, finalized-transcript stop handling, and `todos` before `stopped`.

**Proof**

- **Local preservation proof**
  Run the existing local acceptance tests:
  ```bash
  cd backend && uv run pytest \
    tests/test_ws.py::test_ws_sends_todos_during_recording \
    tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
    tests/test_ws.py::test_ws_stop_sends_todos_before_stopped -v
  ```
  These must prove:
  - live `todos` still appear during the session
  - the stop path still uses the finalized transcript
  - terminal ordering still preserves `todos` before `stopped`

- **Hosted preservation proof**
  Run the existing hosted acceptance tests:
  ```bash
  cd cloudflare && uv run pytest \
    tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
    tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
    tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped -v
  ```
  These must prove the same browser-visible properties for the hosted `/ws` path.

**Expected evidence**

- pytest output showing all six named acceptance tests pass
- brief statement of what each test covers:
  - live todo emission
  - finalized-transcript stop handling
  - `todos` before `stopped` ordering

---

## Gate Execution

### Structural proof for `Shared Runtime Code Lives In One Real Shared Package`

Run:

```bash
test -d shared
test ! -e cloudflare/src/app
rg --files shared | sort
rg -n "from shared\\.|import shared\\." backend/app/ws.py cloudflare/src/session_runtime.py
! rg -n "from (fastapi|workers|js|cloudflare)|import (fastapi|workers|js|cloudflare)" shared
! rg -n "session_recorder|repo_bootstrap|logfire_setup" shared
```

Expected:

- `shared/` exists and lists the moved modules and prompt assets
- `cloudflare/src/app` is absent
- both adapters show direct `shared` imports
- the forbidden-import checks produce no matches

Evidence to collect:

- the `rg --files shared` output
- the `shared` import lines from [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) and [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)
- the absence of forbidden runtime imports under `shared/`

### Behavioral proof for `No Browser-Visible Runtime Regression Is Introduced`

Local proof:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped -v
```

Expected: PASS

Hosted proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped -v
```

Expected: PASS

Evidence to collect:

- pytest output showing all six named tests pass
- short note mapping the tests to the three proof points:
  - live todo emission
  - finalized-transcript stop handling
  - `todos` before `stopped` ordering

---

## Supporting Verification

Shared package import and prompt verification:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py \
  tests/test_prompt_registry.py \
  tests/test_models.py \
  tests/test_transcript_accumulator.py \
  tests/test_live_session.py \
  tests/test_extract.py \
  tests/test_extraction_loop.py \
  -v
cd cloudflare && uv run pytest \
  tests/test_shared_runtime_imports.py \
  tests/test_session_runtime.py \
  -v
```

Static checks:

```bash
cd backend && uv run ruff check app tests
cd backend && uv run ty check app
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
```

Optional hosted smoke after the package move:

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
  --session-id smoke-shared-package \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1 \
  --expect-todos-min 1 \
  --expect-terminal-type stopped
```

Expected:

- import/prompt regression tests PASS
- local shared-module suites PASS
- hosted shared-import/runtime suites PASS
- `ruff` clean in backend and Cloudflare
- `ty` exits `0`; the existing Cloudflare Worker-base warnings may remain unless this slice removes them
- optional smoke prints `PASS`

---

## Task 1.1: Scaffold `shared/` and lock prompt/env path behavior

**Purpose:**
Create the real `shared/` package, move the prompt registry and prompt asset first, and make both runtimes able to import `shared` without yet moving all runtime-neutral modules.

**Files:**
- Create: `shared/__init__.py`
- Create: `shared/backend_env.py`
- Create: `shared/prompts/registry.py`
- Create: `shared/prompts/todo_extraction/v1.md`
- Create: `backend/tests/test_shared_runtime_package.py`
- Create: `cloudflare/tests/test_shared_runtime_imports.py`
- Modify: `backend/app/__init__.py`
- Modify: `backend/app/backend_env.py`
- Modify: `backend/app/prompts/registry.py`
- Modify: `backend/tests/test_prompt_registry.py`
- Modify: `backend/pyproject.toml`
- Modify: `cloudflare/pyproject.toml`
- Modify: `cloudflare/src/repo_bootstrap.py`

**Supports:**
- Acceptance Gate: `Shared Runtime Code Lives In One Real Shared Package`
- Supporting Verification: import and prompt regression checks

- [ ] **Step 1: Write the failing shared-package and prompt-path tests**

Add:

- `backend/tests/test_shared_runtime_package.py::test_backend_package_bootstrap_allows_importing_shared_prompt_registry`
- `cloudflare/tests/test_shared_runtime_imports.py::test_cloudflare_bootstrap_allows_importing_shared_prompt_registry`

Update `backend/tests/test_prompt_registry.py::test_get_prompt_ref_returns_expected_metadata` so the expected path points at `shared/prompts/todo_extraction/v1.md`.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py \
  tests/test_prompt_registry.py::test_get_prompt_ref_returns_expected_metadata \
  -v
cd cloudflare && uv run pytest \
  tests/test_shared_runtime_imports.py \
  -v
```

Expected: FAIL because `shared/` and the new import/bootstrap paths do not exist yet

- [ ] **Step 3: Implement the minimal shared package scaffold**

Create:

- `shared/__init__.py`
- `shared/backend_env.py`
- `shared/prompts/registry.py`
- `shared/prompts/todo_extraction/v1.md`

Update:

- `backend/app/__init__.py` to insert the repo root into `sys.path` before backend modules import `shared`
- `cloudflare/src/repo_bootstrap.py` to insert the repo root as the canonical shared import root
- `backend/app/backend_env.py` and `backend/app/prompts/registry.py` to become thin compatibility re-exports
- `backend/pyproject.toml` and `cloudflare/pyproject.toml` test import paths so direct `shared` imports work in pytest

- [ ] **Step 4: Run the focused scaffold tests**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py \
  tests/test_prompt_registry.py \
  -v
cd cloudflare && uv run pytest \
  tests/test_shared_runtime_imports.py \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared backend/app/__init__.py backend/app/backend_env.py backend/app/prompts/registry.py backend/tests/test_shared_runtime_package.py backend/tests/test_prompt_registry.py backend/pyproject.toml cloudflare/pyproject.toml cloudflare/src/repo_bootstrap.py cloudflare/tests/test_shared_runtime_imports.py
git commit -m "refactor: scaffold shared runtime package"
```

---

## Task 1.2: Move session and transcript core into `shared/`

**Purpose:**
Make the session/transcript source of truth live under `shared/` while preserving backend behavior through minimal compatibility shims.

**Files:**
- Create: `shared/stt.py`
- Create: `shared/transcript_accumulator.py`
- Create: `shared/live_session.py`
- Modify: `backend/app/stt.py`
- Modify: `backend/app/transcript_accumulator.py`
- Modify: `backend/app/live_session.py`
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_shared_runtime_package.py`

**Supports:**
- Acceptance Gate: `Shared Runtime Code Lives In One Real Shared Package`
- Supporting Verification: `test_stt`, `test_transcript_accumulator`, `test_live_session`

- [ ] **Step 1: Write the failing shared session/transcript import tests**

Add to `backend/tests/test_shared_runtime_package.py`:

- `test_shared_session_modules_import_from_top_level_shared_package`

It should import `shared.stt`, `shared.transcript_accumulator`, and `shared.live_session` directly and assert the expected public symbols are present.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py::test_shared_session_modules_import_from_top_level_shared_package \
  -v
```

Expected: FAIL because the session/transcript modules have not been moved yet

- [ ] **Step 3: Move the session/transcript source of truth**

Move the implementations into:

- `shared/stt.py`
- `shared/transcript_accumulator.py`
- `shared/live_session.py`

Convert the `backend/app/...` copies into thin compatibility re-exports.

Update [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) to import the shared controller/contracts directly instead of importing them back through `app.*`.

- [ ] **Step 4: Run the focused shared-core suites**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py \
  tests/test_stt.py \
  tests/test_transcript_accumulator.py \
  tests/test_live_session.py \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/stt.py shared/transcript_accumulator.py shared/live_session.py backend/app/stt.py backend/app/transcript_accumulator.py backend/app/live_session.py backend/app/ws.py backend/tests/test_shared_runtime_package.py
git commit -m "refactor: move session core into shared package"
```

---

## Task 1.3: Move extraction, todo, model, and prompt consumers into `shared/`

**Purpose:**
Finish the shared source-of-truth move for todo/extraction/model code and prove the local runtime still behaves the same through `/ws`.

**Files:**
- Create: `shared/models.py`
- Create: `shared/model_providers.py`
- Create: `shared/extract.py`
- Create: `shared/extraction_loop.py`
- Create: `shared/extraction_thresholds.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/model_providers.py`
- Modify: `backend/app/extract.py`
- Modify: `backend/app/extraction_loop.py`
- Modify: `backend/app/extraction_thresholds.py`
- Modify: `backend/app/ws.py`
- Modify: `backend/tests/test_shared_runtime_package.py`

**Supports:**
- Acceptance Gate: `Shared Runtime Code Lives In One Real Shared Package`
- Acceptance Gate: `No Browser-Visible Runtime Regression Is Introduced`
- Supporting Verification: extract/extraction_loop/models/prompt/local-acceptance checks

- [ ] **Step 1: Write the failing shared extraction-stack import tests**

Add to `backend/tests/test_shared_runtime_package.py`:

- `test_shared_extraction_modules_import_from_top_level_shared_package`

It should import `shared.models`, `shared.model_providers`, `shared.extract`, `shared.extraction_loop`, and `shared.extraction_thresholds` directly.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py::test_shared_extraction_modules_import_from_top_level_shared_package \
  -v
```

Expected: FAIL because the extraction/todo/model modules have not been moved yet

- [ ] **Step 3: Move the extraction/todo/model source of truth**

Move the implementations into the `shared/` package and convert the corresponding `backend/app/...` modules into compatibility re-exports. Update [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) to import shared todo/extraction modules directly.

- [ ] **Step 4: Run the local shared-stack and acceptance checks**

Run:

```bash
cd backend && uv run pytest \
  tests/test_shared_runtime_package.py \
  tests/test_prompt_registry.py \
  tests/test_models.py \
  tests/test_extract.py \
  tests/test_extraction_loop.py \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/models.py shared/model_providers.py shared/extract.py shared/extraction_loop.py shared/extraction_thresholds.py backend/app/models.py backend/app/model_providers.py backend/app/extract.py backend/app/extraction_loop.py backend/app/extraction_thresholds.py backend/app/ws.py backend/tests/test_shared_runtime_package.py
git commit -m "refactor: move extraction stack into shared package"
```

---

## Task 1.4: Rewire the hosted runtime to `shared/`, remove the mirror, and run the gates

**Purpose:**
Finish the symmetric import boundary: hosted code imports `shared/` directly, `cloudflare/src/app/` is removed, and both structural and browser-visible non-regression gates pass.

**Files:**
- Modify: `cloudflare/src/session_runtime.py`
- Modify: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/src/repo_bootstrap.py`
- Modify: `cloudflare/tests/test_shared_runtime_imports.py`
- Modify: `cloudflare/tests/test_shared_todo_imports.py` or delete if superseded
- Delete: `cloudflare/src/app/`

**Supports:**
- Acceptance Gate: `Shared Runtime Code Lives In One Real Shared Package`
- Acceptance Gate: `No Browser-Visible Runtime Regression Is Introduced`
- Supporting Verification: hosted shared-import/runtime checks

- [ ] **Step 1: Write the failing hosted direct-import test**

Update `cloudflare/tests/test_shared_runtime_imports.py` so it imports the hosted runtime through `shared` directly and asserts `session_runtime` no longer depends on the `app` mirror path.

- [ ] **Step 2: Run the targeted hosted import tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_shared_runtime_imports.py \
  -v
```

Expected: FAIL because hosted code still imports the mirror under `cloudflare/src/app`

- [ ] **Step 3: Rewire hosted imports and remove `cloudflare/src/app/`**

Update [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py) and any remaining hosted runtime modules to import from `shared/` directly, then delete `cloudflare/src/app/`.

- [ ] **Step 4: Run both acceptance gates**

Run the structural proof:

```bash
test -d shared
test ! -e cloudflare/src/app
rg --files shared | sort
rg -n "from shared\\.|import shared\\." backend/app/ws.py cloudflare/src/session_runtime.py
! rg -n "from (fastapi|workers|js|cloudflare)|import (fastapi|workers|js|cloudflare)" shared
! rg -n "session_recorder|repo_bootstrap|logfire_setup" shared
```

Run the non-regression proof:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_sends_todos_during_recording \
  tests/test_ws.py::test_ws_stop_uses_finalized_transcript_for_final_pass \
  tests/test_ws.py::test_ws_stop_sends_todos_before_stopped -v
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_session_sends_todos_during_recording \
  tests/test_session_runtime.py::test_hosted_session_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_session_stop_sends_todos_before_stopped -v
```

Expected: all commands succeed; both acceptance gates PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/session_runtime.py cloudflare/src/stt_factory_cf.py cloudflare/src/repo_bootstrap.py cloudflare/tests/test_shared_runtime_imports.py
git rm -r cloudflare/src/app
git commit -m "refactor: remove cloudflare shared mirror"
```

---

## Checkpoint

Do not begin [015_plan_hosted-stt-provider-parity.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/015_plan_hosted-stt-provider-parity.md) until both `V4a` acceptance gates pass and their expected evidence has been collected.

---

REQUIRED HANDOFF: `superpowers:executing-plans`

OPTIONAL HANDOFF: `superpowers:subagent-driven-development`
