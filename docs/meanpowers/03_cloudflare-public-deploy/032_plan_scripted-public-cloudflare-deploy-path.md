# Plan: Scripted Public Cloudflare Deploy Path

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [032_spec_scripted-public-cloudflare-deploy-path.md](032_spec_scripted-public-cloudflare-deploy-path.md)

**Goal:** Add one accepted public deployment path for the Cloudflare-hosted app so an operator can prove the local same-origin Cloudflare smoke, run one scripted deploy command from `cloudflare/`, publish directly to the final public subdomain, and treat the deployment as complete only after the real public app passes the deterministic fixture smoke.

**Architecture:** Keep `frontend/` as the UI source of truth and `cloudflare/` as the deployment boundary. Add one deploy entrypoint in `cloudflare/scripts/deploy_public_app.py` that builds the frontend, reuses `cloudflare/scripts/sync_frontend_dist.sh`, uploads only the required Cloudflare secrets from the shared `backend/.env` source, and deploys with `uv run pywrangler deploy --domain <final-public-subdomain>`. Keep the public runtime config contract explicit by committing only base Worker config in `cloudflare/wrangler.jsonc`, passing `STT_PROVIDER=soniox` and optional non-secret runtime overrides through the deploy script, and using the repo-owned `scripts/browser_ui_smoke.sh` as both the local pre-publish prerequisite and the public post-deploy completion gate.

**Tech Stack:** Python 3.12+, `pywrangler`, Wrangler deploy-time secrets, bash, React 19 + Vite 8, `agent-browser`

---

## Scope

This plan covers exactly seven deliverables:

1. Make the operator-owned prerequisites explicit before implementation starts: final public hostname, Cloudflare auth path, Cloudflare-zone readiness, secrets presence, and optional runtime overrides.
2. Unify the stop-timeout runtime policy across backend and hosted Cloudflare so the public deploy contract does not freeze historical config drift.
3. Make the Cloudflare base config explicit for public custom-domain deployment by keeping only true secrets in `secrets.required` and disabling `workers.dev`.
4. Add one scripted deploy command in `cloudflare/` that owns frontend build, asset sync, required-secret upload, and Cloudflare publish.
5. Make the deploy-time non-secret contract explicit: fixed `STT_PROVIDER=soniox`, optional `SESSION_CAP_MS`, and optional `STOP_TIMEOUT_SECONDS`.
6. Tighten the repo-owned browser smoke so it can serve as the required public completion proof instead of only a loose sanity check.
7. Add one operator-facing runbook that defines the required local smoke, public smoke, Cloudflare-log diagnosis, lightweight recovery flow, and the non-blocking Mistral follow-up note.

Out of scope for this plan:

- no staging environment
- no CI auto-deploy
- no Cloudflare-side Logfire parity work
- no operator-gated hardening of the deterministic public smoke path
- no public-runtime architecture change away from the existing Worker + Durable Object `/ws` shape
- no Mistral provider-behavior debugging beyond linking the existing findings note

This plan assumes `031` has already landed and that both `031` acceptance gates have passed before `032` implementation begins.

---

## Implementation Start Prerequisites

Before any code edits that depend on deploy wiring or any real Cloudflare
publish attempt, the implementing agent must explicitly walk the operator
through the following inputs and blockers:

1. Final public hostname
   - example: `voice-todos.example.com`
   - this repo does not currently pin the real production hostname anywhere
2. Cloudflare authentication path
   - either interactive login such as `cd cloudflare && uv run pywrangler login`
   - or a pre-existing `CLOUDFLARE_API_TOKEN` flow the operator wants to use
3. Zone readiness
   - the target hostname must live on a zone already managed in Cloudflare
   - if the personal-site zone is not in Cloudflare, custom-domain deploy is blocked
4. Provider secrets source
   - `backend/.env` must contain:
     - `SONIOX_API_KEY`
     - `GEMINI_API_KEY`
     - `MISTRAL_API_KEY`
