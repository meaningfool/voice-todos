# Spec: Same-Origin Local Cloudflare App Boundary

## Source

- Slice `V1` from
  [030_shaping_cloudflare-public-deploy.md](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/docs/meanpowers/03_cloudflare-public-deploy/030_shaping_cloudflare-public-deploy.md:1)
- Follow-on work after `016`, which proved local runtime switching through the
  frontend dev server but did not make `cloudflare/` the same-origin app
  boundary

## Baseline

After `016`, the repo supports two local websocket runtime targets:

- FastAPI through [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/backend/app/ws.py:1)
- Cloudflare Worker + Durable Object through
  [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/cloudflare/src/entry.py:1)
  and
  [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/cloudflare/src/session_runtime.py:1)

The real frontend currently connects to:

- `ws(s)://<current-host>/ws`
  in
  [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/frontend/src/hooks/useTranscript.ts:1)

Local runtime selection today is owned by the Vite dev server proxy in
[frontend/vite.config.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/frontend/vite.config.ts:1):

- `WS_BACKEND=fastapi` proxies `/ws` to FastAPI
- `WS_BACKEND=cloudflare` proxies `/ws` to the local Worker runtime

The Cloudflare app boundary is still websocket-only:

- [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/cloudflare/src/entry.py:1)
  accepts `/ws`
- non-`/ws` routes currently return `404`

So the current state is:

- local Cloudflare websocket behavior exists
- the real frontend can already talk to that runtime through the dev server
- but `cloudflare/` does not yet serve the real app UI and `/ws` together as one
  same-origin local app boundary

## Target System

After this slice, `cloudflare/` becomes a real same-origin local app boundary.

The local Cloudflare runtime should serve:

- the built frontend assets
- the existing Worker + Durable Object `/ws` runtime

from the same local Cloudflare origin.

The frontend source of truth remains in `frontend/`. This slice does not move
UI source code into `cloudflare/`; instead, it defines a deterministic local
asset handoff from the frontend build output into the Cloudflare app boundary.

This slice also defines the deterministic smoke path for that same-origin
Cloudflare-served app. Because the current fixture path is dev-only, the slice
may add a built-app smoke mechanism that works from the Cloudflare-served app
boundary and can later be reused by the public deployment slice.

## Architecture

This slice establishes the public app shape locally before any deployment
automation exists.

Target boundary:

```text
frontend/          -> source of truth for UI
frontend build     -> produces static assets
cloudflare/        -> serves static assets + /ws runtime together
```

The hosted runtime shape does not change:

- Worker front door
- Durable Object session owner
- same websocket protocol at `/ws`

What changes is the app boundary around it:

- `cloudflare/` stops being only a websocket runtime target
- it becomes a same-origin local app that can be opened directly in the browser
- the Vite proxy path becomes supporting local tooling rather than the proof
  surface for this slice

## Components

- **Same-origin local Cloudflare app boundary**
  - `cloudflare/` serves frontend assets and `/ws` together

- **Frontend asset handoff**
  - `frontend/` remains source of truth
  - the build output is handed into the Cloudflare app boundary explicitly

- **Retained hosted runtime**
  - existing Worker + Durable Object session ownership remains intact

- **Local deterministic smoke path**
  - the real app UI can be verified locally on the Cloudflare-served origin
  - the deterministic smoke path established here is the same one that `V2`
    later reuses publicly

## Behavioral Delta

Before this slice:

- local Cloudflare proves the websocket runtime
- the frontend still relies on a separate dev server boundary for the real UI

After this slice:

- the real app UI can be opened directly from the local Cloudflare app boundary
- that same origin serves both the UI and `/ws`
- the local Cloudflare path becomes the primary deployment baseline for the app
  boundary rather than just a websocket target

## Decisions

- Keep `frontend/` as the UI source of truth
- Keep the existing Worker + Durable Object runtime shape
- Make `cloudflare/` serve the built UI and `/ws` together locally
- Use a deterministic local browser smoke path for this boundary
- Let this slice establish the deterministic smoke path that `V2` later reuses
  on the public deployment surface

## Non-Goals

