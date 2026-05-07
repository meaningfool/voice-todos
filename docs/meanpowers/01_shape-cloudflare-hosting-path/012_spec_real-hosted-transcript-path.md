# Spec: Real Hosted Transcript Path

## Source

- Shaping document: [010_shaping_shape-cloudflare-hosting-path.md](./010_shaping_shape-cloudflare-hosting-path.md)
- Shaping slice: `V2`
- Scope: first real Cloudflare Worker + Durable Object hosted path for session ownership, transcript flow, stop finalization, provider transport, and session-cap teardown

## Baseline

After `V1`, the repo has a shared live-session controller in [backend/app/live_session.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/live_session.py), a preserved local FastAPI `/ws` adapter in [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py), and the existing shared provider/transcript contracts in:

- [backend/app/stt.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt.py)
- [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/transcript_accumulator.py)

The browser contract is still consumed by [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts) and expects `started`, `transcript`, `todos`, `stopped`, and `error` messages over `/ws`.

No real hosted runtime path exists yet in the product code. The only Cloudflare evidence so far is in the local prototype spikes:

- `X6` proved Worker + Durable Object session ownership, websocket routing, browser protocol shape, and session-cap enforcement locally.
- `X7` proved outbound Soniox transport mechanics and the app's real `finalize -> EOS -> final transcript` stop contract inside a Python Durable Object.

## Target System

After this slice, the repo contains a real hosted Cloudflare app boundary, separate from the local FastAPI adapter, that supports the transcript half of the app end to end.

The hosted path provides:

- a Cloudflare Worker `/ws` ingress
- one Durable Object per live browser session
- outbound Soniox transport through a Cloudflare-specific `SttSession` adapter
- transcript streaming over the existing browser websocket protocol
- finalized transcript return on stop using the existing shared controller contract
- server-side hosted session-cap enforcement with clean teardown

The local FastAPI path remains available and behaviorally unchanged.

Hosted todo behavior is intentionally incomplete in this slice. `V2` proves the runtime and transcript path only; hosted todo parity remains a `V3` concern.

## Architecture

This slice adds a sibling hosted adapter surface instead of expanding the local backend package into a mixed runtime area.

Recommended physical structure:

```text
backend/
  app/
    live_session.py
    stt.py
    transcript_accumulator.py
    ws.py

cloudflare/
  wrangler.jsonc
  src/
    entry.py
    session_runtime.py
    stt_soniox_cf.py
```

The shared session core remains where it lives after `V1`, inside `backend/app/`, and is reused by both adapters for now. `V2` does not add a packaging refactor to move it into a neutral top-level shared package.

The Worker front door stays thin. It owns only:

- `/ws` request handling
- websocket upgrade acceptance
- routing one session to one Durable Object instance

The Durable Object is the actual hosted session runtime. It owns:

- the accepted browser websocket
- the shared `LiveSessionController`
- browser control parsing and hosted browser message sends
- stop/finalization lifecycle integration
- session-cap enforcement
- hosted teardown and close behavior

The Cloudflare Soniox transport adapter implements the existing `SttSession` contract using the Cloudflare-specific outbound websocket mechanics proven in `X7`.

## Components

- **Shared session/transcript/finalization core**: reuse [backend/app/live_session.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/live_session.py), [backend/app/stt.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt.py), and [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/transcript_accumulator.py) unchanged except for any narrowly necessary hosted integration support.
- **Local adapter**: [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py) remains the local `/ws` adapter and is not reopened for behavior changes in this slice.
- **Worker ingress**: `cloudflare/src/entry.py` accepts `/ws` and routes to the session Durable Object.
- **Session-owned Durable Object runtime**: `cloudflare/src/session_runtime.py` owns browser websocket lifecycle, hosted message mapping, shared-controller use, cap enforcement, and teardown.
- **Cloudflare Soniox transport**: `cloudflare/src/stt_soniox_cf.py` hides Cloudflare-specific websocket mechanics behind the existing `SttSession` contract.

## Data Flow

1. The browser opens `/ws` with the same browser-side protocol expectations it already has.
2. The Worker front door accepts the websocket upgrade and routes the request to one Durable Object instance for that session.
3. The Durable Object accepts the browser websocket, creates the shared `LiveSessionController`, and injects the Cloudflare-specific Soniox `SttSession` factory.
4. Browser binary audio frames flow into the Durable Object, then into the shared controller, then into the Cloudflare Soniox adapter.
5. Soniox events are translated into the existing `SttEvent` shape, consumed by the shared controller, and mapped by the Durable Object back into browser `transcript` messages.
6. On `stop`, the Durable Object calls controller stop. The controller preserves the existing contract: request final transcript, send EOS, wait for finalization, and return the final transcript.
7. The Durable Object sends `stopped` with the finalized transcript and closes the hosted session cleanly.
8. If the demo session cap is reached first, the Durable Object enforces a clean terminal path and closes intentionally.

`V2` does not yet provide hosted todo parity.

## Behavioral Delta

Before this slice, the repo has only a local FastAPI path and Cloudflare spike prototypes. After this slice, the repo has a real hosted Cloudflare websocket path that can run a live transcript session end to end, including stop finalization and session-cap teardown, while preserving the current browser-visible transcript protocol.

