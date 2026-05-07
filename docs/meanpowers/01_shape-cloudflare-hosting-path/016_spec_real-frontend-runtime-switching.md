# Spec: Real Frontend Runtime Switching For Local FastAPI And Cloudflare

## Source

- Follow-on work identified after `V3`
- Clarifies a gap left by the earlier hosted-runtime slices: the hosted websocket path was validated with browser-style smoke/harness clients, but not yet through the real app UI

## Baseline

After `V3`, both local runtimes exist:

- local FastAPI websocket path:
  - [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py)
- local Cloudflare Worker + Durable Object websocket path:
  - [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/entry.py)
  - [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)

The frontend app UI currently opens:
- `ws://<current-host>/ws`
through [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts)

The frontend dev server currently proxies `/ws` only to the local backend port through [frontend/vite.config.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/vite.config.ts).

The hosted Worker currently requires:
- `/ws?session=<id>`
in [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/entry.py)

So the current state is:
- the real frontend works against FastAPI
- the hosted Cloudflare runtime works through smoke tools and a custom browser harness
- the real frontend is **not yet** drop-in compatible with the local Cloudflare runtime

## Target System

After this slice, the real app UI can be run locally against either backend runtime without changing frontend application code.

The frontend still opens `/ws` exactly once way:
- it does not learn runtime-specific websocket URLs
- it does not learn runtime-specific query params
- it does not branch on FastAPI vs Cloudflare

Instead, local runtime selection becomes an explicit dev configuration concern:
- `WS_BACKEND=fastapi` routes the real app UI to the FastAPI websocket backend
- `WS_BACKEND=cloudflare` routes the real app UI to the Cloudflare Worker websocket backend

The Cloudflare Worker becomes compatible with the same frontend websocket contract by accepting plain `/ws` from the real UI and internally resolving session ownership without requiring the frontend to append `?session=...`.

Smoke tools and harness pages may keep optional explicit-session support for focused debugging, but that support is no longer required for the real UI.

## Architecture

This slice keeps the frontend runtime-agnostic and moves the missing integration into dev routing and Worker compatibility.

The frontend hook remains product-level:
- connect to `/ws`
- process the shared websocket protocol

The dev server owns local runtime selection:
- proxy `/ws` to FastAPI or Cloudflare based on explicit config

The Worker owns frontend compatibility:
- accept plain `/ws`
- preserve optional explicit `?session=...` support if needed for smoke tooling
- derive or allocate the session id internally for real UI sessions

This avoids teaching the frontend about backend runtime details while still making both runtimes easy to test locally.

## Components

- **Frontend websocket client**
  - [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts)
  - should remain runtime-agnostic and keep opening `/ws`

- **Frontend dev routing**
  - [frontend/vite.config.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/vite.config.ts)
  - should expose explicit local backend selection for websocket proxying

- **Cloudflare entry compatibility**
  - [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/entry.py)
  - should accept plain `/ws` from the real frontend
  - may preserve optional `?session=...` compatibility for smoke scripts

- **Hosted session runtime**
  - [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)
  - should remain the hosted session owner
  - this slice should not reopen transcript/todo behavior beyond connection bootstrap needs

- **Real UI live validation surface**
  - the actual frontend app, not only `cloudflare/dev/todo_parity_browser_check.html`

## Behavioral Delta

Before this slice:
- FastAPI is testable through the real UI
- Cloudflare is testable through smoke/harness tooling but not the real UI unchanged

After this slice:
- the same real UI can be run locally against either FastAPI or Cloudflare
- switching runtimes does not require editing frontend websocket code
- Cloudflare no longer requires a frontend-supplied `session` query param for real UI use

## Decisions

- Keep the frontend hook runtime-agnostic
- Put runtime selection in dev config, not in frontend application logic
- Make Cloudflare accept the same frontend websocket entry contract as FastAPI
- Preserve smoke/harness tooling compatibility if possible, but make it supporting verification rather than the primary manual-E2E path