- No public deployment in this slice
- No DNS or subdomain work
- No scripted publish command
- No Cloudflare secrets contract beyond what is needed to run the local smoke
- No operator-gated public smoke mode
- No change to transcript/todo/finalization behavior beyond what is required to
  serve the real app from the Cloudflare boundary
- No repo restructure that merges `frontend/` into `cloudflare/`

## Design And Implementation Constraints

- The real frontend must still connect to `/ws` with no runtime-specific URL
  branching in product code
- `cloudflare/` must serve the real app UI directly for this slice’s acceptance
  proof
- The retained Worker + Durable Object runtime must remain the owner of hosted
  session behavior
- The frontend build output must be handed into `cloudflare/` explicitly rather
  than duplicating UI source files there
- The deterministic smoke path defined in this slice must be compatible with
  reuse by the later public deployment slice
- The Vite websocket proxy path may remain available, but it must not be the
  proof surface for this slice

## Acceptance Gate: Local Cloudflare Same-Origin App Works Through The Real UI

**Why this gate matters:**
This slice exists to prove the app boundary, not just the websocket runtime. If
the real UI still cannot be opened directly from the local Cloudflare app
boundary and complete the accepted session flow, then the target shape has not
been established.

**Criteria**

- The local Cloudflare app serves the real frontend UI directly from the same
  origin that serves `/ws`.
- A browser session started from that Cloudflare-served UI reaches the accepted
  voice-todo flow through the existing Worker + Durable Object runtime.
- The local smoke flow is deterministic and does not require a live microphone.

**Proof**

- **Setup**
  - build the frontend for Cloudflare consumption
  - start the local Cloudflare app boundary from `cloudflare/`
- **Action**
  - open the local Cloudflare URL in a browser
  - invoke the real app UI’s local deterministic smoke path using the accepted
    `while-speaking-two-todos` fixture scenario or equivalent deterministic
    smoke mechanism that can later be reused by `V2`
  - start the session and stop it through normal UI interaction
- **Assertions**
  - the app loads from the Cloudflare-served origin rather than the Vite dev
    server
  - the browser websocket connects to same-origin `/ws`
  - during the run, the UI shows transcript activity and todo updates
  - after stop, the UI shows the finalized transcript, the expected final todo
    list for the fixture, and returns to the normal idle/start state

**Expected evidence**

- exact frontend build and local Cloudflare startup commands
- exact `agent-browser` commands used against the Cloudflare-served app
- observed browser-visible outcomes proving transcript flow, todo flow, and
  clean stop on the same origin

## Acceptance Gate: Local Cloudflare App Boundary And Asset Handoff Are Explicit

**Why this gate matters:**
One successful browser run is not enough if the local Cloudflare app boundary
still depends on hidden manual steps or a muddled source-of-truth boundary. The
slice must leave behind a clear and repeatable local app shape.

**Criteria**

- `frontend/` remains the source of truth for UI code.
- `cloudflare/` consumes built frontend assets rather than duplicating UI source
  files.
- The local Cloudflare boundary explicitly serves frontend routes in addition to
  `/ws`.
- The local same-origin smoke path no longer depends on the Vite websocket proxy
  as its app boundary.

**Proof**

- **Code-boundary proof**
  - inspect the files that define:
    - the frontend build output handoff
    - the Cloudflare static asset serving boundary
    - the retained `/ws` entrypoint
- **Process proof**
  - show the explicit command or documented procedure used to refresh the
    frontend assets consumed by `cloudflare/`
  - verify that the local Cloudflare smoke run can be executed without running
    the Vite dev server as the browser-facing app boundary

**Expected evidence**

- code references showing asset handoff and same-origin Cloudflare serving
- exact command or documented procedure for refreshing the frontend assets used
  by `cloudflare/`
- brief note confirming whether the Vite dev server remained available only as
  supporting tooling

## Supporting Verification

- run a focused frontend build verification for the asset handoff path
- run focused Cloudflare entry/runtime tests for touched files
- add or update a narrow test for non-`/ws` frontend route serving if practical
- run lint/type checks only for touched frontend and Cloudflare surfaces
