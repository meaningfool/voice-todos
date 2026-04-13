# Item 9 Design: Voxtral Realtime Semantics Spike

Scope: run a focused discovery spike against Mistral's realtime transcription
model `voxtral-mini-transcribe-realtime-2602` so we can determine how its live
stream semantics map to the current STT seam from Item 8 and what follow-on
specs are needed before product integration.

## Why this exists

Item 8 created the provider/session seam needed to add a second live STT
provider. But the app behavior above that seam still carries Soniox-shaped
assumptions:

- per-token `is_final`
- replaceable interim text
- endpoint markers
- a stop path tied to token finalization

The current Mistral docs and local SDK inspection are enough to show likely
differences, but not enough to confidently answer whether the seam is already in
the right shape for Voxtral or which app behaviors need to change.

If we skip this spike and go straight to implementation, we risk building
against the wrong abstraction:

- forcing fake finality semantics into the adapter
- choosing the wrong live extraction trigger
- misunderstanding the stop barrier
- over-committing to dual-delay before single-stream behavior is measured

This item exists to replace inference with evidence.

## Roadmap Change

- New `Item 9` becomes this Voxtral realtime semantics spike
- The previous STT benchmark/evals spec moves to `Item 10`
- Follow-on Voxtral integration work should be written as `Item 9.1`, `Item 9.2`,
  and so on, based on the spike results

## Goals

- collect real provider-native Voxtral realtime traces from existing fixture
  audio
- map current Soniox-dependent behaviors to:
  - directly reproducible with Voxtral
  - reproducible through different app logic
  - currently unsupported or unclear
- verify the realtime stop sequence and determine the authoritative stop-time
  transcript source of truth
- measure how `target_streaming_delay_ms` affects transcript quality and timing
  for a small but representative fixture set
- produce a seam-assessment table that says which current abstractions fit, need
  reshaping, or remain unresolved
- produce concrete answers needed to write `Item 9.1`

## Non-goals

- shipping Voxtral as a selectable provider in `/ws`
- implementing a dual-delay live UI
- preserving Soniox's confirmed/interim UI model on this item
- redesigning the browser websocket contract
- building the benchmark-first STT eval harness from the previous Item 9
- deciding final production rollout or default-provider policy

## Approved Context

- Soniox remains the default live STT provider
- any future Voxtral product path is additive, not a migration in this phase
- the first likely product direction after the spike is single-stream Voxtral
  with configurable `target_streaming_delay_ms`
- dual-delay is explicitly deferred until single-stream quality and latency are
  measured

## Core Questions This Spike Must Answer

### 1. Session lifecycle and stop semantics

- What realtime events does Voxtral emit from connection start through stream
  end?
- What is the observable sequence around audio flush, audio end, and final
  completion?
- Is `TranscriptionStreamDone.text` the authoritative final full transcript for
  the session?
- Can meaningful text changes still appear after the last visible text delta and
  before `done`?

### 2. Transcript semantics

- Are realtime text updates purely additive, or is there any evidence of
  correction behavior?
- Does the provider expose anything that could substitute for Soniox
  per-token-finality?
- Does the provider expose anything that could substitute for Soniox endpoint
  boundaries?
- What does the undocumented-but-present `transcription.segment` event actually
  look like in real traces?

### 3. Extraction-trigger feasibility

- Which current live extraction triggers survive the move away from Soniox?
- If endpoint markers are absent, what alternative trigger strategy looks viable
  from the traces:
  - transcript-growth thresholds
  - time-based throttling
  - segment-driven triggers
  - some combination

### 4. Delay sensitivity

- How much does `target_streaming_delay_ms` change:
  - first visible transcript latency
  - transcript update cadence
  - final latency
  - transcript quality
- Is single-stream tuning likely enough, or does the evidence justify a later
  dual-delay design?

### 5. Seam assessment

- Which parts of the Item 8 seam are already in the right place?
- Which parts are too Soniox-shaped?
- Which changes belong in the provider adapter versus the app-level transcript
  and extraction layers?

## Design Decisions

### 1. The spike should record provider-native traces first

The spike must preserve Voxtral's native realtime events rather than only a
normalized `SttEvent` view.

Why:

- we are trying to learn the provider's semantics
- if we only keep normalized events, we may accidentally erase exactly the
  differences we need to study
- later adapter design should be derived from those traces, not the other way
  around

The raw trace format should be JSON Lines and should preserve:

- local receive timestamp
- provider event type
- raw payload
- run metadata such as fixture, delay profile, and model

### 2. The spike should use prerecorded fixture audio, not the browser path

This item is about realtime semantics, not browser integration.

Use existing fixture audio under `backend/tests/fixtures/` so runs are:

- reproducible
- comparable across delay settings
- independent of microphone and browser noise

Initial fixture set should stay small but representative. At minimum include:

- one short stop-sensitive utterance
- one continuous-speech case
- one multi-todo / while-speaking case
- one longer memo-style case

