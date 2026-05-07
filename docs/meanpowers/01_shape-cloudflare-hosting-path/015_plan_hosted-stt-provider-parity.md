# Plan: Hosted STT Provider Parity

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [015_spec_hosted-stt-provider-parity.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/015_spec_hosted-stt-provider-parity.md)

**Goal:** Make Soniox and Mistral follow the same shared-provider boundary, then extend the hosted Cloudflare runtime so `stt_provider` supports both `soniox` and `mistral` without leaking provider-specific transcript semantics into the hosted session runtime.

**Architecture:** This plan assumes [014_plan_extract-shared-runtime-package.md](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/docs/meanpowers/01_shape-cloudflare-hosting-path/014_plan_extract-shared-runtime-package.md) has landed or an equivalent `shared/` package already exists. Move provider normalization, capabilities, and provider-specific session semantics into shared runtime-neutral modules. Keep runtime-specific connection mechanics in local and hosted adapter files. Keep provider selection in the factory layer only. Add a hosted Mistral transport adapter and extend the hosted factory without changing the shared session controller or browser protocol.

**Tech Stack:** Python 3.12+, FastAPI websocket flow, Cloudflare workers-py / workers-runtime-sdk / pywrangler, `mistralai`, Soniox, pytest, pytest-asyncio, ruff, ty

---

## Scope

This plan covers exactly five deliverables:

1. Extract shared Soniox provider semantics into a runtime-neutral module and rewire local and hosted Soniox adapters to use it.
2. Extract shared Mistral provider semantics into a runtime-neutral module and add the hosted Mistral adapter module on top of those shared semantics without wiring hosted provider selection yet.
3. Run the slice-1 structural and semantic non-regression gate for shared provider normalization.
4. Extend the hosted factory and settings surface to support `stt_provider="mistral"` with the expected missing-key failure behavior.
5. Wire the existing hosted Mistral adapter into the hosted runtime, add hosted Mistral session acceptance coverage, and run the slice-2 hosted parity gate.

Out of scope for this plan:

- browser websocket protocol changes
- todo extraction redesign
- shared session controller redesign
- hosted LLM-provider parity
- deployment/documentation work

---

## File Map

### Shared provider-semantics layer

| File | Responsibility |
|------|----------------|
| `shared/stt.py` | Existing shared STT contracts; may gain small provider-facing helper protocols if needed |
| `shared/stt_soniox_shared.py` | Shared Soniox capabilities, config payload builder, event translation, and any transport-neutral Soniox session helpers |
| `shared/stt_mistral_shared.py` | Shared Mistral capabilities, event translation, final transcript semantics, and any transport-neutral Mistral session helpers |

### Local adapters

| File | Responsibility |
|------|----------------|
| `backend/app/stt_factory.py` | Local provider dispatch; keep it free of provider translation logic |
| `backend/app/stt_soniox.py` | Local Soniox connection mechanics only, backed by shared Soniox semantics |
| `backend/app/stt_mistral.py` | Local Mistral connection mechanics only, backed by shared Mistral semantics |

### Hosted adapters

| File | Responsibility |
|------|----------------|
| `cloudflare/src/stt_factory_cf.py` | Hosted provider dispatch for `soniox` and `mistral` |
| `cloudflare/src/stt_soniox_cf.py` | Hosted Soniox connection mechanics only, backed by shared Soniox semantics |
| `cloudflare/src/stt_mistral_cf.py` | New hosted Mistral connection adapter |
| `cloudflare/src/session_runtime.py` | Hosted session owner; must stay provider-agnostic |
| `cloudflare/src/settings.py` | Hosted runtime settings; already carries `mistral_api_key`, may need narrow updates |
| `cloudflare/wrangler.jsonc` | Add `MISTRAL_API_KEY` to required secrets |

### Tests and verification

| File | Responsibility |
|------|----------------|
| `backend/tests/test_stt_soniox.py` | Soniox semantic regression coverage |
| `backend/tests/test_stt_mistral.py` | Mistral semantic regression coverage |
| `backend/tests/test_stt_factory.py` | Local provider-routing regression coverage |
| `backend/tests/test_ws.py` | Local `/ws` Mistral acceptance/reference surface |
| `cloudflare/tests/test_stt_soniox_cf.py` | Hosted Soniox adapter regression coverage |
| `cloudflare/tests/test_stt_factory_cf.py` | New hosted provider-routing coverage |
| `cloudflare/tests/test_stt_mistral_cf.py` | New hosted Mistral adapter coverage |
| `cloudflare/tests/test_session_runtime.py` | Hosted Mistral acceptance coverage above the provider seam |
| `cloudflare/scripts/ws_smoke.py` | Optional hosted runtime smoke for Mistral after parity lands |

