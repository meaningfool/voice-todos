# Spec: Free-Tier Cloudflare Worker Bundle

## Source

- Follow-on work identified during `032` implementation after the real public
  deploy failed with Cloudflare error `10027` because the Worker upload
  exceeded the free-plan size limit.
- Continues the `03_cloudflare-public-deploy` track by restoring actual
  free-plan deployability for the accepted public Soniox path.

## Baseline

After `031` and the implemented parts of `032`, the repo already has:

- a same-origin local Cloudflare app boundary that serves the real UI and `/ws`
- a deterministic Cloudflare browser smoke for the accepted Soniox fixture flow
- a scripted public deploy entrypoint in `cloudflare/`

But the first real public deploy is still blocked:

- Cloudflare rejects the Worker upload on the free plan because the runtime
  bundle is too large
- the current Cloudflare runtime still ships optional dependency families that
  are not required for the accepted first public Soniox path
- the public deploy workflow is therefore operationally defined but not yet
  actually executable on the intended free-plan account

The backend extraction/runtime architecture is not the primary scope here.
This slice is specifically about the Cloudflare production runtime footprint.

## Target System

After this slice, the repo supports an accepted Cloudflare production bundle
that fits within the free Worker size limit for the first public deployment
shape.

That target system should:

- preserve the accepted same-origin public app shape
- preserve the accepted Soniox-first public runtime path
- make the production Cloudflare runtime dependency contract explicit
- remove or defer optional hosted runtime families that are not required for the
  accepted first public path when they threaten the free-plan size cap
- provide direct evidence that the production Worker can be published from the
  same free-plan account without the previous `10027` size failure

This slice is allowed to narrow the first public production contract if needed.
In particular, hosted Mistral support and Cloudflare-side Logfire parity do not
need to remain part of the blocking first public bundle if they are not
required for the accepted Soniox public path.

## Architecture

This slice separates:

- the **accepted first public production bundle**
- from **optional or follow-on hosted capabilities**

The accepted first public production bundle keeps only what is required for:

- serving the real UI from the Cloudflare app boundary
- serving same-origin `/ws`
- the existing Worker + Durable Object hosted runtime
- the accepted Soniox STT path
- the hosted extraction path already used by that accepted public flow

The slice does not require restoring the broader `014` shared-runtime-package
architecture. It only requires that the production Cloudflare runtime contract
be explicit, minimal, and demonstrably small enough for the intended free-plan
deploy target.

## Components

- **Production Cloudflare dependency contract**
  - the exact runtime dependency surface that is allowed to ship in the first
    public bundle

- **Optional hosted capability boundary**
  - explicit handling for non-blocking capabilities such as hosted Mistral or
    Cloudflare-side Logfire if they are excluded from the first public bundle

- **Free-plan deployability proof**
  - one repeatable way to prove that the production Worker no longer fails with
    Cloudflare error `10027`

- **Behavioral regression surface**
  - the existing same-origin Cloudflare app and deterministic Soniox fixture
    smoke that define whether the accepted public path still works

## Behavioral Delta

Before this slice:

- the public deploy workflow exists
- but the intended free-plan public deploy fails because the Worker bundle is
  too large

After this slice:

- the first public production bundle fits the intended free-plan size cap
- the accepted Soniox public app path still works
- free-plan deployability is no longer blocked by unnecessary production runtime
  dependencies

## Decisions

- Optimize first for the accepted Soniox public path.
- Treat the first public production bundle as a deliberately minimal contract,
  not as a requirement to ship every optional hosted capability immediately.
- Allow removal, deferral, or alternate packaging of optional runtime families
  when they are not required for the accepted Soniox public flow.
- Keep the scripted deploy entrypoint from `032` as the operator publish path.
- Use real publishability on the target free-plan account as the blocking proof,
  not only local artifact-size estimates.

## Non-Goals

- No paid Cloudflare plan requirement for first public deploy
- No browser protocol change
- No backend extraction redesign
- No requirement to restore the broader `014` shared extraction/runtime package
- No requirement that hosted Mistral remain in the same first public production
  bundle
- No requirement for Cloudflare-side Logfire parity in this slice

## Design And Implementation Constraints

- `cloudflare/` must remain the public deployment boundary
- the accepted first public path remains Soniox-based
- any capability removed from the blocking production bundle must be explicitly
  documented or explicitly rejected at runtime rather than silently disappearing
- the deterministic Cloudflare browser smoke remains the blocking behavioral
  proof for the accepted public flow
- same-origin UI plus `/ws` behavior must remain intact
- the scripted deploy path from `032` must remain the operator entrypoint once
  the bundle fits

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