5. Optional runtime override decision
   - whether to leave `SESSION_CAP_MS` and `STOP_TIMEOUT_SECONDS` unset and use runtime defaults
   - or provide explicit deploy-time override values
6. Direct-to-production confirmation
   - this slice uses one public environment and no staging

Do not start deploy-dependent implementation or any real publish attempt until
these inputs are explicitly gathered from the operator. This prerequisite
collection is coordination work, not a TDD step.

---

## File Map

### Deploy contract and publish surface

| File | Responsibility |
|------|----------------|
| `cloudflare/wrangler.jsonc` | Base Worker contract for the public app: same-origin assets, true required secrets only, and `workers_dev: false` so deploys are aligned to the final public domain rather than a `workers.dev` fallback |
| `cloudflare/scripts/deploy_public_app.py` | One human-triggered deploy entrypoint that builds the frontend, syncs `cloudflare/public/`, filters the required secrets from `backend/.env`, and invokes `pywrangler deploy` with the final public domain plus explicit non-secret runtime vars |
| `cloudflare/tests/test_public_deploy_contract.py` | Static contract tests for the committed Wrangler config and the secrets/non-secret split |
| `cloudflare/tests/test_deploy_public_app.py` | Focused unit tests for deploy-script argument building, secret filtering, and optional runtime-var handling |
| `cloudflare/README.md` | Operator runbook for pre-publish smoke, publish, public smoke, diagnosis, recovery, and the linked Mistral follow-up note |

### Runtime policy unification surface

| File | Responsibility |
|------|----------------|
| `backend/app/config.py` | Canonical backend runtime settings surface; should expose the same stop-timeout semantic and canonical env name as the hosted runtime |
| `backend/app/ws.py` | Local stop/finalization path that must consume the unified timeout field |
| `backend/app/stt_smoke.py` | Local smoke helper that should build settings with the unified timeout field |
| `backend/tests/test_config.py` | Pins the canonical env name and default for backend runtime policy |
| `backend/tests/test_ws.py` | Preserves local stop-path behavior while the settings field is renamed/unified |
| `cloudflare/src/settings.py` | Hosted runtime settings surface; should keep `STOP_TIMEOUT_SECONDS` as the canonical public name and align its default with backend |
| `cloudflare/tests/test_settings.py` | Pins the hosted default and `STOP_TIMEOUT_SECONDS` loading behavior |

### Public smoke and evidence surface

| File | Responsibility |
|------|----------------|
| `scripts/browser_ui_smoke.sh` | Repo-owned `agent-browser` smoke used for both local pre-publish proof and public post-deploy completion proof |
| `backend/tests/fixtures/while-speaking-two-todos/result.json` | Expected transcript/todo contract that the smoke script should read for exact public assertions instead of hard-coding text inline |

### Existing surfaces reused rather than redesigned

| File | Why it matters |
|------|----------------|
| `cloudflare/scripts/sync_frontend_dist.sh` | Keeps the accepted `frontend/dist/` -> `cloudflare/public/` handoff instead of inventing a second asset-copy path |
| `frontend/package.json` | Owns the accepted frontend build entrypoint that the deploy script must run |
| `cloudflare/tests/test_assets_config.py` | Keeps the `031` same-origin asset boundary pinned while `032` layers deployment behavior on top |
| `docs/references/2026-05-07-mistral-live-validation-findings.md` | Remains the explicit linked note for the known Mistral live-validation gap that is non-blocking for this slice |

---

## Acceptance Gates From Spec

## Acceptance Gate: Deploy Contract And Publish Path Are Explicit And Repeatable

**Why this gate matters:**
This slice is incomplete if deployment still depends on tribal knowledge,
mixed-up config semantics, or multiple ad hoc publish steps. The repo must
leave behind one clear and repeatable deployment contract.

**Criteria**

- The repo exposes one documented/scripted deploy command for the whole app.
- The deploy command builds the frontend, syncs assets into `cloudflare/`, and
  publishes the Workers app.
