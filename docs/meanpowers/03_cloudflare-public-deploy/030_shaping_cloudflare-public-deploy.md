# Shaping: Cloudflare Public Deploy

## Source

- Originating inbox item: `INB-0003_cloudflare-public-deploy.md`
- Source conversation/document: Conductor shaping thread for publishing the
  existing hosted app on a public Cloudflare subdomain
- Shaping started: 2026-05-11
- Shaping confirmed: 2026-05-11

## Compressed Problem

**Problem statement:**

`How might we deploy the hosted voice-todos app to Cloudflare as one public same-origin app?`

## Baseline

### Current Actor Journeys

- A browser user can run the app locally against FastAPI or against the local
  Cloudflare `/ws` runtime.
- The frontend already assumes same-origin WebSocket usage at `/ws`.
- The Cloudflare runtime already uses the selected Worker front door +
  session-owned Durable Object runtime for hosted sessions.

### Current Observable Behavior

- Local FastAPI and local Cloudflare `/ws` flows exist.
- The Cloudflare Worker currently serves the WebSocket path and returns `404`
  for non-`/ws` routes.
- The public deployment path for the whole app does not exist yet.

### Current Components / Internals

- `frontend/` owns the UI source and currently builds independently.
- `cloudflare/` owns the hosted runtime boundary and already contains the
  Worker + Durable Object session runtime.
- `cloudflare/src/entry.py` is currently a websocket-first entrypoint.
- `016` proved local frontend runtime switching, not public same-origin hosting.

## Requirements (R)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| R0 | The app is publicly deployable on a subdomain of the personal site. | Core goal | |
| R1 | The public app serves the UI and `/ws` from the same origin. | Must-have | Simplicity and browser behavior are the primary reasons. |
| R2 | The selected Worker + Durable Object session runtime remains the hosted `/ws` architecture. | Must-have | This shape does not reopen the top-level runtime decision from work item `01`. |
| R3 | The deployment model uses one public environment rather than formal staging plus production. | Must-have | Local Cloudflare remains the pre-publish baseline. |
| R4 | The repo layout remains split between `frontend/` source and `cloudflare/` deploy boundary. | Must-have | Avoid a repo restructure unless later friction proves it necessary. |
| R5 | `cloudflare/` becomes the single public deployment boundary for frontend assets plus the existing `/ws` runtime. | Must-have | |
| R6 | The deploy flow is human-triggered and runs through one scripted publish command. | Must-have | CI automation is out of scope. |
| R7 | The deploy flow builds the frontend first, then syncs build output into `cloudflare/` before publish. | Must-have | |
| R8 | A local Cloudflare browser smoke check is required before publish. | Must-have | |
| R9 | A public post-deploy browser smoke check on the real subdomain is required before the deployment is considered complete. | Must-have | |
| R10 | The smoke checks run against the `STT_PROVIDER` configured for the app, with the initial public deployment using Soniox. | Must-have | |
| R11 | The known real-Mistral live-validation gap is documented but does not block the first public deployment. | Must-have | Public deployment proof uses Soniox. |
| R12 | Cloudflare-managed secrets are used for deployed runtime credentials, while local `.env` remains the local development source. | Must-have | |
| R13 | The deployment contract clearly distinguishes required secrets from non-secret runtime config. | Must-have | |
| R14 | The first public deployment requires only lightweight diagnosability via Cloudflare logs. | Must-have | Cloudflare-side Logfire parity is out of scope. |
| R15 | Recovery from a bad deploy is redeploying the previous known-good commit. | Must-have | A formal rollback system is out of scope. |
| R16 | Formal staging, CI auto-deploy, Cloudflare Logfire parity, and one-click deploy UX are out of scope. | Out | |
| R17 | `GOOGLE_CLOUD_PROJECT_ID` is part of the deployment contract. | Out | Present in config surface today, but not operationally required by current behavior. |

## Journeys (J)

