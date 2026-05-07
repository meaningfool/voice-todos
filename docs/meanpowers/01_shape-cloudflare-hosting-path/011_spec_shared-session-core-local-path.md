# Spec: Shared Session Core In The Local Path

## Source

- Shaping document: [010_shaping_shape-cloudflare-hosting-path.md](./010_shaping_shape-cloudflare-hosting-path.md)
- Shaping slice: `V1`
- Scope: shared session, transcript, and finalization core in the existing local path

## Baseline

The current local app runs the live voice-todo session through [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py). That route currently accepts the browser WebSocket, parses `start` and `stop`, opens the STT session, forwards audio, relays transcript events, coordinates stop finalization, runs todo extraction, sends todo snapshots, and performs cleanup.

The browser contract is consumed by [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts) and expects `started`, `transcript`, `todos`, `stopped`, and `error` messages over `/ws`.

Some core pieces are already runtime-neutral:

- [backend/app/stt.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt.py)
- [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/transcript_accumulator.py)
- [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extraction_loop.py)

But the current session lifecycle is still centered in the FastAPI adapter, which leaves no clean shared seam for the later Cloudflare runtime.

## Target System

After this slice, the local FastAPI `/ws` path still supports the same end-to-end live voice workflow, but session, transcript, and finalization control no longer live primarily inside the FastAPI route.

A new shared live session controller owns:

- STT session lifecycle
- audio forwarding to the active `SttSession`
- transcript accumulation from normalized STT events
- provider-neutral stop coordination and cleanup
- final transcript resolution, including provider-supplied `final_transcript_text` when available

The FastAPI `/ws` route becomes a thin local adapter that owns:

- browser WebSocket accept/read/write
- JSON control parsing and browser message formatting
- local todo extraction orchestration via `ExtractionLoop`
- optional session recording
- user-facing warning strings and todo fallback behavior

The local browser-visible contract stays unchanged. The frontend still connects to `/ws`, still sends `start`, `stop`, and binary audio frames, and still receives the same message types in the same meaningful order.

## Architecture

The new boundary is a shared live session controller extracted from [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py).

The controller is runtime-neutral and depends on the existing provider seam:

- `create_stt_session`
- `SttSession`
- `TranscriptAccumulator`

The controller does not know about FastAPI request handling, browser WebSocket classes, todo extraction policy, or session recording. It exposes controller-level outcomes and transcript/update callbacks that the local adapter maps into the existing browser protocol.

The FastAPI adapter keeps local-only concerns:

- browser protocol parsing and formatting
- ordering of `todos` relative to `stopped`
- `ExtractionLoop`
- session recording

This keeps `V1` narrow and creates the session seam needed for the later Cloudflare adapter without prematurely pulling todo orchestration into shared code.

## Components

### Shared Live Session Controller

The controller owns:

- `start`
- audio forwarding
- STT relay consumption
- transcript state
- stop/finalization coordination
- cleanup

It depends on an injected STT-session factory rather than on FastAPI or direct `websockets` transport calls.

### Shared Stop Result

The controller returns a stop result that includes the final transcript text and controller-level stop outcome, including timeout when applicable. The adapter remains responsible for converting that into the current user-facing warning text.

### FastAPI `/ws` Adapter

The FastAPI adapter remains the local integration boundary. It:

- accepts the browser socket
- parses `start`, `stop`, and invalid control input
- sends browser `started`, `transcript`, `todos`, `stopped`, and `error` messages
- owns local extraction-loop triggering and todo snapshot sending
- owns optional session recording

### Provider Seam

`create_stt_session` and `SttSession` remain the provider seam for this slice. `V1` preserves that seam rather than redesigning provider selection or transport shape.

## Data Flow

1. The browser sends `start` to the FastAPI `/ws` adapter.
2. The adapter creates the shared controller, injects the configured `create_stt_session` factory, wires controller callbacks to browser transcript sends, and starts the local `ExtractionLoop`.
3. Audio frames still enter through the FastAPI WebSocket. The adapter passes raw audio bytes to the controller, and the controller forwards them through the active `SttSession`.
4. As provider events arrive, the controller updates transcript state and emits normalized transcript updates back to the adapter. The adapter turns those into existing browser `transcript` messages and separately triggers the local todo loop on transcript-change and endpoint signals.
5. On `stop`, the adapter asks the controller to stop. The controller preserves the current provider-neutral sequence: request final transcript, send end-of-stream, wait for either the provider's final transcript completion or the observed finalization boundary, then return the final transcript text and stop status.
6. After the controller returns, the adapter runs the same local final todo behavior it has today: do the final extraction pass if needed, fall back to the latest todo snapshot if no new final pass ran, then send `stopped`.