- The Cloudflare runtime contract clearly separates required secrets from
  required or optional non-secret runtime config.
- The deployment workflow defines local pre-publish smoke, public post-deploy
  smoke, diagnosis via Cloudflare logs, and recovery via redeploy of the
  previous known-good commit.

**Proof**

- **Deploy-path proof**
  - inspect the deploy script/command entrypoint and show that it owns:
    - frontend build
    - asset handoff into `cloudflare/`
    - Cloudflare publish
- **Config-contract proof**
  - inspect the deployment docs/config and show the explicit contract:
    - required secrets: `SONIOX_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`
    - required non-secret config: `STT_PROVIDER=soniox`
    - optional non-secret config: `SESSION_CAP_MS`, `STOP_TIMEOUT_SECONDS`
  - show that non-secret runtime config is no longer treated as if it were a
    required secret-only value
- **Operational-proof contract**
  - inspect the deployment documentation/procedure and show:
    - local Cloudflare smoke is a required prerequisite
    - public post-deploy smoke is a required completion step
    - diagnosis uses Cloudflare logs
    - recovery is redeploy of the previous known-good commit

**Expected evidence**

- code/doc references for the single deploy command and asset-sync path
- code/doc references for the final secret/config contract
- brief note confirming how the previous `SESSION_CAP_MS` misclassification was
  resolved
- code/doc references for diagnosis and recovery procedure

## Acceptance Gate: Public Deployment Reaches Link-Ready Operational State

**Why this gate matters:**
The slice exists to make the app actually deployable, not just theoretically
documented. If the scripted path cannot publish the app to the final subdomain
and the real public app does not pass its required smoke, the deployment shape
has not landed.

**Criteria**

- After the local Cloudflare smoke passes, the scripted deploy path can publish
  the app to the final public subdomain.
- The public subdomain serves the real app UI and same-origin `/ws`.
- The public deterministic post-deploy smoke can complete the accepted fixture
  session without visible app errors.
- The deployment is only treated as complete after that public smoke passes.

**Proof**

- **Prerequisite proof**
  - run the required local Cloudflare smoke from `V1` and report the result
- **Publish proof**
  - run the deploy command against the configured final public subdomain
- **Public smoke proof**
  - open the real public app URL in a browser
  - invoke the public deterministic smoke path using the accepted
    `while-speaking-two-todos` fixture scenario or equivalent deterministic
    smoke mechanism carried forward from `V1`
  - stop the session through normal UI interaction
  - verify the app shows transcript/todo activity and reaches a clean final
    state without visible errors

**Expected evidence**

- exact local smoke command/result used as prerequisite
- exact deploy command used for publish
- final public URL used for verification
- the exact deterministic public smoke path or invocation used
- observed browser-visible outcomes from the public run
- if diagnosis was needed, the relevant Cloudflare log reference or excerpt

## Supporting Verification

- run focused lint/type checks for touched deploy/config/doc surfaces
- run focused Cloudflare tests for touched routing or config code
- add or update a narrow check around deploy-config validation if practical
- keep Mistral follow-up documentation linked, but do not expand this slice into
  provider-behavior debugging

---

## Gate Execution

### Contract proof for `Deploy Contract And Publish Path Are Explicit And Repeatable`

Run the focused contract and deploy-script tests:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_deploy_public_app.py \
  -v
```

Expected:

- both test files PASS
- the committed Wrangler config proves only the three provider keys remain in
  `secrets.required`
- the deploy-script tests prove the publish entrypoint owns frontend build,
  asset sync, required-secret upload, `STT_PROVIDER=soniox`, and optional
  `SESSION_CAP_MS` / `STOP_TIMEOUT_SECONDS` propagation

Run the deploy entrypoint in dry-run mode with a sample domain:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain voice-todos.example.com \
  --dry-run
```

Expected:

- the script runs the frontend build
- the script refreshes `cloudflare/public/` via
  `cloudflare/scripts/sync_frontend_dist.sh`
