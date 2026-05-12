# Spike: Shape B Refactor Impact

## Context

Shape `B` is now a concrete session-owned Durable Object runtime candidate. The remaining shaping question is what this choice would actually do to the codebase: what can stay, what must move, and where the refactor cost concentrates.

## Goal

Identify the concrete refactor impact of choosing Shape `B`, especially whether the current app logic can stay portable while only the runtime/session boundary becomes Cloudflare-specific.

## Questions

| ID | Question |
|---|---|
| X4-Q1 | Which current modules are already runtime-neutral and can likely be kept? |
| X4-Q2 | Which modules are tightly coupled to FastAPI or Python `websockets` and would need to be rewritten or split? |
| X4-Q3 | Can Shape `B` preserve the frontend protocol and keep the browser app unchanged? |
| X4-Q4 | What is the likely size and concentration of the refactor if Shape `B` is chosen? |

## Findings

### Finding 1

The frontend contract can likely remain unchanged.

Repo evidence:

- The frontend opens a browser WebSocket at `/ws`.
- It only depends on the existing message protocol:
  - client to server: `start`, `stop`, binary audio frames
  - server to client: `started`, `transcript`, `todos`, `stopped`, `error`

Relevant code:

- [frontend/src/hooks/useTranscript.ts](../../../frontend/src/hooks/useTranscript.ts)

Impact:

- Shape `B` does not need a frontend redesign.
- If the Worker front door preserves the `/ws` endpoint and message schema, the browser app can stay unchanged or very close to unchanged.

### Finding 2

The transcript and extraction logic is already mostly runtime-neutral.

Repo evidence:

- `TranscriptAccumulator` only consumes normalized `SttEvent` values and maintains transcript state.
- `ExtractionLoop` only needs transcript access, a send callback, and an async extraction function.
- `extract_todos` is independent of FastAPI or WebSocket transport.
- `SttSession` is already expressed as a protocol.

Relevant code:

- [backend/app/stt.py](../../../backend/app/stt.py)
- [backend/app/transcript_accumulator.py](../../../backend/app/transcript_accumulator.py)
- [backend/app/extraction_loop.py](../../../backend/app/extraction_loop.py)
- [backend/app/extract.py](../../../backend/app/extract.py)

Impact:

- These modules are good candidates to remain shared and portable.
- The main business logic does not need to become Cloudflare-specific.

### Finding 3

The main refactor hotspot is `backend/app/ws.py`, because it currently mixes transport, session orchestration, and provider lifecycle in one FastAPI route.

Repo evidence:

- `websocket_endpoint()` currently does all of the following:
  - accepts the browser WebSocket
  - parses control messages
  - creates and tears down the STT session
  - owns transcript and extraction state
  - relays provider events to the browser
  - finalizes stop behavior and emits the final messages

Relevant code:

- [backend/app/ws.py](../../../backend/app/ws.py)

Impact:

- If Shape `B` is chosen, this file should be split rather than ported directly.
- The natural split is:
  - a runtime-neutral live-session controller
  - a browser transport adapter
  - a provider transport adapter

### Finding 4

The current Soniox integration is the most transport-specific backend component and would need a real rewrite for Shape `B`.

Repo evidence:

- `SonioxSession` is hard-wired to `websockets.ClientConnection`.
- `connect_soniox()` defaults to `websockets.connect`.
- `app.ws.create_stt_session()` injects `websockets.connect` into the Soniox connection path.

Relevant code:

- [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py)
- [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py)
- [backend/app/ws.py](../../../backend/app/ws.py)

Impact:

- Shape `B` requires a new outbound provider transport implementation that works in the Durable Object runtime.
- The existing `SttSession` protocol can likely stay.
- The Soniox implementation itself should be treated as a replacement module, not a small patch.

### Finding 5

The recording path is easy to drop from the hosted runtime, which reduces refactor surface.

Repo evidence:

- Session recording is isolated in `SessionRecorder`.
- The live path only touches it at session start, audio writes, provider message writes, final result write, and stop cleanup.

Relevant code:

- [backend/app/session_recorder.py](../../../backend/app/session_recorder.py)
- [backend/app/ws.py](../../../backend/app/ws.py)

Impact:

- Since hosted local-file recording is out of scope, Shape `B` can simply omit this path from the Cloudflare runtime.
- That removes one portability blocker without affecting the product behavior.

### Finding 6

The test suite currently anchors most session behavior to the FastAPI WebSocket route, so Shape `B` would benefit from moving those expectations one layer down.

Repo evidence:

- The backend test suite exercises the `/ws` route extensively through `TestClient` and FastAPI WebSocket tests.

Relevant code:

- [backend/tests/test_ws.py](../../../backend/tests/test_ws.py)

Impact:

- If Shape `B` is chosen, the highest-value test refactor is:
  - move session-behavior assertions to a shared live-session controller test surface
  - keep only thin transport tests for FastAPI or Cloudflare-specific adapters
- This would improve portability and reduce transport-coupled duplication.

## Refactor Read

If Shape `B` is chosen, the refactor impact is best described as:

- Frontend: low
- Shared business logic: low
- Session orchestration boundary: medium
- Provider transport rewrite: medium to high
- Runtime/deployment surface: medium
- Test surface: medium

## Practical Refactor Direction

The most plausible codebase shape for `B` is:

1. Keep shared modules:
   - transcript accumulation
   - extraction loop
   - extraction agent and prompts
   - STT event and session interfaces

2. Introduce a runtime-neutral live-session controller module that owns:
   - `start`
   - `on_audio`
   - `on_provider_event`
   - `stop`
   - session cleanup

3. Replace the current monolithic FastAPI route with thin adapters:
   - local FastAPI adapter for current backend and local development, if retained
   - Cloudflare Worker front door plus Durable Object adapter for hosted runtime

4. Replace the current Soniox transport implementation with a Cloudflare-compatible one while preserving the `SttSession` protocol shape.

## Conclusion

Shape `B` does not imply rewriting the whole app.

It implies:

- extracting the session controller out of the current FastAPI route
- replacing the Soniox transport layer
- adding a Cloudflare-specific session adapter layer

If that split is done cleanly, most business logic can remain portable even though the hosted session runtime is Cloudflare-specific.
