# Plan: Free-Tier Cloudflare Worker Bundle

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [033_spec_free-tier-cloudflare-worker-bundle.md](033_spec_free-tier-cloudflare-worker-bundle.md)

**Goal:** Make the accepted Cloudflare public app deployable on the free Worker plan again by slimming the production runtime bundle down to the Soniox + Gemini path that the public app actually needs, while preserving the accepted same-origin UI and deterministic Soniox smoke.

**Architecture:** Treat the first public production bundle as a deliberately minimal Cloudflare runtime contract. Keep `cloudflare/` as the deployment boundary and preserve the existing same-origin UI + `/ws` shape from `031` and the scripted deploy entrypoint from `032`. Remove optional runtime dependency families from the shipped Worker bundle, narrow the production secret/config contract to the Soniox public path, and make hosted Mistral an explicit deferred capability rather than a silently half-supported production path. The Worker should ship only the runtime code required for the accepted Soniox public flow, while deferred hosted Mistral code may remain in-repo only if it is no longer part of the routed public production contract.

**Tech Stack:** Python 3.12+, Cloudflare Workers Python runtime, `pywrangler`, bash, React 19 + Vite 8, `agent-browser`

---

## Scope

This plan covers exactly five deliverables:

1. Pin the free-tier public bundle contract around the accepted Soniox + Gemini production path.
2. Remove optional runtime dependency families from the shipped Worker bundle, specifically the Cloudflare-side `logfire` and hosted Mistral runtime package surface.
3. Narrow the production secret/config contract so the public deploy path no longer requires Mistral secrets that the accepted first public bundle does not use.
4. Make hosted Mistral an explicit deferred capability at runtime, in tests, and in operator docs rather than leaving it as an implied production path.
5. Re-run the accepted local and public Soniox smoke proofs through the same scripted deploy path from `032` and verify that the previous Cloudflare `10027` size failure is gone.

Out of scope for this plan:

- no paid Cloudflare plan upgrade
- no browser protocol change
- no redesign of backend extraction
- no restoration of the broader `014` shared extraction/runtime package
- no new staging environment or CI deployment flow
- no Cloudflare-side Logfire parity work
- no new live Mistral public acceptance surface

This plan assumes the `032` deploy entrypoint already exists and that the intended public hostname remains `voice-todos.meaningfool.net` unless the operator explicitly changes it before execution.

---

## Implementation Start Prerequisites

Before any real Cloudflare publish attempt for this slice, the implementing
agent must explicitly confirm the current operator-owned prerequisites:

1. Public hostname
   - default expected value for this workspace: `voice-todos.meaningfool.net`
   - if the target hostname changed, stop and update the execution inputs first
2. Cloudflare authentication
   - confirm `cd cloudflare && uv run pywrangler whoami` succeeds
   - if not authenticated, stop and walk the operator through login again
3. Zone readiness
   - confirm the target zone is still managed in the intended Cloudflare account
4. Required secret source for the accepted first public bundle
   - `backend/.env` must contain:
     - `SONIOX_API_KEY`
     - `GEMINI_API_KEY`
   - `MISTRAL_API_KEY` is no longer a blocking input for this slice once the
     contract is narrowed
5. Free-plan target remains intentional
   - do not resolve the deployment blocker by silently switching to a paid plan
   - this slice exists to make the existing free-plan account work

Do not start the real publish proof until those prerequisites are confirmed.
This coordination step is not a TDD task.

---

## File Map

### Production bundle contract