- the script prints the `pywrangler deploy` command it would execute, including:
  - `--domain voice-todos.example.com`
  - `--var STT_PROVIDER=soniox`
  - optional `--var` entries only when those optional flags are supplied
  - a generated secrets file that contains only `SONIOX_API_KEY`,
    `GEMINI_API_KEY`, and `MISTRAL_API_KEY`
- the script does not attempt a real Cloudflare publish in `--dry-run` mode

Inspect the operator runbook for the required procedural contract:

```bash
rg -n \
  "pre-publish smoke|post-deploy smoke|pywrangler tail|known-good commit|Mistral" \
  cloudflare/README.md
```

Expected:

- the runbook explicitly marks the local Cloudflare smoke as required before
  publish
- the runbook explicitly marks the public deterministic smoke as required before
  completion
- the runbook names `pywrangler tail` for diagnosis
- the runbook names redeploying a previous known-good commit for recovery
- the runbook links the existing Mistral findings note as non-blocking context

### Behavioral proof for `Public Deployment Reaches Link-Ready Operational State`

Record the final public domain for this deploy:

```bash
export PUBLIC_APP_DOMAIN="voice-todos.example.com"
```

Expected:

- `PUBLIC_APP_DOMAIN` is the real final subdomain, not a temporary
  `workers.dev` hostname

Run the required local Cloudflare smoke from `031` first.

In terminal A:

```bash
cd frontend && pnpm build
cd ../cloudflare && ./scripts/sync_frontend_dist.sh
set -a && source ../backend/.env && set +a
uv run pywrangler dev --port 8788
```

In terminal B:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Expected:

- the local smoke exits `0`
- it proves the same-origin Cloudflare-served UI and `/ws` path still pass
  before any public publish begins