Todo timing decisions remain outside the controller in `V1`. The controller owns transcript and finalization truth, while the adapter still owns when `todos` messages are sent and in what order relative to `stopped`.

## Behavioral Delta

Before this slice, the local live session flow is implemented mostly inside the FastAPI route. After this slice, the same local flow runs through a shared controller boundary that later runtimes can reuse.

The intended externally visible change is none. The intended internal change is that the local adapter now depends on a reusable session controller instead of directly owning session orchestration.

## Decisions

- Keep `V1` narrow: only shared session, transcript, and finalization core move behind the new boundary.
- Leave todo extraction orchestration in the FastAPI adapter for this slice.
- Preserve `create_stt_session` and `SttSession` as the provider seam.
- Treat stop timeout as a controller stop outcome, while keeping user-facing warning text in the adapter.
- Keep session recording local-only and optional.

## Non-Goals

- Add Cloudflare Worker or Durable Object runtime code.
- Move todo extraction orchestration into shared code.
- Change the browser `/ws` protocol.
- Rewrite STT provider transport implementations.
- Add deploy-path or packaging work.

## Design And Implementation Constraints

- Preserve the `/ws` contract consumed by [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts).
- Preserve current stop semantics, including finalize-before-EOS ordering.
- Preserve use of provider-supplied `final_transcript_text` when available.
- Keep the shared controller free of FastAPI, browser WebSocket, and local todo/recording dependencies.
- Keep cleanup idempotent across disconnect, failed start, relay failure, timeout, and normal stop.

## Acceptance Gate: Local Live Session Workflow Is Preserved Through The Shared Controller Boundary

**Why this gate matters:**
This slice is only complete if the local browser workflow still behaves the same while the session lifecycle has actually moved behind a reusable shared boundary. Either half failing makes the slice incomplete.

**Criteria:**

- When the local browser client starts a session over `/ws`, the system still returns `started` and streams transcript token updates using the existing browser message contract.
- When the local browser client stops a session, the system still requests provider finalization before end-of-stream, resolves the final transcript using the current finalization rules, sends todo output before `stopped`, and preserves the current warning behavior for timeout and final extraction failure.
- When the configured provider exposes `final_transcript_text`, the stop path still uses that text for the final transcript payload and final extraction input.
- The local FastAPI adapter depends on a shared live session controller boundary, and the shared controller does not import FastAPI, browser WebSocket types, `ExtractionLoop`, or session-recording modules.

**Proof:**

- **Setup:** Run backend integration tests against the existing FastAPI app with fake `SttSession` implementations that cover normal transcript streaming, provider final transcript override, stop timeout, and final extraction failure.
- **Action:** Drive the `/ws` route through `start`, transcript relay, binary audio frames where relevant, and `stop`.
- **Assertions:** Verify `started` is sent, transcript messages stream in order, stop triggers finalize before EOS, final transcript output matches the current rules, todo messages are sent before `stopped`, timeout and extraction-failure warnings match the current contract, and provider final transcript override is preserved.
- **Structural assertions:** Inspect the code boundary to show the FastAPI route uses the shared controller interface and the shared controller module does not import FastAPI, browser WebSocket types, local todo orchestration, or recording code.
- **Evidence:** Named integration tests covering the preserved `/ws` contract, their asserted ordering and payload expectations, and code references showing the new controller boundary and forbidden dependency absence.

## Supporting Verification

- Focused controller unit tests for stop coordination, including:
  - finalization boundary observed before provider completion
  - provider completion without finalization boundary
  - timeout outcome
  - idempotent cleanup after relay failure or disconnect
- Focused adapter tests for invalid JSON and unknown control-message handling if they need adjustment during the refactor.
- Static type and targeted test pass for the touched backend modules.
