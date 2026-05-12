# Architecture Walkthrough

This is the durable overview of how the current `voice-todos` app is put
together.

It is intentionally about stable boundaries and invariants, not about old item
numbers or branch history.

## System Shape

The user-facing flow is:

`browser mic -> same-origin /ws -> runtime adapter -> STT session -> transcript state -> todo extraction -> todo snapshots -> browser UI`

Two runtime adapters implement that flow:

- local FastAPI in [backend/app/ws.py](../../backend/app/ws.py)
- hosted Cloudflare Worker + Durable Object in
  [cloudflare/src/entry.py](../../cloudflare/src/entry.py) and
  [cloudflare/src/session_runtime.py](../../cloudflare/src/session_runtime.py)

The frontend stays runtime-agnostic and always talks to same-origin `/ws`
through [frontend/src/hooks/useTranscript.ts](../../frontend/src/hooks/useTranscript.ts).

## Browser Contract

The browser protocol is small and stable.

Control messages sent by the browser:

- `start`
- `stop`
- binary audio frames

Messages sent back by the runtime:

- `started`
- `transcript`
- `todos`
- `stopped`
- `error`

That contract is the seam that lets the same frontend work against both the
local FastAPI path and the hosted Cloudflare path.

## Runtime Adapters

The adapters own transport concerns, not the core session semantics.

### Local FastAPI

[backend/app/ws.py](../../backend/app/ws.py) accepts the browser WebSocket and
wires together:

- settings
- STT session creation
- the live-session controller
- the extraction loop
- optional session recording

### Hosted Cloudflare

[cloudflare/src/entry.py](../../cloudflare/src/entry.py) routes `/ws` upgrades
to a Durable Object. [cloudflare/src/session_runtime.py](../../cloudflare/src/session_runtime.py)
owns the hosted session actor, session-cap handling, and browser socket
adaptation.

The hosted runtime also supports a deterministic smoke-fixture path so browser
validation can exercise the real app boundary without a live microphone.

## Session Core

The main runtime-neutral session lifecycle lives in
[backend/app/live_session.py](../../backend/app/live_session.py).

`LiveSessionController` owns:

- opening the provider session
- relaying provider events
- feeding transcript updates into the accumulator
- stop-time finalization and timeout handling
- closing provider resources cleanly

The important point is that transcript correctness and stop semantics live on
the server side, not in the browser.

## Transcript Ownership

[backend/app/transcript_accumulator.py](../../backend/app/transcript_accumulator.py)
is the canonical transcript seam.

It translates provider events into:

- stable transcript text
- provisional transcript text
- full transcript text
- boundary observations such as finalization or endpoint markers

Durable invariants:

- protocol markers such as `<fin>` and `<end>` are not transcript text
- the runtime owns the canonical final transcript
- the `stopped` payload is the source of truth for the final transcript shown
  to the user

If transcript behavior changes, start here rather than in the React hook.

## STT Abstraction

[backend/app/stt.py](../../backend/app/stt.py) defines the `SttSession`
protocol plus capability flags. That protocol hides provider-specific transport
details behind a common interface:

- `send_audio`
- `request_final_transcript`
- `end_stream`
- `wait_for_final_transcript`
- `close`
- async iteration over normalized `SttEvent`s

Provider-specific normalization is shared under [shared/](../../shared):

- [shared/stt_soniox_shared.py](../../shared/stt_soniox_shared.py)
- [shared/stt_mistral_shared.py](../../shared/stt_mistral_shared.py)

Important provider differences:

- Soniox exposes explicit finalization and endpoint boundaries
- Mistral does not expose those boundaries in the same way and instead yields a
  final transcript on `transcription.done`
- the public hosted Cloudflare bundle intentionally supports only Soniox today

## Todo Extraction Model

[backend/app/extraction_loop.py](../../backend/app/extraction_loop.py) owns
when extraction runs.

It triggers background extraction when:

- the provider exposes an endpoint boundary, or
- transcript growth crosses the configured token threshold

It also owns stop-time behavior:

- wait for any in-flight extraction
- run one final extraction only if the final transcript changed
- resend the last successful todo snapshot on transcript timeout or extraction
  failure

The extraction result is snapshot-based, not patch-based. Each update is the
current best full todo list, not a stream of incremental todo mutations.

## Extraction Engine

[backend/app/extract.py](../../backend/app/extract.py) is the typed extraction
layer. It turns transcript text plus optional `previous_todos` into structured
`Todo` items.

The local runtime uses the main backend extraction path directly. The hosted
runtime keeps a small worker-specific `app.*` compatibility layer under
[cloudflare/src/app/](../../cloudflare/src/app) where the worker runtime needs
different settings, models, or extraction implementation details.

That split is a code-layout detail worth knowing:

- most core session logic still comes from `backend/app`
- Cloudflare bootstraps `backend/` imports through
  [cloudflare/src/repo_bootstrap.py](../../cloudflare/src/repo_bootstrap.py)
- `cloudflare/src/app/*` exists only for the worker-specific overrides

## Stop-Time Invariants

These are the easiest invariants to accidentally break:

- stop is a protocol boundary, not just a UI event
- the runtime must request provider finalization before ending the stream
- final transcript correctness is more important than immediate shutdown
- if finalization times out, the runtime should surface a warning and keep the
  last known todo snapshot rather than fabricate certainty

Any refactor that touches stop handling should be checked against
[docs/references/soniox.md](./soniox.md).

## Read This Next

If you are orienting in the codebase, read in this order:

1. [soniox.md](./soniox.md)
2. [2026-04-13-credential-storage-and-logfire-access.md](./2026-04-13-credential-storage-and-logfire-access.md)
3. [backend/app/live_session.py](../../backend/app/live_session.py)
4. [backend/app/transcript_accumulator.py](../../backend/app/transcript_accumulator.py)
5. [backend/app/extraction_loop.py](../../backend/app/extraction_loop.py)
6. [backend/app/ws.py](../../backend/app/ws.py)
7. [cloudflare/src/session_runtime.py](../../cloudflare/src/session_runtime.py)
8. [frontend/src/hooks/useTranscript.ts](../../frontend/src/hooks/useTranscript.ts)