Run the single public deploy command:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN"
```

Expected:

- the command builds the frontend
- the command syncs the built assets into `cloudflare/public/`
- the command uploads only the required provider secrets to Cloudflare
- the command publishes the Worker to the configured final custom domain
- the command exits `0` and prints the domain it just deployed

Run the required public deterministic smoke against the real app:

```bash
./scripts/browser_ui_smoke.sh "https://$PUBLIC_APP_DOMAIN" while-speaking-two-todos
```

Expected:

- the script exits `0`
- it opens the real public app in a browser through `agent-browser`
- it proves transcript activity, todo activity, normal stop behavior, and the
  expected final transcript/todo contract from the fixture
- the deployment is not treated as complete unless this step passes

Optional raw `agent-browser` equivalent for manual evidence capture or debugging:

```bash
agent-browser --session 032-public open "https://$PUBLIC_APP_DOMAIN/?fixture=while-speaking-two-todos"
agent-browser --session 032-public wait --load networkidle
agent-browser --session 032-public snapshot -i
```

Expected:

- the public app shell loads directly from the final domain
- the browser-visible state matches the successful scripted smoke result

If diagnosis is needed during or after the public smoke, use Cloudflare logs:

```bash
cd cloudflare && uv run pywrangler tail voice-todos-cloudflare --format pretty
```

Expected:

- tail output can be used to capture the relevant deploy-time or request-time
  failure evidence without introducing Cloudflare-side Logfire work into this
  slice

---

## Checkpoint

Do not start follow-up CI deploy work, staged-environment work, or public smoke
hardening until both `032` acceptance gates pass:

1. `Deploy Contract And Publish Path Are Explicit And Repeatable`
2. `Public Deployment Reaches Link-Ready Operational State`

Supporting verification does not replace either gate.

---

## Task 1.1: Collect operator-owned deploy prerequisites

**Purpose:**
Make the user interactions and external-account dependencies explicit before any
deploy-dependent implementation starts.

**Files:**
- Read: `backend/.env`
- Read: `cloudflare/wrangler.jsonc`
- No repository edits required for this task

**Supports:**
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Acceptance Gate: `Public Deployment Reaches Link-Ready Operational State`

- [ ] **Step 1: Ask the operator for the required deploy inputs**

Explicitly request:

- the final public hostname
- the chosen Cloudflare auth path:
  - `uv run pywrangler login`
  - or an existing `CLOUDFLARE_API_TOKEN`
- confirmation that the target zone is already on Cloudflare
- confirmation that `backend/.env` contains the three required provider secrets
- whether `SESSION_CAP_MS` or `STOP_TIMEOUT_SECONDS` should be overridden
- confirmation that direct-to-production is acceptable

Expected:

- every operator-owned input is answered before deploy-dependent code work proceeds

- [ ] **Step 2: Verify the local prerequisites that can be checked immediately**

Run:

```bash
test -e backend/.env && echo "backend env present" || echo "backend env missing"
cd cloudflare && uv run pywrangler whoami
```

Expected:

- `backend env present`
- `pywrangler whoami` succeeds after the operator completes login or provides a working token

- [ ] **Step 3: Record the chosen runtime inputs for the implementation session**

Once the operator answers, set or note the active values that later tasks will use, for example:

```bash
export PUBLIC_APP_DOMAIN="voice-todos.example.com"
# Optional only if the operator asked for overrides:
export SESSION_CAP_MS="65000"
export STOP_TIMEOUT_SECONDS="12"
```

Expected:

- later tasks do not have to guess the hostname, auth path, or runtime override intent

- [ ] **Step 4: Checkpoint**

Expected:

- do not continue to deploy-dependent code changes or any real publish attempt until all required operator inputs are present

- [ ] **Step 5: Commit**

No commit for this coordination-only task.

## Task 1.2: Unify stop-timeout runtime policy across backend and hosted Cloudflare

**Purpose:**
Remove the historical drift where backend uses `SONIOX_STOP_TIMEOUT_SECONDS`
with a `30.0` default while Cloudflare uses `STOP_TIMEOUT_SECONDS` with a
`10.0` default, so the first public deploy lands on one explicit runtime
policy instead of two competing ones.

**Files:**
- Create: `cloudflare/tests/test_settings.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/ws.py`
- Modify: `backend/app/stt_smoke.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_ws.py`
- Modify: `cloudflare/src/settings.py`

**Supports:**
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Acceptance Gate: `Public Deployment Reaches Link-Ready Operational State`
- Supporting Verification: focused backend/hosted config tests

- [ ] **Step 1: Write the failing config tests**

Add focused tests that pin the unified contract, such as:

```python
def test_backend_settings_defaults_stop_timeout_seconds_to_30(monkeypatch, tmp_path):
    ...
    assert s.stop_timeout_seconds == 30.0

def test_backend_settings_accepts_stop_timeout_seconds_env(monkeypatch, tmp_path):
    ...
    monkeypatch.setenv("STOP_TIMEOUT_SECONDS", "12.5")
    assert s.stop_timeout_seconds == 12.5

def test_cloudflare_settings_default_stop_timeout_seconds_is_30() -> None:
    assert get_settings(SimpleNamespace()).stop_timeout_seconds == 30.0
```

Also add one backward-compatibility test proving backend still accepts
`SONIOX_STOP_TIMEOUT_SECONDS` temporarily if `STOP_TIMEOUT_SECONDS` is absent.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_config.py -v
cd cloudflare && uv run pytest tests/test_settings.py -v
```

Expected:

- backend tests FAIL because the canonical field/env name is still Soniox-specific
- hosted tests FAIL because the hosted default is still `10.0`

- [ ] **Step 3: Write the minimal implementation**

Update the runtime settings so that:

- backend exposes `stop_timeout_seconds: float = 30.0`
- backend reads `STOP_TIMEOUT_SECONDS` as the canonical env name
- backend temporarily falls back to `SONIOX_STOP_TIMEOUT_SECONDS` only for compatibility
- local websocket and local STT smoke code consume `settings.stop_timeout_seconds`
- hosted Cloudflare keeps `STOP_TIMEOUT_SECONDS` as the canonical name
- hosted Cloudflare default becomes `30.0`

