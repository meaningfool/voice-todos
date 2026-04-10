# Item 8 Design: STT Provider Abstraction Refactor

Scope: refactor the production STT path so `/ws` depends on an injectable
provider/session abstraction instead of Soniox-specific websocket details, while
preserving the current Soniox user-visible behavior.

## Why this exists

The current production websocket path in `backend/app/ws.py` mixes four concerns
in one place:

- browser websocket orchestration
- Soniox connection setup and transport details
- provider-specific finalization and end-of-stream ordering
- transcript/extraction flow

That works for one provider, but it makes the next STT provider harder to add
than it needs to be. Right now the app-level code knows too much about Soniox.

Item 8 exists to create a clean app-level seam before we do STT benchmark work.
It should become easy to plug in another provider without rewriting the `/ws`
flow or mixing eval concerns into backend production code.

## Goals

- preserve the current Soniox production behavior
- keep the browser `/ws` contract stable
- isolate Soniox-specific config, transport, and event translation behind an
  adapter
- define one provider-neutral app contract for streaming STT sessions
- make future provider injection explicit through a factory or settings-driven
  selection point
- keep this refactor usable by later STT eval work without putting eval code in
  `backend/app/`

## Non-goals

- building the STT benchmark harness
- defining WER, latency, or provider-comparison reporting
- creating STT datasets, manifests, or benchmark files
- choosing a new production provider in this item
- changing the todo extraction semantics
- redesigning the browser websocket API

## Current State Summary

The current Soniox-specific production behavior lives primarily in:

- `backend/app/ws.py`
- `backend/app/transcript_accumulator.py`
- `backend/app/config.py`

Important current behavior that must remain intact:

- `/ws` connects to Soniox on `start`
- audio bytes are forwarded upstream as they arrive
- `stop` sends Soniox `finalize`, then an empty frame to close the stream
- the backend waits for the transcript finalization signal before running the
  final extraction pass
- endpoint and finalization semantics still drive the same extraction behavior

## Design Decisions

### 1. Keep Soniox as the default production provider

This item is a refactor, not a provider migration.

The default production configuration remains Soniox, with the same model and the
same stop/finalization sequence already encoded in `backend/app/ws.py`.

### 2. Introduce a provider-neutral STT session boundary in `backend/app/`

Production app code should depend on a small app-level STT contract rather than
provider-specific websocket messages.

Target shape:

```text
backend/app/
  stt.py
  stt_factory.py
  stt_soniox.py
  ws.py
  transcript_accumulator.py
```

Responsibilities:

- `stt.py`: provider-neutral session protocol and normalized event/result types
- `stt_factory.py`: construct the configured provider
- `stt_soniox.py`: Soniox-specific connection setup, config payload, finalize
  ordering, and event translation
- `ws.py`: browser orchestration only

The exact file split can change during implementation, but the boundary should
be this clean.

### 3. Normalize provider events before they reach transcript assembly

`TranscriptAccumulator` and `ExtractionLoop` should not need to parse raw
provider payloads.

The provider adapter should translate provider-native events into one normalized
app contract that carries:

- transcript tokens
- whether those tokens are final
- whether a finalization marker was observed
- whether an endpoint marker was observed
- whether the provider has finished the stream

This preserves current behavior while removing Soniox-specific JSON from the app
orchestration layer.

### 4. Preserve the current stop contract explicitly

The Soniox stop sequence is not accidental. The current behavior is:

- send `finalize`
- send end-of-stream
- wait for the finalization signal
- then run the final extraction path

That ordering should be part of the provider contract rather than an incidental
detail hidden inside `ws.py`.

Future providers may implement the same app-level operations differently, but
the app should still ask for:

- finalize pending transcript state
- close/end the audio stream
- wait for the provider's final transcript boundary

### 5. Provider selection should be explicit, but production requirements stay stable

Item 8 should introduce one explicit provider-selection seam, most likely via a
factory plus settings, but it should not make non-Soniox providers mandatory for
production startup.

That means:

- Soniox credentials remain required for the current default path
- future-provider credentials may exist as optional settings
- app startup behavior for the current Soniox deployment should remain unchanged

### 6. Evals stay outside the backend app

Item 7 already defines the architectural rule:

- `evals` may depend on `backend/app`
- `backend/app` must not depend on `evals`

Item 8 should reinforce that split. This refactor exists partly so a later STT
benchmark can call into a clean production-adjacent abstraction without dragging
benchmark concerns into `backend/app/`.

## Relationship To Item 7 And Item 9

- Item 7 defines the benchmark-first eval architecture and top-level `evals/`
  boundary
- Item 8 prepares the production STT code so multiple providers can be injected
  cleanly
- Item 9 will define the dedicated STT benchmark work on top of the Item 7
  eval structure and the Item 8 abstraction seam

## Expected Next Deliverables

- an implementation plan for the backend refactor
- a clear factory/provider boundary in `backend/app/`
- Soniox adapter tests that lock the current behavior
- a new Item 9 spec for the STT benchmark itself

## References

- `backend/app/ws.py`
- `backend/app/transcript_accumulator.py`
- `backend/tests/test_ws.py`
- `backend/tests/test_soniox_integration.py`
- `docs/references/soniox.md`
- `docs/superpowers/specs/2026-04-10-item7-evals-restructure-design.md`