## Non-Goals

- No remote Cloudflare deployment in this slice
- No change to transcript/todo/finalization behavior beyond connection compatibility
- No redesign of the websocket message protocol
- No removal of smoke scripts or focused harness tools if they remain useful
- No general production runtime-selection UI inside the product

## Design And Implementation Constraints

- The real frontend must continue to connect to `/ws` without runtime-specific branching
- `WS_BACKEND` selection must be explicit and deterministic in local dev
- Invalid backend-selection config must fail clearly rather than silently routing to the wrong target
- Cloudflare plain `/ws` support must not break existing focused smoke tooling unless the tooling is intentionally migrated in the same slice
- Browser-visible websocket semantics after connection establishment must remain unchanged in both runtimes

## Acceptance Gate: Real App UI Works Against Both Local Runtimes

**Why this gate matters:**
This is the missing product-level proof. If the real frontend still cannot run unchanged against both backends, then local Cloudflare support remains a harness-only capability rather than a true alternate runtime for the app.

**Criteria**
- The real app UI can be launched locally in FastAPI mode and complete the accepted websocket flow through the FastAPI backend.
- The real app UI can be launched locally in Cloudflare mode and complete the same accepted websocket flow through the Cloudflare backend.
- Switching between FastAPI mode and Cloudflare mode does not require editing frontend application code or changing the frontend websocket URL shape.

**Proof**
- **FastAPI setup:** run the local backend and frontend with `WS_BACKEND=fastapi`
- **FastAPI action:** use the real app UI in a browser to start recording, stream audio, and stop
- **FastAPI assertions:** verify the UI reaches the accepted browser-visible behavior already expected locally, including transcript activity and clean stop behavior
- **Cloudflare setup:** run the local Worker and frontend with `WS_BACKEND=cloudflare`
- **Cloudflare action:** use the same real app UI in a browser to start recording, stream audio, and stop
- **Cloudflare assertions:** verify the same UI reaches transcript activity, todo behavior where applicable, and clean stop behavior through the hosted runtime
- **Shared assertion:** no frontend websocket code edits or runtime-specific URL changes are required between the two runs; only local runtime configuration changes

**Expected evidence**
- exact local commands used to run:
  - FastAPI backend
  - Cloudflare Worker
  - frontend in both modes
- `agent-browser` commands used against the real app UI
- observed browser-visible outcomes for both modes

## Acceptance Gate: Local Runtime Selection And Worker Compatibility Are Explicit And Correct

**Why this gate matters:**
Even if one manual run works, the slice is incomplete if runtime switching is ambiguous or if Cloudflare still requires a frontend-specific compatibility hack outside the real UI contract.

**Criteria**
- Local frontend runtime selection is explicit through dev configuration rather than hidden code edits.
- `WS_BACKEND=fastapi` routes `/ws` to the FastAPI backend.
- `WS_BACKEND=cloudflare` routes `/ws` to the Cloudflare Worker backend.
- The Cloudflare Worker accepts plain `/ws` from the frontend instead of requiring a frontend-supplied `session` query parameter.

**Proof**
- **Config proof:** inspect [frontend/vite.config.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/vite.config.ts) and show explicit runtime-selection behavior
- **Worker proof:** inspect [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/entry.py) and show plain `/ws` compatibility for real frontend requests
- **Negative-config proof:** run the frontend with an invalid `WS_BACKEND` value and assert startup fails clearly rather than silently proxying to an unintended target

**Expected evidence**
- code references showing explicit Vite runtime selection and Cloudflare plain `/ws` handling
- exact failing startup output for invalid backend selection
- brief note on whether optional `?session=...` compatibility was preserved for smoke tooling

## Supporting Verification

- keep or update focused smoke scripts for direct runtime debugging
- add or update a narrow test around invalid `WS_BACKEND` handling if that is practical
- add or update a focused Worker compatibility test for plain `/ws` session bootstrap if that is practical
- run existing frontend/backend regression checks only as needed for touched files