Do not keep two first-class runtime policy names after this task. The old
Soniox-specific name should survive only as a temporary backend fallback.

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd backend && uv run pytest tests/test_config.py tests/test_ws.py -v
cd cloudflare && uv run pytest tests/test_settings.py tests/test_session_runtime.py -v
```

Expected:

- backend config tests PASS
- local websocket tests PASS
- hosted settings tests PASS
- hosted session-runtime tests PASS

- [ ] **Step 5: Commit**

```bash
git add \
  backend/app/config.py \
  backend/app/ws.py \
  backend/app/stt_smoke.py \
  backend/tests/test_config.py \
  backend/tests/test_ws.py \
  cloudflare/src/settings.py \
  cloudflare/tests/test_settings.py
git commit -m "Unify stop timeout runtime policy"
```

## Task 1.3: Pin the public deploy base contract in Wrangler

**Purpose:**
Make the committed Worker config safe for direct custom-domain deployment by
keeping only true secrets in `secrets.required` and disabling `workers.dev`.

**Files:**
- Create: `cloudflare/tests/test_public_deploy_contract.py`
- Modify: `cloudflare/wrangler.jsonc`
- Read for context: `cloudflare/src/settings.py`

**Supports:**
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Supporting Verification: focused Cloudflare config tests

- [ ] **Step 1: Write the failing contract tests**

Add focused tests such as:

```python
from pathlib import Path

WRANGLER = Path(__file__).resolve().parents[1] / "wrangler.jsonc"

def test_required_secrets_only_include_provider_api_keys() -> None:
    text = WRANGLER.read_text()
    assert '"SONIOX_API_KEY"' in text
    assert '"GEMINI_API_KEY"' in text
    assert '"MISTRAL_API_KEY"' in text
    assert '"SESSION_CAP_MS"' not in text.split('"required":', 1)[1]

def test_workers_dev_is_disabled_for_public_domain_deploys() -> None:
    text = WRANGLER.read_text()
    assert '"workers_dev": false' in text
```

Keep these tests narrowly scoped to the public deploy contract instead of
retesting the `031` asset boundary.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd cloudflare && uv run pytest tests/test_public_deploy_contract.py -v
```

Expected:

- FAIL because `SESSION_CAP_MS` is still incorrectly listed as a required secret
- FAIL because `workers_dev` is not yet explicitly disabled

- [ ] **Step 3: Write the minimal config change**

Update `cloudflare/wrangler.jsonc` so that:

- `secrets.required` contains only:
  - `SONIOX_API_KEY`
  - `GEMINI_API_KEY`
  - `MISTRAL_API_KEY`
- `SESSION_CAP_MS` is removed from the required secret list
- `workers_dev` is set to `false`

Do not move optional non-secret config into committed secrets or dashboard-only
tribal knowledge.

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_assets_config.py \
  -v
```

Expected:

- both test files PASS
- the `031` asset-serving contract still passes unchanged

- [ ] **Step 5: Commit**

```bash
git add cloudflare/wrangler.jsonc cloudflare/tests/test_public_deploy_contract.py
git commit -m "Pin public deploy wrangler contract"
```

## Task 1.4: Add the single scripted public deploy command

**Purpose:**
Replace ad hoc manual publish steps with one repo-owned entrypoint that builds
the frontend, syncs assets, uploads only the required secrets, and deploys to
the real public domain.

**Files:**
- Create: `cloudflare/scripts/deploy_public_app.py`
- Create: `cloudflare/tests/test_deploy_public_app.py`
- Reuse: `cloudflare/scripts/sync_frontend_dist.sh`
- Read for context: `frontend/package.json`, `backend/.env`

**Supports:**
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Acceptance Gate: `Public Deployment Reaches Link-Ready Operational State`
- Supporting Verification: narrow deploy-config validation

- [ ] **Step 1: Write the failing deploy-script tests**

Add focused tests for helpers such as:

```python
def test_collect_required_secrets_reads_only_public_provider_keys(tmp_path):
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "SONIOX_API_KEY=s\n"
        "GEMINI_API_KEY=g\n"
        "MISTRAL_API_KEY=m\n"
        "LOGFIRE_TOKEN=ignored\n"
    )
    assert collect_required_secrets(env_file) == {
        "SONIOX_API_KEY": "s",
        "GEMINI_API_KEY": "g",
        "MISTRAL_API_KEY": "m",
    }