---

## Acceptance Gates From Spec

## Acceptance Gate: Provider Normalization Semantics Are Shared Without Regression

**Why this gate matters:**
This is the refactor slice that makes the provider architecture coherent. If provider semantics remain duplicated or drift during the extraction, hosted parity work will be built on an inconsistent seam.

**Criteria**

- Soniox and Mistral normalization/capability logic lives in shared runtime-neutral modules.
- Local and hosted adapters for the same provider depend on the same shared normalization logic.
- Extracting shared provider normalization does not change the accepted provider transcript/finalization semantics.

**Proof**

- **Structural proof**
  - inspect the provider modules and show:
    - shared Soniox normalization exists
    - shared Mistral normalization exists
    - local and hosted Soniox adapters import shared Soniox logic
    - local and hosted Mistral adapters import shared Mistral logic
- **Semantic non-regression proof**
  - run existing local Mistral tests that define accepted translation/session semantics:
    ```bash
    cd backend && uv run pytest \
      tests/test_stt_mistral.py \
      tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
      tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
      tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key -v
    ```
  - run focused local Soniox/provider regression tests or add them if missing, to prove Soniox shared extraction did not change accepted semantics
  - run focused hosted Soniox adapter tests to prove the hosted path now depends on shared Soniox normalization without changing behavior

**Expected evidence**

- code references showing both runtimes import shared normalization modules for each provider
- pytest output for the named provider semantic/regression tests
- explicit note if a small new Soniox semantic-regression test had to be added because the current suite did not pin a required behavior

## Acceptance Gate: Hosted Runtime Supports Both STT Providers

**Why this gate matters:**
This is the actual hosted parity outcome. If the Cloudflare runtime still only supports Soniox, the slice has not delivered the requested capability.

**Criteria**

- Hosted provider selection accepts both `soniox` and `mistral`.
- When hosted `stt_provider="mistral"`, the hosted `/ws` path preserves the accepted browser-visible session behavior above the provider seam.
- Hosted Mistral startup rejects missing `MISTRAL_API_KEY` with the expected hosted failure behavior.
- Hosted session/controller/runtime layers remain provider-agnostic; provider choice stays behind the hosted factory and adapter seam.

**Proof**

- **Hosted factory proof**
  - run hosted factory tests proving:
    - `mistral` dispatches to the hosted Mistral connector
    - missing `MISTRAL_API_KEY` is rejected
- **Hosted Mistral session proof**
  - run focused hosted acceptance tests for Mistral that cover:
    - transcript streaming
    - finalized-transcript stop handling
    - terminal ordering
  - these should mirror the accepted local Mistral session behavior already covered in:
    - [backend/tests/test_ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/tests/test_ws.py)
- **Structural seam proof**
  - inspect [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py) to show it does not branch on provider-specific transcript semantics

**Expected evidence**

- named hosted factory test output
- named hosted Mistral acceptance test output
- code references showing factory dispatch and provider-agnostic hosted session runtime

---

## Gate Execution

### Structural and semantic proof for `Provider Normalization Semantics Are Shared Without Regression`

Structural proof:

```bash
test -f shared/stt_soniox_shared.py
test -f shared/stt_mistral_shared.py
rg -n "from shared\\.stt_soniox_shared|import shared\\.stt_soniox_shared" backend/app/stt_soniox.py cloudflare/src/stt_soniox_cf.py
rg -n "from shared\\.stt_mistral_shared|import shared\\.stt_mistral_shared" backend/app/stt_mistral.py cloudflare/src/stt_mistral_cf.py
! rg -n "from (fastapi|workers|js|cloudflare)|import (fastapi|workers|js|cloudflare)" shared/stt_soniox_shared.py shared/stt_mistral_shared.py
```

Expected: all structural commands succeed and the forbidden-import check yields no matches

Semantic non-regression proof:

```bash
cd backend && uv run pytest \
  tests/test_stt_soniox.py \
  tests/test_stt_mistral.py \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
  tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
cd cloudflare && uv run pytest \
  tests/test_stt_soniox_cf.py \
  -v
```

Expected: PASS

Evidence to collect:

- code references showing shared Soniox and shared Mistral imports in local and hosted adapters
- pytest output for the named Soniox/Mistral semantic tests
- explicit note if a new Soniox semantic test was added to pin an uncovered behavior

### Behavioral and seam proof for `Hosted Runtime Supports Both STT Providers`

Hosted factory proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py::test_create_stt_session_routes_mistral_provider_to_hosted_connector \
  tests/test_stt_factory_cf.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
```

Expected: PASS

Hosted Mistral session proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_mistral_session_streams_and_stops_with_final_done_text \
  tests/test_session_runtime.py::test_hosted_mistral_transcript_state_acceptance \
  tests/test_session_runtime.py::test_hosted_mistral_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_mistral_stop_sends_todos_before_stopped \
  -v
```

Expected: PASS

Structural seam proof:

```bash
! rg -n "\"mistral\"|\"soniox\"|stt_provider" cloudflare/src/session_runtime.py
```

Expected: no matches, proving provider names do not leak into the hosted session runtime

Evidence to collect:

- pytest output for the hosted factory tests
- pytest output for the hosted Mistral acceptance tests
- the absence of provider-name branching in [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)

---

## Supporting Verification

Hosted adapter verification:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_soniox_cf.py \
  tests/test_stt_mistral_cf.py \
  tests/test_stt_factory_cf.py \
  tests/test_session_runtime.py \
  -v
```

Focused local Mistral `/ws` regression checks if provider refactors touch behavior above the adapter seam:

```bash
cd backend && uv run pytest \
  tests/test_ws.py::test_ws_mistral_configured_session_streams_and_stops_with_final_done_text \
  tests/test_ws.py::test_mistral_transcript_state_acceptance \
  tests/test_ws.py::test_ws_stop_uses_session_final_transcript_text_for_extraction_and_payload \
  -v
```

Static checks:

```bash
cd backend && uv run ruff check app tests
cd backend && uv run ty check app
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
```

Optional hosted Mistral smoke after parity lands:

In terminal A:

```bash
cd cloudflare && SONIOX_API_KEY="${SONIOX_API_KEY:-unused}" MISTRAL_API_KEY="$MISTRAL_API_KEY" STT_PROVIDER=mistral GEMINI_API_KEY="${GEMINI_API_KEY:-unused}" uv run pywrangler dev --port 8788
```

In terminal B:

```bash
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --fixture-path ../backend/tests/fixtures/stop-the-button/audio.pcm \
  --mode transcript-stop \
  --session-id smoke-hosted-mistral \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1
```

Expected:

- hosted adapter suites PASS
- local Mistral `/ws` regressions PASS if run
- `ruff` clean in both apps
- `ty` exits `0`; the existing Cloudflare Worker-base warnings may remain unless this slice removes them
- optional smoke prints `PASS`

---

## Task 1.1: Extract shared Soniox semantics and rewire both Soniox adapters

**Purpose:**
Make Soniox follow the same provider boundary the spec requires: shared semantics, runtime-specific transport.

**Files:**
- Create: `shared/stt_soniox_shared.py`
- Modify: `backend/app/stt_soniox.py`
- Modify: `cloudflare/src/stt_soniox_cf.py`
- Modify: `backend/tests/test_stt_soniox.py`
- Modify: `cloudflare/tests/test_stt_soniox_cf.py`

**Supports:**
- Acceptance Gate: `Provider Normalization Semantics Are Shared Without Regression`

- [ ] **Step 1: Write the failing shared Soniox semantic tests**

Add tests that import the shared module directly, for example:

- `backend/tests/test_stt_soniox.py::test_build_soniox_config_matches_current_production_defaults`
- `backend/tests/test_stt_soniox.py::test_translate_soniox_event_sets_fin_and_endpoint_flags`

Update them to import from `shared.stt_soniox_shared` instead of `app.stt_soniox`.

- [ ] **Step 2: Run the targeted Soniox tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_stt_soniox.py \
  -v
```

Expected: FAIL because `shared.stt_soniox_shared` does not exist yet