The externally visible system delta is that there is now a real hosted runtime path for transcript behavior. The intentionally missing behavior is hosted todo parity.

## Decisions

- Keep the shared core in `backend/app/` for `V2` instead of paying for a packaging relocation now.
- Add the hosted runtime in a separate `cloudflare/` app boundary.
- Keep the Worker ingress thin and make the Durable Object the real session owner.
- Reuse the shared `LiveSessionController` for hosted transcript/finalization lifecycle.
- Hide Cloudflare websocket transport details behind a Cloudflare-specific Soniox `SttSession` adapter.
- Keep hosted todo behavior intentionally out of parity in this slice.

## Non-Goals

- Move the shared core into a new neutral package.
- Reach hosted todo extraction parity.
- Redesign the browser websocket protocol.
- Rework the local FastAPI path beyond narrowly required integration support.
- Add publishability/deployment documentation or deploy-button packaging.

## Design And Implementation Constraints

- Preserve browser protocol compatibility with [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts).
- Preserve the real stop contract already proven locally and in `X7`: finalize, EOS, wait for finalization, then return the finalized transcript.
- Keep the Worker front door transport-thin and the Durable Object session-owned.
- Keep Cloudflare-specific websocket mechanics inside the hosted Soniox adapter, not in the shared core.
- Enforce the hosted demo session cap server-side and close cleanly.
- Keep the local FastAPI adapter available and behaviorally intact.
- Do not let hosted todo incompleteness blur the slice boundary.

## Acceptance Gate: Hosted Transcript Session Works End To End Through The Real Cloudflare Runtime

**Why this gate matters:**
This is the core blocking outcome of `V2`. If the real hosted runtime cannot own a browser session, stream transcript updates, and return a finalized transcript on stop, then the slice has not delivered the first real Cloudflare path.

**Criteria:**

- When a browser-style client connects to the hosted `/ws` endpoint, the Cloudflare runtime accepts the session and returns the existing browser `started` message.
- While the client streams audio, the hosted runtime emits browser-compatible `transcript` messages driven by the real Soniox path rather than local stubs.
- When the client stops the session, the hosted runtime preserves the app's current stop contract: request finalization, send EOS, wait for final transcript completion/finalization, and return `stopped` with the finalized transcript.
- The hosted runtime keeps session ownership inside one Durable Object rather than splitting transcript/finalization state across the Worker and another layer.

**Proof:**

- **Setup:** Run the real Cloudflare app locally in the supported Worker + Durable Object dev runtime with valid Soniox credentials and a known PCM fixture or equivalent deterministic audio input.
- **Action:** Open a websocket session to the hosted `/ws` endpoint, send the browser `start` control, stream the test audio as browser binary frames, then send `stop`.
- **Assertions:** Verify the browser-visible message sequence includes `started`, one or more `transcript` messages, and a terminal `stopped` containing the finalized transcript; verify the stop path matches the current finalize-then-EOS contract through the hosted Soniox adapter; verify the transcript is produced by the real hosted path rather than a local fake.
- **Structural assertions:** Inspect the hosted implementation to show the Worker handles upgrade/routing only, while the Durable Object owns the session controller and transcript/finalization state.
- **Expected evidence:** command or procedure output from the local Cloudflare runtime test, the observed browser-message sequence, and code references showing the Worker/DO ownership boundary.

## Acceptance Gate: Hosted Session Cap And Teardown Are Enforced Intentionally

**Why this gate matters:**
`V2` includes session policy and teardown as a first-class hosted requirement. A transcript path that only works when stopped manually is incomplete for the public demo shape.

**Criteria:**

- When a hosted session exceeds the configured cap, the runtime terminates it server-side without requiring the browser to stop first.
- Cap expiry follows an intentional terminal path: the browser receives the appropriate terminal session message behavior for this slice, and the websocket closes cleanly instead of hanging or dying implicitly.
- Browser disconnect, manual stop, provider failure, and cap expiry all converge on an idempotent hosted cleanup path.

**Proof:**

- **Setup:** Run the local Cloudflare app with a short configured session cap.
- **Action:** Open a websocket session to the hosted `/ws` endpoint and keep it open past the cap without sending `stop`; separately exercise manual stop, browser disconnect, and a provider/relay failure path.
- **Assertions:** Verify cap expiry produces the intended terminal behavior and close path; verify repeated or competing teardown triggers do not double-close or leave the session running; verify hosted cleanup remains stable across the exercised end states.
- **Expected evidence:** local runtime logs or observed browser events from the cap-expiry session, plus targeted hosted tests or inspections proving idempotent cleanup across the teardown cases.

## Supporting Verification

- Focused hosted adapter tests for Worker routing to the Durable Object and invalid control-message handling.
- Focused hosted Soniox adapter tests or smoke checks for Cloudflare-specific outbound websocket mechanics.
- Static or structural checks that the hosted adapter depends on the shared core but does not move shared transcript/finalization logic back into Cloudflare-specific files.
- Local FastAPI regression checks only if a narrow compatibility change is required during integration.