def test_build_deploy_command_uses_public_domain_and_explicit_runtime_vars():
    cmd = build_deploy_command(
        public_domain="voice-todos.example.com",
        secrets_file=Path("/tmp/public.secrets.env"),
        session_cap_ms="65000",
        stop_timeout_seconds="12",
    )
    assert "--domain" in cmd
    assert "voice-todos.example.com" in cmd
    assert "--var" in cmd
    assert "STT_PROVIDER=soniox" in cmd
    assert "SESSION_CAP_MS=65000" in cmd
    assert "STOP_TIMEOUT_SECONDS=12" in cmd
```

Also add one test that the script refuses to continue if any required secret is
missing from the backend env source.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd cloudflare && uv run pytest tests/test_deploy_public_app.py -v
```

Expected:

- FAIL because the deploy script does not exist yet

- [ ] **Step 3: Write the minimal deploy entrypoint**

Implement `cloudflare/scripts/deploy_public_app.py` so it:

- requires `--public-domain`
- defaults the backend env source to `../backend/.env`
- reads only:
  - `SONIOX_API_KEY`
  - `GEMINI_API_KEY`
  - `MISTRAL_API_KEY`
- writes those three keys to a temporary `.env`-format secrets file for
  `pywrangler deploy --secrets-file`
- runs `pnpm build` in `frontend/`
- runs `cloudflare/scripts/sync_frontend_dist.sh`
- builds a deploy command that always includes:
  - `--domain <public-domain>`
  - `--var STT_PROVIDER=soniox`
- appends optional `--var SESSION_CAP_MS=...` and
  `--var STOP_TIMEOUT_SECONDS=...` only when those optional flags are supplied
- supports `--dry-run` by executing the local build and asset handoff, printing
  the Cloudflare deploy command, and skipping the actual publish step

Keep the script small and testable: parse env files and build command argv in
pure helpers, then keep subprocess execution in a thin wrapper.

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd cloudflare && uv run pytest tests/test_deploy_public_app.py -v
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain voice-todos.example.com \
  --dry-run