- [ ] **Step 3: Implement the shared Soniox semantic module**

Move into `shared/stt_soniox_shared.py`:

- Soniox capabilities
- config payload builder
- raw-event translation into `SttEvent`
- any transport-neutral Soniox session helper that cleanly removes duplicated provider semantics from local and hosted adapters

Update the local and hosted Soniox adapters so they keep only connection mechanics and import shared Soniox logic.

- [ ] **Step 4: Run the Soniox semantic and hosted Soniox adapter tests**

Run:

```bash
cd backend && uv run pytest tests/test_stt_soniox.py -v
cd cloudflare && uv run pytest tests/test_stt_soniox_cf.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/stt_soniox_shared.py backend/app/stt_soniox.py cloudflare/src/stt_soniox_cf.py backend/tests/test_stt_soniox.py cloudflare/tests/test_stt_soniox_cf.py
git commit -m "refactor: share soniox provider semantics"
```

---

## Task 1.2: Extract shared Mistral semantics and create the unwired hosted Mistral adapter

**Purpose:**
Move Mistral capabilities, translation, and final transcript semantics into shared code, and create the hosted Mistral adapter module on top of those shared semantics before hosted provider selection is enabled.

**Files:**
- Create: `shared/stt_mistral_shared.py`
- Create: `cloudflare/src/stt_mistral_cf.py`
- Create: `cloudflare/tests/test_stt_mistral_cf.py`
- Modify: `backend/app/stt_mistral.py`
- Modify: `backend/tests/test_stt_mistral.py`
- Modify: `backend/tests/test_stt_factory.py`

**Supports:**
- Acceptance Gate: `Provider Normalization Semantics Are Shared Without Regression`

- [ ] **Step 1: Write the failing shared Mistral semantic tests**

Update `backend/tests/test_stt_mistral.py` so it imports the translation/session semantics from `shared.stt_mistral_shared`.

Add hosted adapter tests in `cloudflare/tests/test_stt_mistral_cf.py` that import the future hosted adapter and assert it delegates transcript/final transcript semantics to the shared Mistral helper.

Keep the existing acceptance-shaped coverage:

- additive final token deltas
- `transcription.done` finishing semantics
- `final_transcript_text` handling
- raw-event callback behavior

- [ ] **Step 2: Run the targeted Mistral tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_stt_mistral.py \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
  tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
cd cloudflare && uv run pytest \
  tests/test_stt_mistral_cf.py \
  -v
```

Expected: FAIL because `shared.stt_mistral_shared` and `cloudflare/src/stt_mistral_cf.py` do not exist yet

- [ ] **Step 3: Implement the shared Mistral semantic module**

Move into `shared/stt_mistral_shared.py`:

- Mistral capabilities
- raw-event normalization into `SttEvent`
- final transcript completion semantics
- any transport-neutral session helper that local and hosted Mistral adapters can both use

Update `backend/app/stt_mistral.py` to keep only connection mechanics plus construction of the shared Mistral session helper.

Create `cloudflare/src/stt_mistral_cf.py` so it uses only Cloudflare-specific connection/client mechanics and returns the shared Mistral session helper, but do not wire it into `stt_factory_cf.py` yet.

- [ ] **Step 4: Run the Mistral semantic and factory tests**

Run:

```bash
cd backend && uv run pytest \
  tests/test_stt_mistral.py \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
  tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
cd cloudflare && uv run pytest \
  tests/test_stt_mistral_cf.py \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/stt_mistral_shared.py cloudflare/src/stt_mistral_cf.py cloudflare/tests/test_stt_mistral_cf.py backend/app/stt_mistral.py backend/tests/test_stt_mistral.py backend/tests/test_stt_factory.py