Recommended starting fixtures:

- `stop-the-button`
- `continuous-speech`
- `while-speaking-two-todos`
- `call-mom-memo-supplier`

### 3. The spike should compare a small delay matrix, not just one run

The spike should not only verify that Voxtral works. It should also answer
whether single-stream delay tuning is sufficient to justify deferring
dual-delay.

Minimum matrix:

- provider default delay
- a fast explicit delay based on the docs' dual-delay example: `240ms`
- a slow explicit delay based on the docs' dual-delay example: `2400ms`

If runtime or cost becomes an issue, reduce fixture count before reducing the
delay matrix.

### 4. The spike should produce both traces and a behavior-mapping summary

Raw traces alone are not enough. The item should end with a compact summary that
maps behavior to consequences for the seam.

Required output table shape:

| Behavior | Soniox mechanism today | Voxtral evidence | Reproducible as-is? | Different implementation? | Unknown? |
|---|---|---|---|---|---|

This is the main artifact the follow-on spec will consume.

### 5. The spike should measure stop-time transcript authority explicitly

One specific risk must be answered directly: what event should gate the final
extraction pass in a future Voxtral integration?

The spike should therefore capture and compare:

- transcript visible before stop
- transcript at the last visible delta before completion
- transcript inside `TranscriptionStreamDone.text`
- whether those differ

This determines whether a future integration should:

- always trust `done.text`
- trust the accumulated streaming text
- or reconcile both

### 6. Segment events are in scope to observe, not to trust

The installed SDK includes a `transcription.segment` event type, but the current
docs do not explain it as an endpoint or finalization signal.

This item should:

- record those events if they appear
- describe their observed cadence and payload shape
- explicitly avoid treating them as a replacement for Soniox endpoint markers
  unless the evidence is strong

### 7. The spike should end with a recommendation, not a full integration design

The item's conclusion should answer:

- Is the current session seam good enough for Voxtral transport and stop
  lifecycle?
- What transcript/extraction assumptions above the seam need to change?
- Should `Item 9.1` target a single-stream live integration?
- Is dual-delay justified now, or should it stay deferred?

That recommendation is the handoff into the next spec, not a substitute for it.

## Expected Implementation Shape

The exact filenames may vary slightly, but the spike should roughly produce:

```text
scripts/
  mistral_realtime_probe.py

backend/tests/fixtures/
  <fixture>/
    mistral/
      provider_default.jsonl
      fast_240ms.jsonl
      slow_2400ms.jsonl

docs/references/
  2026-04-13-item9-voxtral-realtime-spike-findings.md
```

Optional additive artifacts:

- compact per-run summary JSON with timing and final transcript metadata
- a small analysis helper for diffing transcripts or summarizing event types

## Artifact Requirements

### Raw trace artifact

Each run should preserve provider-native events as JSONL with enough metadata to
replay the reasoning later.

Minimum fields per line:

- local monotonic receive time or elapsed milliseconds
- provider event type
- raw event payload

### Findings document

The findings document should answer the spike questions directly and include:

- the behavior-mapping table
- the stop-semantics conclusion
- the observed role, if any, of `transcription.segment`
- a short recommendation for `Item 9.1`

### Source-of-truth note

The current research note
`research/item9-mistral-streaming-strategy.md` should remain the background
reasoning doc. The findings document should capture what the spike proved.

## Success Criteria

This item is complete when all of the following are true:

- we have real Voxtral traces for the selected fixtures and delay profiles
- the stop path has a documented, evidence-backed conclusion
- the behavior-mapping table clearly separates:
  - reproducible as-is
  - reproducible differently
  - still unknown
- we can say whether the current seam is:
  - sufficient at the session lifecycle layer
  - insufficient at the transcript semantics layer
  - or unclear in specific areas
- we have enough evidence to write `Item 9.1` without relying on broad
  inference from docs alone

## Relationship To Item 10

The STT benchmark/evals track remains important, but it should follow this
spike, not precede it.

Why:

- the spike clarifies what Voxtral actually exposes in realtime
- Item 10 can then benchmark Voxtral with a more accurate understanding of its
  capability notes and runtime behavior
- the product integration and the benchmark track will both rely on the same
  evidence base rather than two separate assumptions about the provider

## Expected Next Deliverables

- `Item 9.1`: single-stream Voxtral live integration design
- optionally `Item 9.2`: focused follow-up if the spike reveals unresolved
  segment or stop-path ambiguity
- `Item 10`: renumbered STT benchmark/evals track

## References

- `research/item9-mistral-streaming-strategy.md`
- `docs/superpowers/specs/2026-04-10-item8-stt-provider-abstraction-design.md`
- Mistral realtime transcription docs:
  `https://docs.mistral.ai/capabilities/audio_transcription/realtime_transcription`
- Mistral model page:
  `https://docs.mistral.ai/models/voxtral-mini-transcribe-realtime-26-02`
- `backend/tests/fixtures/`