| ID | Journey / Step | Actor | Description |
|---|---|---|---|
| J1 | Use the public app | end user | A user opens the public subdomain, starts a session, and the app behaves as one same-origin browser app with `/ws`. |
| J2 | Run the local pre-publish smoke | operator | The operator runs the same-origin app locally on Cloudflare, verifies the Soniox fixture flow, and only then publishes. |
| J3 | Publish and validate | operator | The operator runs one deploy command, then verifies the real public subdomain before treating the deployment as complete. |
| J4 | Recover from a bad deploy | operator | The operator redeploys the previous known-good commit and, if needed, temporarily removes exposure from the personal site. |

## Shapes (S)

### Shape Options

| ID | Shape | Summary | Status |
|---|---|---|---|
| P | Single Workers public app boundary | `cloudflare/` publishes one Cloudflare Workers app that serves the built frontend assets and the existing Worker + Durable Object `/ws` runtime on one public subdomain. | Selected |
| X1 | Split public hosting surfaces | Host the frontend and websocket runtime through different public surfaces while preserving same-domain behavior through extra routing glue. | Excluded |
| X2 | Formal staging plus production environments | Add at least two public Cloudflare environments and promotion flow before the first public release. | Excluded |

### Selected Shape Components

| ID | Component | Flag | Notes |
|---|---|:---:|---|
| P1 | Final public subdomain app boundary |  | The deployment target is the final public subdomain from the start. |
| P2 | Same-origin static frontend serving from `cloudflare/` |  | The Worker app serves the built frontend assets in addition to `/ws`. |
| P3 | Existing Worker + Durable Object `/ws` runtime retained |  | Reuse the hosted runtime shape already established by work item `01`. |
| P4a | Local frontend asset handoff into `cloudflare/` |  | `frontend/` remains the source of truth for the UI build, but the local Cloudflare app needs a deterministic asset handoff to serve the UI and `/ws` together. |
| P4b | Deploy-time frontend asset handoff into `cloudflare/` |  | The public publish path reuses the same basic handoff, but as part of the scripted deploy flow. |
| P5 | One scripted human-triggered deploy command |  | The command orchestrates build, asset sync, and Cloudflare publish. |
| P6 | Cloudflare secrets and config contract |  | Required secrets: `SONIOX_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`. Required non-secret config: `STT_PROVIDER=soniox`. Optional non-secret config: `SESSION_CAP_MS`, `STOP_TIMEOUT_SECONDS`. |
| P7a | Local Cloudflare smoke scenario |  | Define and prove the deterministic browser smoke that exercises the same-origin local Cloudflare app shape. |
| P7b | Local Cloudflare smoke as deploy gate |  | The already-defined local smoke becomes a required manual prerequisite before publish. |
| P8 | Public deterministic post-deploy smoke on the real subdomain |  | Required completion step after publish. |
| P9 | Lightweight diagnosability and recovery |  | Use Cloudflare logs plus redeploy of the previous known-good commit. |

## Selected Shape

**Selected option:**

`P` Single Workers public app boundary

**Why this shape:**

This is the smallest public deployment shape that stays aligned with the
existing architecture decisions:

- the Worker + Durable Object session runtime is already selected and partially
  implemented
- the frontend already wants same-origin `/ws`
- the user wants one public subdomain, one environment, and simplicity over
  release machinery

This shape keeps those decisions intact and scopes the next work to packaging,
asset serving, deployment flow, and operational proof.

**Key tradeoffs:**

- UI and runtime deploy together rather than on independent release cadences.
- The first public release accepts manual scripted deployment instead of CI.
- The first public release accepts Cloudflare logs instead of Cloudflare-side
  Logfire parity.

## Final Slices

### Selected Slicing Logic

**Rationale:**

The open work is no longer about runtime feasibility. It is about making the
public app boundary real, then making that boundary publishable. The slices
therefore separate:

1. creating the same-origin Cloudflare app shape locally
2. turning that local shape into a repeatable public deployment path

To keep the slices clean, component boundaries are split between:

- app-boundary mechanics: `P2`, `P3`, `P4a`, `P7a`
- deployment-process mechanics: `P1`, `P4b`, `P5`, `P6`, `P7b`, `P8`, `P9`

**Map:**