git commit -m "refactor: share mistral provider semantics"
```

---

## Task 1.3: Finish the shared-provider boundary and run the slice-1 gate

**Purpose:**
Prove the refactor is complete: both providers now use shared semantics across local and hosted runtimes, with no semantic regression.

**Files:**
- Modify: `backend/app/stt_factory.py` if any provider-semantics residue remains
- Modify: `cloudflare/src/stt_soniox_cf.py`
- Create or modify any narrow structural import test if needed

**Supports:**
- Acceptance Gate: `Provider Normalization Semantics Are Shared Without Regression`

- [ ] **Step 1: Add or update any missing structural import test**

If the codebase does not yet pin the shared-provider imports structurally, add a small test or inspection helper that makes the shared Soniox/shared Mistral import boundary explicit.

- [ ] **Step 2: Run the full slice-1 gate**

Run the structural proof:

```bash
test -f shared/stt_soniox_shared.py
test -f shared/stt_mistral_shared.py
rg -n "from shared\\.stt_soniox_shared|import shared\\.stt_soniox_shared" backend/app/stt_soniox.py cloudflare/src/stt_soniox_cf.py
rg -n "from shared\\.stt_mistral_shared|import shared\\.stt_mistral_shared" backend/app/stt_mistral.py cloudflare/src/stt_mistral_cf.py
! rg -n "from (fastapi|workers|js|cloudflare)|import (fastapi|workers|js|cloudflare)" shared/stt_soniox_shared.py shared/stt_mistral_shared.py
```

Run the semantic proof:

```bash
cd backend && uv run pytest \
  tests/test_stt_soniox.py \
  tests/test_stt_mistral.py \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
  tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
  tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
cd cloudflare && uv run pytest \
  tests/test_stt_soniox_cf.py \
  -v
```

Expected: slice-1 gate PASS

- [ ] **Step 3: Commit**

```bash
git add shared backend/app cloudflare/src cloudflare/tests
git commit -m "refactor: unify provider normalization boundary"
```

---

## Checkpoint After Slice 1

Do not begin the hosted Mistral parity tasks until `Provider Normalization Semantics Are Shared Without Regression` passes and its expected evidence has been collected.

---

## Task 2.1: Extend the hosted factory for Mistral selection and missing-key failure

**Purpose:**
Add the hosted provider-selection seam for Mistral now that the hosted adapter module exists.

**Files:**
- Create: `cloudflare/tests/test_stt_factory_cf.py`
- Modify: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/wrangler.jsonc`

**Supports:**
- Acceptance Gate: `Hosted Runtime Supports Both STT Providers`

- [ ] **Step 1: Write the failing hosted factory tests**

Add:

- `test_create_stt_session_routes_mistral_provider_to_hosted_connector`
- `test_create_stt_session_rejects_mistral_without_api_key`

Model them after the local `backend/tests/test_stt_factory.py` Mistral routing tests.

- [ ] **Step 2: Run the targeted factory tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py::test_create_stt_session_routes_mistral_provider_to_hosted_connector \
  tests/test_stt_factory_cf.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
```

Expected: FAIL because the hosted factory still rejects any provider other than `soniox`

- [ ] **Step 3: Implement the hosted Mistral factory branch**

Update `cloudflare/src/stt_factory_cf.py` to:

- accept `stt_provider="mistral"`
- require `settings.mistral_api_key`
- dispatch to a hosted `connect_mistral` adapter function
- keep recorder/provider-message routing at the factory edge if the hosted Mistral adapter supports it

Update `cloudflare/wrangler.jsonc` so `MISTRAL_API_KEY` is a required secret.

- [ ] **Step 4: Run the hosted factory tests**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py::test_create_stt_session_routes_mistral_provider_to_hosted_connector \
  tests/test_stt_factory_cf.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/stt_factory_cf.py cloudflare/wrangler.jsonc cloudflare/tests/test_stt_factory_cf.py
git commit -m "feat: add hosted mistral provider selection"
```

---

## Task 2.2: Wire the hosted Mistral adapter into the hosted provider path

**Purpose:**
Enable the already-created hosted Mistral adapter inside the hosted provider path and keep `session_runtime.py` provider-agnostic.

**Files:**
- Modify: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/src/stt_mistral_cf.py`
- Modify: `cloudflare/tests/test_stt_mistral_cf.py`

**Supports:**
- Acceptance Gate: `Hosted Runtime Supports Both STT Providers`
- Supporting Verification: hosted Mistral adapter suite

- [ ] **Step 1: Write the failing hosted Mistral wiring tests**

Add tests that cover:

- hosted factory dispatch reaching the existing hosted Mistral adapter
- the hosted adapter receiving the expected Cloudflare/runtime-specific connection factory inputs
- no provider-specific semantics being reimplemented inside `stt_factory_cf.py`

- [ ] **Step 2: Run the targeted hosted Mistral adapter tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py \
  tests/test_stt_mistral_cf.py \
  -v
```

