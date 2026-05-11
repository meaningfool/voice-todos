# Spec: Scripted Public Cloudflare Deploy Path

## Source

- Slice `V2` from
  [030_shaping_cloudflare-public-deploy.md](030_shaping_cloudflare-public-deploy.md)
- Follows `V1`, which establishes the same-origin Cloudflare app boundary
  locally

## Baseline

After `V1`, the repo should already support:

- a same-origin local Cloudflare app boundary that serves the real UI and `/ws`
- a deterministic local Cloudflare browser smoke for that boundary

But the public deployment path is still incomplete:

- there is no accepted single publish command for the whole app
- the final public subdomain is not yet part of a documented deploy workflow
- the Cloudflare runtime secret/config contract is not yet explicit enough for
  public operation
- public post-deploy verification is not yet defined as part of completion
- recovery and diagnosis rules are not yet part of the deployment workflow

The current Cloudflare config surface also mixes secrets and non-secret runtime
values. For example, `cloudflare/wrangler.jsonc` currently treats
`SESSION_CAP_MS` as required secret-like config even though it is a non-secret
runtime value.

## Target System

After this slice, the repo has one accepted public deployment path for the app.

That path should:

- target the final public subdomain from the start
- publish the whole app from `cloudflare/`
- use one human-triggered scripted deploy command
- build the frontend, sync the built assets into `cloudflare/`, and publish the
  Workers app

The deployment contract must distinguish:

- **required secrets**
  - `SONIOX_API_KEY`
  - `GEMINI_API_KEY`
  - `MISTRAL_API_KEY`
- **required non-secret config**
  - `STT_PROVIDER=soniox`
- **optional non-secret config**
  - `SESSION_CAP_MS`
  - `STOP_TIMEOUT_SECONDS`

Deployment completion also gains explicit operational proof:

- required local Cloudflare pre-publish smoke
- required public deterministic post-deploy smoke on the final subdomain

For this slice, the public post-deploy smoke reuses the deterministic smoke path
established in `V1`. Security hardening of that public smoke path is
intentionally deferred.

## Architecture

This slice adds deployment and operational structure on top of the already
proven local app boundary.

Target flow:

```text
local Cloudflare smoke passes
-> one deploy command
-> frontend build
-> asset sync into cloudflare/
-> Cloudflare publish
-> open final public subdomain
-> run required public deterministic smoke
```

This slice does not change the app’s public runtime architecture:

- UI and `/ws` remain same-origin
- the Worker + Durable Object session runtime remains intact

What changes is the operational contract around that runtime:

- one explicit publish path
- one explicit runtime config contract
- one explicit completion procedure
- one explicit lightweight recovery/diagnosis posture

## Components

- **Final public subdomain deployment target**
  - deploy directly to the real public app URL

- **Scripted deploy command**
  - one human-triggered command owns build, asset sync, and publish

- **Secrets/config contract**
  - required secrets vs non-secret runtime config are explicit

- **Pre-publish local smoke gate**
  - the already-defined local Cloudflare smoke becomes a required prerequisite

- **Public post-deploy smoke**
  - deterministic verification on the real public subdomain

- **Lightweight recovery/diagnosis**
  - Cloudflare logs for diagnosis
  - redeploy previous known-good commit for recovery

## Behavioral Delta

Before this slice:

- the app shape is proven locally
- public deployment remains ad hoc or undefined

After this slice:

- there is one accepted public deployment path
- deployment is not considered complete until the real public app passes the
  required smoke
- public operation has an explicit secrets/config contract and lightweight
  recovery/diagnosis rules

## Decisions

- Keep one public environment rather than staging plus production
- Deploy directly to the final public subdomain
- Use one human-triggered scripted deploy command rather than CI automation
- Keep local Cloudflare smoke as a manual prerequisite rather than embedding it
  into the deploy command
- Reuse the deterministic smoke path from `V1` for public post-deploy smoke in
  this slice
- Use Cloudflare logs rather than Cloudflare-side Logfire parity for first
  public deployment diagnosis
- Keep only the security hardening of public deterministic smoke out of this
  slice

## Non-Goals

- No staging environment
- No CI auto-deploy
- No Cloudflare-side Logfire parity
- No operator-gated hardening of deterministic public smoke
- No Cloudflare Access or other operator-only authorization surface
- No full rollback system beyond redeploying the previous known-good commit
- No change to the hosted runtime shape selected in work item `01`
- No requirement to use `GOOGLE_CLOUD_PROJECT_ID` in the deployment contract

## Design And Implementation Constraints

- The deploy path must preserve `cloudflare/` as the public deployment boundary
- The frontend build must remain sourced from `frontend/`
- The deployment contract must clearly distinguish required secrets from
  required or optional non-secret runtime config
- Public deploy readiness is defined against the configured `STT_PROVIDER`, with
  the initial public deployment using Soniox
- The known Mistral live-validation gap must remain documented but non-blocking
  for this slice
- The public smoke for this slice must reuse the deterministic smoke path
  established earlier
- Recovery must be defined in the lightweight form selected during shaping

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