| File | Responsibility |
|------|----------------|
| `cloudflare/pyproject.toml` | Defines the shipped Worker runtime dependency contract; should stop shipping optional runtime families that are not required for the Soniox public path |
| `cloudflare/src/app/extraction_loop.py` | Current Cloudflare extraction loop imports `logfire`; should become runtime-self-sufficient without a shipped Logfire package |
| `cloudflare/src/settings.py` | Current hosted runtime settings surface; should match the narrowed public secret/config contract instead of implying extra production provider inputs |
| `cloudflare/wrangler.jsonc` | Committed Cloudflare secret contract for the public app; should narrow to the secrets actually required by the accepted first public bundle |
| `cloudflare/scripts/deploy_public_app.py` | Scripted public deploy entrypoint; should only upload the secrets required by the accepted first public bundle |
| `cloudflare/tests/test_public_deploy_contract.py` | Static contract tests for the committed production bundle and Wrangler secret surface |
| `cloudflare/tests/test_deploy_public_app.py` | Focused tests for the deploy script secret filtering and runtime-var contract |
| `cloudflare/tests/test_settings.py` | Pins the hosted settings contract after the public bundle is narrowed |

### Deferred hosted Mistral boundary

| File | Responsibility |
|------|----------------|
| `cloudflare/src/stt_factory_cf.py` | Hosted provider routing seam; should reject hosted Mistral explicitly for the free-tier public bundle instead of routing it as an implied production capability |
| `cloudflare/tests/test_stt_factory_cf.py` | Pins explicit hosted-provider routing and rejection behavior for the public bundle |
| `cloudflare/tests/test_session_runtime.py` | Keeps the hosted runtime acceptance surface current; should stop implying hosted Mistral is part of the accepted public production path |
| `cloudflare/src/stt_mistral_cf.py` | May remain as deferred in-repo code only if it is no longer part of the routed public production contract |
| `cloudflare/tests/test_stt_mistral_cf.py` | Optional focused verification for deferred adapter code if that source remains in-repo after the contract narrowing |
| `docs/references/2026-05-07-mistral-live-validation-findings.md` | Existing findings note that should remain linked as context for the deferred capability rather than being promoted back into the public acceptance surface |

### Operator runbook and smoke surface

| File | Responsibility |
|------|----------------|
| `cloudflare/README.md` | Operator runbook; must state the narrowed first-public-bundle contract and the deferred Mistral posture explicitly |
| `scripts/browser_ui_smoke.sh` | Repo-owned deterministic browser smoke used for both local and public Soniox proof |
| `backend/tests/fixtures/while-speaking-two-todos/result.json` | Accepted transcript/todo contract consumed by the browser smoke |

### Existing surfaces reused rather than redesigned

| File | Why it matters |
|------|----------------|
| `cloudflare/scripts/sync_frontend_dist.sh` | Keeps the accepted frontend asset handoff from `032` instead of inventing a second copy path |
| `cloudflare/tests/test_assets_config.py` | Preserves the same-origin Cloudflare app boundary from `031` while this slice changes only the bundle contract |
| `032_plan_scripted-public-cloudflare-deploy-path.md` | Defines the scripted deploy path that must remain the operator entrypoint after the bundle slimming lands |

---

## Acceptance Gates From Spec

## Acceptance Gate: Production Bundle Contract Is Explicit And Free-Plan Compatible

**Why this gate matters:**
This slice is incomplete if free-plan deployability depends on accidental
packaging behavior or undocumented exclusions. The production runtime contract
must be explicit and must actually fit the target account.

**Criteria**

- The Cloudflare production runtime dependency contract is explicit for the
  accepted first public Soniox path.
- Optional hosted runtime families that are not required for that path are
  either removed from the production bundle or explicitly moved out of the
  blocking production contract.
- A real publish attempt on the target free-plan account no longer fails with
  Cloudflare error `10027`.

**Proof**

- **Contract proof**
  - inspect the Cloudflare runtime dependency/config surface and show which
    dependencies are part of the accepted first public production bundle
  - show which optional hosted families were removed, deferred, or otherwise
    excluded from the blocking production contract
- **Free-plan publish proof**
  - run the real scripted deploy command or the narrowest equivalent publish
    path against the same free-plan account that previously failed
  - verify that Cloudflare accepts the Worker upload and that the previous
    `10027` size error does not occur

**Expected evidence**