Expected: FAIL because the hosted Mistral adapter is not wired into the hosted provider path yet

- [ ] **Step 3: Wire the hosted Mistral adapter into the hosted provider path**

Finish `cloudflare/src/stt_factory_cf.py` and any narrow hosted adapter seam needed so:

- the hosted factory dispatches `mistral` to the existing `stt_mistral_cf.py`
- the hosted adapter continues to use only shared Mistral semantics
- provider-specific semantics do not leak back into the factory layer

- [ ] **Step 4: Run the hosted Mistral adapter suite**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py \
  tests/test_stt_mistral_cf.py \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/stt_factory_cf.py cloudflare/src/stt_mistral_cf.py cloudflare/tests/test_stt_factory_cf.py cloudflare/tests/test_stt_mistral_cf.py
git commit -m "feat: wire hosted mistral transport"
```

---

## Task 2.3: Add hosted Mistral session acceptance coverage and run the slice-2 gate

**Purpose:**
Prove the hosted `/ws` path now supports both STT providers while keeping `session_runtime.py` provider-agnostic.

**Files:**
- Modify: `cloudflare/tests/test_session_runtime.py`
- Modify: `cloudflare/src/session_runtime.py` only if any provider leakage or small seam issue is exposed

**Supports:**
- Acceptance Gate: `Hosted Runtime Supports Both STT Providers`

- [ ] **Step 1: Write the failing hosted Mistral acceptance tests**

Add:

- `test_hosted_mistral_session_streams_and_stops_with_final_done_text`
- `test_hosted_mistral_transcript_state_acceptance`
- `test_hosted_mistral_stop_uses_finalized_transcript_for_final_pass`
- `test_hosted_mistral_stop_sends_todos_before_stopped`

Model them after the accepted local Mistral `/ws` tests in [backend/tests/test_ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/tests/test_ws.py), but run them against the hosted `HostedSessionActor` / hosted runtime seam.

- [ ] **Step 2: Run the targeted hosted Mistral acceptance tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_mistral_session_streams_and_stops_with_final_done_text \
  tests/test_session_runtime.py::test_hosted_mistral_transcript_state_acceptance \
  tests/test_session_runtime.py::test_hosted_mistral_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_mistral_stop_sends_todos_before_stopped \
  -v
```

Expected: FAIL because the hosted Mistral provider path is not wired end-to-end yet

- [ ] **Step 3: Wire hosted Mistral through the existing hosted runtime seam**

Finish the hosted provider path so:

- `stt_factory_cf.py` dispatches Mistral to the new hosted adapter
- `session_runtime.py` does not branch on provider semantics
- the shared controller and hosted runtime continue to handle transcript/todo/stop flows exactly as they do for Soniox

- [ ] **Step 4: Run the full slice-2 gate**

Run the hosted factory proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py::test_create_stt_session_routes_mistral_provider_to_hosted_connector \
  tests/test_stt_factory_cf.py::test_create_stt_session_rejects_mistral_without_api_key \
  -v
```

Run the hosted Mistral acceptance proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_session_runtime.py::test_hosted_mistral_session_streams_and_stops_with_final_done_text \
  tests/test_session_runtime.py::test_hosted_mistral_transcript_state_acceptance \
  tests/test_session_runtime.py::test_hosted_mistral_stop_uses_finalized_transcript_for_final_pass \
  tests/test_session_runtime.py::test_hosted_mistral_stop_sends_todos_before_stopped \
  -v
```

Run the structural seam proof:

```bash
! rg -n "\"mistral\"|\"soniox\"|stt_provider" cloudflare/src/session_runtime.py
```

Expected: slice-2 gate PASS

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/stt_factory_cf.py cloudflare/src/stt_mistral_cf.py cloudflare/src/session_runtime.py cloudflare/tests/test_stt_factory_cf.py cloudflare/tests/test_stt_mistral_cf.py cloudflare/tests/test_session_runtime.py cloudflare/wrangler.jsonc
git commit -m "feat: add hosted mistral stt parity"
```

---

## Checkpoint

Do not call this work complete until both acceptance gates pass and the expected evidence for each gate has been collected.

---

REQUIRED HANDOFF: `superpowers:executing-plans`

OPTIONAL HANDOFF: `superpowers:subagent-driven-development`
