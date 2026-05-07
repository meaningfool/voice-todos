# Spec: Extract Shared Runtime Package

## Source

- Follow-on work identified after `V3`
- Refines the shaping path by splitting packaging symmetry out from later deploy/docs work and from hosted provider parity
- Scope here is only the shared-package extraction

## Baseline

After `V3`, the repo has working local and hosted paths, but the shared runtime code still physically lives under `backend/app/`. The hosted app reaches that code through the symlink mirror in [cloudflare/src/app](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/app), which currently points back into `backend/app/`.

That means the architecture is only logically symmetric:

- local adapter: [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py)
- hosted adapter: [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)
- but the shared code still "belongs" to the local app in filesystem terms

The runtime-neutral surface currently includes:

- session/transcript core:
  - `live_session.py`
  - `transcript_accumulator.py`
  - `stt.py`
- todo/extraction core:
  - `extract.py`
  - `extraction_loop.py`
  - `extraction_thresholds.py`
  - `models.py`
  - `model_providers.py`
  - `prompts/`
- shared env helper:
  - `backend_env.py`

## Target System

After this slice, the runtime-neutral code lives in one real top-level `shared/` package. Both apps import from it directly.

Target shape:

```text
shared/
  __init__.py
  backend_env.py
  extract.py
  extraction_loop.py
  extraction_thresholds.py
  live_session.py
  model_providers.py
  models.py
  prompts/
  stt.py
  transcript_accumulator.py

backend/
  app/
    ws.py
    main.py
    session_recorder.py
    stt_factory.py
    stt_soniox.py
    stt_mistral.py
    ...

cloudflare/
  src/
    entry.py
    session_runtime.py
    settings.py
    stt_factory_cf.py
    stt_soniox_cf.py
    ...
```

The `cloudflare/src/app/` symlink mirror is removed. The local and hosted apps become true peers around one shared package.

## Structural Delta

Before this slice:

- shared runtime behavior is implemented in `backend/app/`
- hosted reuses it through `cloudflare/src/app/` symlinks

After this slice:

- shared runtime behavior is implemented in `shared/`
- both adapters import the same package directly
- browser-visible behavior is intended to stay unchanged

## Decisions

- Extract only runtime-neutral modules into `shared/`
- Keep runtime-specific transport, boot, and entry code in `backend/app/` and `cloudflare/src/`
- Remove the `cloudflare/src/app/` mirror entirely rather than maintaining two shared-code entrypoints
- Treat non-regression of browser-visible `/ws` behavior as a blocking acceptance outcome, not just supporting verification

## Non-Goals

- No hosted STT provider parity in this slice
- No deploy/documentation work from the original `V4`
- No browser protocol changes
- No STT transport rewrite
- No extraction behavior change
- No local/hosted feature expansion

## Design And Implementation Constraints

- `shared/` must stay runtime-neutral:
  - no FastAPI imports
  - no Cloudflare Worker/Durable Object imports
  - no local-only recorder/bootstrap imports
- Prompt resolution must still work after moving `prompts/`
- Local app must still run without Cloudflare tooling installed
- Hosted app must still run without depending on a mirror back into `backend/app/`
- Existing accepted `/ws` message ordering and stop behavior must remain intact in both runtimes

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

## Supporting Verification

- focused import tests for moved shared modules
- prompt-resolution test after moving `prompts/`
- lint/type checks on `shared/`, `backend/app/`, and `cloudflare/src/`
- optional hosted runtime smoke after the package move:
  ```bash
  cd cloudflare && uv run python scripts/ws_smoke.py \
    --mode todo-stop \
    --url http://127.0.0.1:8788/ws \
    --fixture-path ../backend/tests/fixtures/while-speaking-two-todos/audio.pcm \
    --expect-todos-min 1
  ```