- code/doc references for the accepted production dependency contract
- exact publish command and outcome used to prove the previous `10027` failure
  is gone
- explicit note describing how hosted Mistral and Cloudflare-side Logfire were
  handled for the first public bundle

## Acceptance Gate: Accepted Public Soniox Path Still Works After Bundle Slimming

**Why this gate matters:**
A smaller bundle is not acceptable if it breaks the actual public app path that
the deployment item exists to ship.

**Criteria**

- The same-origin Cloudflare app still serves the real UI and `/ws`.
- The deterministic Soniox fixture flow still passes against the Cloudflare app
  boundary without visible browser errors.
- The scripted public deploy path from `032` remains usable for the accepted
  first public Soniox flow once the bundle fits.

**Proof**

- **Behavior proof**
  - run the required deterministic Cloudflare browser smoke against the accepted
    Soniox fixture scenario
  - verify transcript activity, todo activity, and clean terminal behavior
- **Deployed-path proof**
  - after the bundle has been slimmed enough to publish, open the real deployed
    app URL
  - run the accepted deterministic public smoke path from `032`
  - verify the deployed same-origin app completes the accepted Soniox flow
    without visible UI errors

**Expected evidence**

- exact local Cloudflare browser smoke command and result
- exact deploy command and resulting public publish outcome
- final public URL used for verification
- exact public deterministic smoke path or invocation and its result
- observed browser-visible outcomes from the deployed run

## Supporting Verification

- focused lint/type checks for touched Cloudflare files
- narrow config/dependency tests where practical
- focused runtime tests for any touched provider-selection or bootstrap code

---

## Gate Execution

### Contract proof for `Production Bundle Contract Is Explicit And Free-Plan Compatible`

Run the focused contract and provider-boundary tests:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_deploy_public_app.py \
  tests/test_stt_factory_cf.py \
  tests/test_session_runtime.py::test_hosted_session_start_surfaces_unsupported_provider_error \
  -v
```

Expected:

- all named tests PASS
- the committed contract proves the accepted first public bundle requires only
  the Soniox and Gemini secrets
- the production bundle no longer ships `logfire` or `mistralai` as runtime
  Worker dependencies
- hosted Mistral is rejected explicitly for the free-tier public bundle instead
  of failing later through an implicit dependency hole

Inspect the production dependency contract directly:

```bash
cd cloudflare && sed -n '1,80p' pyproject.toml
cd cloudflare && sed -n '1,120p' wrangler.jsonc
```

Expected:

- `[project.dependencies]` contains only the packages intentionally shipped in
  the public Worker bundle
- `wrangler.jsonc` required secrets match the narrowed production contract

Run the real publish proof against the same free-plan account and hostname that
previously failed:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain voice-todos.meaningfool.net
```

Expected:

- Cloudflare accepts the Worker upload
- the command does not fail with error `10027`
- the printed deploy result identifies the real public hostname

Evidence to collect:

- exact publish command and result
- code references to `cloudflare/pyproject.toml`,
  `cloudflare/wrangler.jsonc`, and
  `cloudflare/scripts/deploy_public_app.py`
- brief note stating whether hosted Mistral was:
  - rejected in the public runtime while source remains deferred in-repo, or
  - removed more aggressively
- brief note stating how `logfire` was removed from the public runtime bundle

### Behavior proof for `Accepted Public Soniox Path Still Works After Bundle Slimming`

Run the required local same-origin Cloudflare smoke first.

Terminal A:

```bash
cd frontend
pnpm build
cd ../cloudflare
./scripts/sync_frontend_dist.sh
set -a && source ../backend/.env && set +a
uv run pywrangler dev --port 8788
```

Terminal B, from repo root:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Expected:

- the smoke exits `0`
- the final transcript matches
  `backend/tests/fixtures/while-speaking-two-todos/result.json`
- the final todo list matches the same fixture result
- no visible warning card is present

Run the required deployed-path smoke after the real publish succeeds:

```bash
./scripts/browser_ui_smoke.sh \
  "https://voice-todos.meaningfool.net" \
  while-speaking-two-todos
```

Expected:

- the smoke exits `0`
- the deployed app reaches the accepted final transcript
- the deployed app reaches the accepted final todo list
- no visible warning card is present

If diagnosis is needed during either proof, use:

```bash
cd cloudflare && uv run pywrangler tail voice-todos-cloudflare --format pretty
```

Evidence to collect:

- exact local smoke command/result
- exact deploy command/result
- final public URL
- exact public smoke command/result
- observed browser-visible transcript/todo outcomes
- relevant Cloudflare tail output only if a failure required diagnosis

---

## Supporting Verification

Run focused runtime and config regressions after the implementation tasks land:

```bash
cd cloudflare && uv run pytest \
  tests/test_settings.py \
  tests/test_assets_config.py \
  tests/test_ws_smoke.py \
  tests/test_session_runtime.py \
  tests/test_stt_mistral_cf.py \
  -v
```

Run static checks for touched Cloudflare surfaces:

```bash
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
bash -n scripts/browser_ui_smoke.sh
```

Expected:

- focused pytest regressions PASS
- `ruff check` is clean for touched files
- `ty check` exits `0`
- the browser smoke script remains shell-valid

---

## Task 1.1: Pin the Soniox-only public bundle contract and slim the shipped runtime

**Purpose:**
Make the free-tier public bundle contract fail loudly in tests before changing
the shipped Worker surface. This task pins the exact secrets and runtime
dependency contract that the accepted first public bundle is allowed to ship.

**Files:**
- Modify: `cloudflare/tests/test_public_deploy_contract.py`
- Modify: `cloudflare/tests/test_deploy_public_app.py`
- Modify: `cloudflare/pyproject.toml`
- Modify: `cloudflare/src/app/extraction_loop.py`
- Modify: `cloudflare/src/settings.py`
- Modify: `cloudflare/wrangler.jsonc`
- Modify: `cloudflare/scripts/deploy_public_app.py`
- Modify: `cloudflare/tests/test_settings.py`

**Supports:**
- Acceptance Gate: `Production Bundle Contract Is Explicit And Free-Plan Compatible`
- Supporting Verification: focused contract/deploy-script tests

- [ ] **Step 1: Write the failing public-bundle contract tests**

Add assertions that prove:

- `wrangler.jsonc` required secrets are exactly:
  - `SONIOX_API_KEY`
  - `GEMINI_API_KEY`
- `cloudflare/pyproject.toml` runtime Worker dependencies no longer include:
  - `logfire`
  - `mistralai`
- the deploy script uploads only the narrowed required secrets for the accepted
  first public bundle

- [ ] **Step 2: Run the focused contract tests to confirm the current contract fails**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_deploy_public_app.py \
  -v
```

Expected: FAIL because the current public contract still requires
`MISTRAL_API_KEY` and still ships `logfire` and `mistralai` in the runtime
Worker dependency surface.

- [ ] **Step 3: Implement the minimal production bundle slimming**

Make the smallest coherent code changes:

- remove `logfire` from the shipped Worker dependency surface in
  `cloudflare/pyproject.toml`
- remove `mistralai` from the shipped Worker dependency surface in
  `cloudflare/pyproject.toml`
- if deferred hosted Mistral source remains in-repo, move `mistralai` to a
  non-shipped dependency surface rather than leaving it in `[project.dependencies]`
- replace the Cloudflare extraction-loop `logfire` dependency with a no-op
  runtime-safe span helper or equivalent zero-dependency behavior
- align `cloudflare/src/settings.py` with the narrowed public secret/config
  contract so the hosted runtime surface no longer implies extra production
  provider inputs
- narrow `wrangler.jsonc` required secrets to the accepted Soniox public path
- narrow `deploy_public_app.py` secret filtering to the same contract

- [ ] **Step 4: Run the focused contract tests again**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_deploy_public_app.py \
  -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  cloudflare/tests/test_public_deploy_contract.py \
  cloudflare/tests/test_deploy_public_app.py \
  cloudflare/pyproject.toml \
  cloudflare/src/app/extraction_loop.py \
  cloudflare/src/settings.py \
  cloudflare/wrangler.jsonc \
  cloudflare/scripts/deploy_public_app.py \
  cloudflare/tests/test_settings.py
git commit -m "Slim free-tier public worker bundle contract"
```