```

Expected:

- deploy-script tests PASS
- the dry-run executes the frontend build and asset sync successfully
- the dry-run prints the exact `pywrangler deploy` invocation it would run
- the printed command shows `STT_PROVIDER=soniox`
- optional non-secret vars are absent unless the caller explicitly passed them

- [ ] **Step 5: Commit**

```bash
git add cloudflare/scripts/deploy_public_app.py cloudflare/tests/test_deploy_public_app.py
git commit -m "Add scripted public cloudflare deploy command"
```

## Task 1.5: Tighten the browser smoke for public completion proof

**Purpose:**
The public deployment gate needs deterministic, exact fixture assertions rather
than a smoke that only proves "something happened."

**Files:**
- Modify: `scripts/browser_ui_smoke.sh`
- Read for assertions: `backend/tests/fixtures/while-speaking-two-todos/result.json`

**Supports:**
- Acceptance Gate: `Public Deployment Reaches Link-Ready Operational State`
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Supporting Verification: repo-owned browser smoke script

- [ ] **Step 1: Expand the smoke assertions**

Update `scripts/browser_ui_smoke.sh` so it:

- keeps accepting `<base-url>` and `<fixture-name>`
- keeps driving the real UI through `agent-browser`
- reads `backend/tests/fixtures/while-speaking-two-todos/result.json`
  for expected transcript and final todo titles
- fails if the final transcript or final todo list diverges from the fixture
  contract
- still exits non-zero on visible warning states such as failed microphone,
  websocket, or fixture setup
- prints the observed final transcript and todo list so the public smoke leaves
  behind useful evidence

- [ ] **Step 2: Static-check the script**

Run:

```bash
bash -n scripts/browser_ui_smoke.sh
```

Expected:

- PASS

- [ ] **Step 3: Run the tightened smoke against the local Cloudflare-served app**

In terminal A:

```bash
cd frontend && pnpm build
cd ../cloudflare && ./scripts/sync_frontend_dist.sh
set -a && source ../backend/.env && set +a
uv run pywrangler dev --port 8788
```

In terminal B:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Expected:

- the script exits `0`
- it proves the Cloudflare-served real UI reaches the expected final transcript
  and final todo list for the accepted fixture
- no Vite dev server is needed as the browser-facing boundary

- [ ] **Step 4: Commit**

```bash
git add scripts/browser_ui_smoke.sh
git commit -m "Strengthen cloudflare browser smoke assertions"
```

## Task 1.6: Write the operator runbook for publish, diagnosis, and recovery

**Purpose:**
Leave behind one clear operational path for deploy completion instead of
spreading critical knowledge across shell history and prior conversations.

**Files:**
- Create: `cloudflare/README.md`
- Reference: `cloudflare/scripts/deploy_public_app.py`
- Reference: `scripts/browser_ui_smoke.sh`
- Link: `docs/references/2026-05-07-mistral-live-validation-findings.md`

**Supports:**
- Acceptance Gate: `Deploy Contract And Publish Path Are Explicit And Repeatable`
- Acceptance Gate: `Public Deployment Reaches Link-Ready Operational State`
- Supporting Verification: deploy/runbook contract review

- [ ] **Step 1: Write the runbook**

Create `cloudflare/README.md` with concise sections for:

- required secrets in `backend/.env`:
  - `SONIOX_API_KEY`
  - `GEMINI_API_KEY`
  - `MISTRAL_API_KEY`
- required non-secret runtime config:
  - `STT_PROVIDER=soniox`
- optional non-secret runtime config:
  - `SESSION_CAP_MS`
  - `STOP_TIMEOUT_SECONDS`
- required local pre-publish smoke using the Cloudflare-served app boundary
- exact public deploy command:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN"
```

- required public post-deploy smoke using:

```bash
./scripts/browser_ui_smoke.sh "https://$PUBLIC_APP_DOMAIN" while-speaking-two-todos
```

- diagnosis via:

```bash
cd cloudflare && uv run pywrangler tail voice-todos-cloudflare --format pretty
```

- recovery by redeploying a previous known-good commit, for example:

```bash
git switch --detach <known-good-commit>
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN"
```

- a short note that `docs/references/2026-05-07-mistral-live-validation-findings.md`
  remains linked context only and is not a blocker for the Soniox-based first
  public deploy

- [ ] **Step 2: Verify the runbook contract**

Run:

```bash
rg -n \
  "pre-publish smoke|post-deploy smoke|pywrangler tail|known-good commit|Mistral" \
  cloudflare/README.md
```

Expected:

- the output shows one discoverable location for all required deploy,
  validation, diagnosis, and recovery instructions

- [ ] **Step 3: Run the full slice gates if implementation is complete**

Run:

```bash
cd cloudflare && uv run pytest \
  tests/test_public_deploy_contract.py \
  tests/test_deploy_public_app.py \
  -v
bash -n ../scripts/browser_ui_smoke.sh
```

Then run the two acceptance-gate procedures from the `Gate Execution` section:

- local Cloudflare prerequisite smoke
- real public deploy
- real public deterministic smoke

Expected:

- supporting verification PASS
- both `032` acceptance gates PASS with the required evidence collected

- [ ] **Step 4: Commit**

```bash
git add cloudflare/README.md
git commit -m "Document public cloudflare deploy workflow"
```

REQUIRED HANDOFF: `superpowers:executing-plans`

OPTIONAL HANDOFF: `superpowers:subagent-driven-development`