| Component | V1 | V2 |
|---|---:|---:|
| P1 Final public subdomain app boundary |  | X |
| P2 Same-origin static frontend serving from `cloudflare/` | X |  |
| P3 Existing Worker + Durable Object `/ws` runtime retained | X |  |
| P4a Local frontend asset handoff into `cloudflare/` | X |  |
| P4b Deploy-time frontend asset handoff into `cloudflare/` |  | X |
| P5 One scripted human-triggered deploy command |  | X |
| P6 Cloudflare secrets and config contract |  | X |
| P7a Local Cloudflare smoke scenario | X |  |
| P7b Local Cloudflare smoke as deploy gate |  | X |
| P8 Public deterministic post-deploy smoke on the real subdomain |  | X |
| P9 Lightweight diagnosability and recovery |  | X |

### V1: Same-Origin Local Cloudflare App Boundary

**State after this slice:**

- `cloudflare/` serves the built frontend assets and `/ws` together as one local
  Cloudflare app.
- The frontend still lives in `frontend/`, and the Cloudflare runtime still
  lives in `cloudflare/`.
- The local Cloudflare path becomes the primary deployment baseline rather than
  only a websocket runtime check.
- One deterministic browser smoke proves the same-origin app shape locally.

**Included components:**

- P2
- P3
- P4a
- P7a

**Notes for `meanpowers:write-spec`:**

- Acceptance should prove the local same-origin app shape through the browser,
  not only through tests.
- Use the configured provider contract, with Soniox as the initial proof path.
- Do not pull public DNS, secrets management, or publish automation into this
  slice.

### V2: Scripted Public Cloudflare Deploy Path

**State after this slice:**

- One deploy command builds the frontend, syncs assets into `cloudflare/`, and
  publishes the Workers app.
- Required secrets and non-secret config are documented as an explicit deploy
  contract.
- The deploy is considered complete only after the real public subdomain passes
  the required post-deploy smoke.
- Recovery and runtime diagnosis are documented in the lightweight form chosen
  during shaping.

**Included components:**

- P1
- P4b
- P5
- P6
- P7b
- P8
- P9

**Notes for `meanpowers:write-spec`:**

- Acceptance must include a manual operational proof path on the real public
  subdomain after publish.
- Keep the release shape simple: no staging environment, no CI deploy, no
  Cloudflare Logfire parity.
- The spec should keep the Mistral live-validation gap explicitly out of scope
  for deploy readiness.
- For this slice, public post-deploy smoke uses the same deterministic smoke
  path publicly, without security hardening yet.

### Optional V3: Operator-Gated Deterministic Public Smoke

**Why this is separate:**

This would harden an already-existing public deterministic smoke surface with
its own security boundary. It is useful, but it is not required to make the app
publicly deployable.

**State after this slice:**

- The public app keeps the deterministic smoke path introduced earlier.
- That existing smoke path is now protected server-side rather than exposed as a
  public query-param-only capability.
- Public post-deploy verification still reuses fixture-driven browser checks,
  but now through an authorized operator path.

**Notes for later shaping/spec work:**

- Treat this as an operational hardening follow-up, not as part of the first
  public deployment path.
- The likely shape is Worker-enforced operator authorization plus protected
  fixture access.

## Decision Record

| Decision | Rationale | Rejected Options |
|---|---|---|
| Publish the whole app from one Cloudflare Workers app boundary | Matches the same-origin goal and avoids extra routing complexity. | Split public hosting surfaces |
| Keep `frontend/` as source and `cloudflare/` as deploy boundary | Preserves current repo layout while keeping one public publish target. | Repo restructure around a new monolithic app folder |
| Use one human-triggered deploy command | Keeps the first release repeatable without adding CI machinery. | Ad hoc multi-command deploy; CI auto-deploy |
| Require local Cloudflare smoke before publish and public smoke after publish | Gives operational proof without introducing a second environment. | Local-only validation; no required public smoke |
| Keep public deterministic smoke in `V2` and defer only its security hardening to `V3` | Preserves the deterministic first-release verification path while isolating the added security/authorization complexity. | Moving deterministic public smoke itself into `V3` |
| Use Cloudflare logs for first-release diagnosability | Adequate for the first public deploy and consistent with the low-complexity release model. | Cloudflare-side Logfire parity as a deployment requirement |