---

## Task 1.2: Make hosted Mistral an explicit deferred capability in runtime, tests, and docs

**Purpose:**
The public bundle contract is still ambiguous if hosted Mistral remains a
routed production provider in code, tests, or docs. This task makes the
deferred status explicit and keeps the accepted hosted test surface current.

**Files:**
- Modify: `cloudflare/src/stt_factory_cf.py`
- Modify: `cloudflare/tests/test_stt_factory_cf.py`
- Modify: `cloudflare/tests/test_session_runtime.py`
- Modify: `cloudflare/README.md`
- Optional Modify: `cloudflare/src/stt_mistral_cf.py`
- Optional Modify: `cloudflare/tests/test_stt_mistral_cf.py`

**Supports:**
- Acceptance Gate: `Production Bundle Contract Is Explicit And Free-Plan Compatible`
- Acceptance Gate: `Accepted Public Soniox Path Still Works After Bundle Slimming`
- Supporting Verification: focused hosted runtime/provider tests

- [ ] **Step 1: Write the failing provider-boundary tests**

Add or replace tests that prove:

- `stt_provider="mistral"` is rejected explicitly for the free-tier public
  bundle
- the hosted runtime surfaces a clear startup error instead of a hidden import
  or missing-dependency failure
- hosted session-runtime tests no longer imply Mistral is part of the accepted
  public production path

- [ ] **Step 2: Run the focused provider tests to confirm the current behavior fails**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py \
  tests/test_session_runtime.py::test_hosted_session_start_surfaces_unsupported_provider_error \
  -v
```

Expected: FAIL because the current factory still routes Mistral and the hosted
runtime test surface still implies a Mistral production path.

- [ ] **Step 3: Implement the explicit deferred-provider boundary**

Make the smallest coherent changes:

- change `cloudflare/src/stt_factory_cf.py` so hosted Mistral is rejected with
  a clear free-tier-public-bundle message
- prune or rewrite the hosted Mistral runtime tests in
  `cloudflare/tests/test_session_runtime.py` so the accepted hosted runtime
  surface matches the Soniox-only public contract
- update `cloudflare/README.md` so the required secrets, deploy expectations,
  and deferred Mistral posture match the code
- if `cloudflare/src/stt_mistral_cf.py` remains in-repo, keep it clearly out of
  the routed public production path and retain only the focused adapter tests
  that still make sense for deferred source

- [ ] **Step 4: Run the focused provider/runtime tests again**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_stt_factory_cf.py \
  tests/test_session_runtime.py \
  tests/test_stt_mistral_cf.py \
  -v
```

Expected:

- `test_stt_factory_cf.py` PASS
- the hosted session-runtime suite PASS with a current acceptance surface that
  no longer claims a public Mistral runtime path
- `test_stt_mistral_cf.py` either PASS as deferred adapter coverage or is
  intentionally removed in the same task

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src cloudflare/tests cloudflare/README.md
git commit -m "Defer hosted mistral from free-tier public bundle"
```

---

## Checkpoint After Slice 1

Do not claim completion for `033` until both acceptance gates pass:

- `Production Bundle Contract Is Explicit And Free-Plan Compatible`
- `Accepted Public Soniox Path Still Works After Bundle Slimming`

If the real publish still fails with Cloudflare error `10027`, or if either the
local or public deterministic Soniox smoke fails, the slice is incomplete even
if all focused tests pass.
