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
- preserve compatibility with the current replay evidence and transcript
  assembly path while Item 7 migration work is still in flight
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
- `ws.py`: browser orchestration plus transcript/extraction coordination, but
  not provider transport details

The exact file split can change during implementation, but the boundary should
be this clean.

### 3. Preserve replay compatibility while Item 7 is still migrating

Item 8 and Item 7 can be developed in parallel, but only if Item 8 does not
strand the current replay path.

Today replay evidence and replay helpers still use provider-native Soniox traces
and the current transcript accumulation behavior. Item 8 must therefore provide
one dedicated compatibility adapter that translates recorded Soniox traces into
the normalized app contract before transcript assembly until Item 7 replay
migration is complete.

`TranscriptAccumulator` should not stay permanently dual-wired to both raw
Soniox events and normalized app events. The production accumulator should move
toward one input contract, and replay compatibility should live in one explicit
translation seam.

What Item 8 must not do:

- force Item 7 replay work to depend on a removed raw-event contract
- duplicate Soniox control-marker parsing in multiple places
- silently change replay transcript semantics without explicit regression tests

This is a compatibility rule, not a reason to keep Soniox-specific transport
logic in `ws.py`.

### 4. Normalize provider events before they reach transcript assembly

`TranscriptAccumulator` and `ExtractionLoop` should not need to parse raw
provider payloads.

The provider adapter should translate provider-native events into one normalized
app contract. That contract should preserve the app-level semantics we actually
need, not blindly mirror Soniox's raw JSON.

The normalized event model should be able to carry:

- transcript tokens
- whether those tokens are final
- whether a finalization boundary was observed
- whether an endpoint boundary was observed
- whether the provider has finished the stream

Important constraint:

- not every provider will expose every boundary explicitly
- the normalized contract must therefore support "capability absent" and "event
  not observed" as distinct cases
- future providers must not be forced to invent fake Soniox-style markers just
  to satisfy the app contract

That means the normalized boundary fields should not be modeled as plain booleans
if booleans would collapse those states together. The contract should use an
explicit representation such as:

- an enum-like state value
- or `bool | None` with documented semantics

so the app can distinguish:

- boundary observed
- boundary not observed
- provider does not expose that boundary at all

This preserves current behavior while removing Soniox-specific JSON from the app
orchestration layer and without pretending every provider looks exactly like
Soniox.

### 5. Preserve the current stop contract explicitly

The Soniox stop sequence is not accidental. The current behavior is:

- send `finalize`
- send end-of-stream
- wait for the finalization signal
- then run the final extraction path

That ordering should be part of the provider contract rather than an incidental
detail hidden inside `ws.py`.

Future providers may implement the same app-level operations differently, but
the app should still ask for:

- request that the provider flush or finalize pending transcript state
- close/end the audio stream
- wait until the final transcript is ready for the app

### 6. Define the provider session lifecycle explicitly

Item 8 should not leave the session lifecycle implicit. The app-level contract
must define:

- when a session is considered started and ready for audio
- how the app-level "request final transcript" action maps to each provider
- whether `end_stream()` may be called after the final-transcript request and in
  what order
- what event or session signal means "final transcript ready for the app"
- what event or session signal means "provider stream is finished"
- whether repeated final-transcript requests, `end_stream()`, or `close()` calls
  are allowed and how they behave
- which layer owns stop timeouts and cancellation

Required behavior for the app contract:

- the app must have one explicit action for "make the transcript final now"
- every provider session exposed to the app must implement that action
- that action may map differently per provider:
  - explicit finalize message
  - no-op because the provider finalizes on end-of-stream
  - provider-specific flush or commit call
- `end_stream()` remains a separate app-level operation even if one provider
  internally couples it with finalization
- the app may wait for the final transcript to become ready before the stream is fully
  finished
- `finished` is not the same as "final transcript is ready"
- cleanup operations must be safe during partial failure or disconnect paths
- provider capabilities must be queryable explicitly rather than inferred from
  ad hoc runtime failures

The session contract should therefore expose provider capabilities in one clear
place, for example through:

- a capabilities object on the session
- or documented provider metadata returned alongside session construction

and it should expose one explicit way for the app to wait for the final
transcript rather than assuming that iterating until `finished` is equivalent.

The app should not need a capability check to decide whether it is allowed to
call the app-level "request final transcript" action. That action is part of
the required session contract. Provider differences should be handled inside the
adapter's implementation of that action.

For Soniox specifically, this means preserving the current:

- request final transcript via `finalize`
- end-of-stream
- wait for `<fin>`
- eventual `finished` or socket close

sequence without letting those raw markers leak back into app orchestration.

### 7. Provider selection should be explicit, but production requirements stay stable

Item 8 should introduce one explicit provider-selection seam, most likely via a
factory plus settings, but it should not make non-Soniox providers mandatory for
production startup.

That means:

- Soniox credentials remain required for the current default path
- future-provider credentials may exist as optional settings
- app startup behavior for the current Soniox deployment should remain unchanged

### 8. Keep raw session evidence provider-native for now

Recorded session evidence currently serves replay and debugging needs. Item 8
should not force that evidence to migrate formats at the same time as the
provider abstraction refactor.

For this item:

- raw recorded provider traffic may remain provider-native on disk
- Soniox recordings may continue to be stored as Soniox JSONL traces
- normalized app events may be introduced in memory without becoming the new
  canonical recorded evidence format
- the current session recording path should continue to emit Soniox JSONL for
  the Soniox provider unless a follow-up item intentionally changes that format
- Item 8 should include regression coverage that recording still produces the
  expected provider-native evidence files for Soniox:
  - `audio.pcm`
  - `soniox.jsonl`
  - `result.json`

If the repo later wants dual-format or provider-neutral evidence capture, that
should be a follow-up item with its own migration plan.

### 9. Evals stay outside the backend app

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
- Item 8 must preserve replay compatibility through one explicit Soniox-trace
  adapter while Item 7 is still migrating replay benchmarks and fixtures
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
