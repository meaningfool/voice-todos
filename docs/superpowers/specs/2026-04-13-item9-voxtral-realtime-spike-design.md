# Item 9 Design: Voxtral Realtime Semantics Spike

Scope: run a short discovery spike against Mistral's realtime transcription
model `voxtral-mini-transcribe-realtime-2602` to determine whether the current
STT seam from Item 8 is in the right place for a Voxtral adapter, and where the
current Soniox-shaped assumptions above that seam need to change.

## Why this exists

Item 8 created the provider/session seam, but the current live path still
assumes Soniox-style behavior:

- per-token finality
- replaceable interim text
- endpoint markers
- a stop path tied to Soniox finalization semantics

The docs and SDK suggest Voxtral differs, but that is not enough to design the
adapter with confidence. This spike exists to replace that uncertainty with real
trace evidence.

## Roadmap Change

- Item 9 becomes this spike
- the previous STT benchmark/evals spec is now Item 10
- follow-on Voxtral integration work should start at Item 9.1

## Goals

- capture real Voxtral realtime traces from prerecorded fixture audio
- verify Voxtral session lifecycle and stop semantics
- verify what transcript semantics Voxtral actually exposes in practice
- map the current seam into:
  - fits as-is
  - fits, but needs different app logic above the seam
  - unclear or unsupported
- produce the minimum findings needed to write Item 9.1

## Non-goals

- shipping Voxtral in `/ws`
- designing a new extraction trigger strategy
- evaluating delay tuning or dual-delay
- benchmarking providers
- redesigning the browser websocket API

## Core Questions

### 1. Session lifecycle and stop semantics

- What events does Voxtral emit from connection start to stream completion?
- What is the observable sequence around flush, end, and completion?
- Is `TranscriptionStreamDone.text` the authoritative final transcript?
- Can the final transcript differ from the last visible streaming text?

### 2. Transcript semantics

- Are text updates purely additive, or is there evidence of correction?
- Is there any provider-native replacement for:
  - per-token finality
  - replaceable interim text
  - endpoint markers
- What does `transcription.segment` look like in real traces, if it appears?

### 3. Seam assessment

- Which parts of the Item 8 seam already fit Voxtral?
- Which parts are too Soniox-shaped?
- Which changes belong in the adapter versus the app-level transcript/extraction
  logic?

## Design Decisions

### 1. Use prerecorded fixtures, not the browser path

This spike is about provider semantics, not browser integration.

Use a small set of existing fixture audio so runs are reproducible and easy to
compare. Start with a few representative fixtures, not the whole corpus.

### 2. Record provider-native traces

The spike must preserve raw Voxtral realtime events. Do not normalize away the
differences first.

Each trace should preserve at least:

- local receive timing
- provider event type
- raw payload
- run metadata such as fixture and model

### 3. Observe `transcription.segment`, but do not trust it yet

If segment events appear, record them and describe them. Do not assume they are
equivalent to endpoint or finalization semantics unless the evidence clearly
shows that.

### 4. Keep the output short and decision-oriented

The spike should end with:

- raw trace artifacts
- one short findings note
- one seam-mapping table

Required table shape:

| Behavior | Soniox today | Voxtral evidence | Fit status | Note |
|---|---|---|---|---|

`Fit status` should be one of:

- `fits as-is`
- `fits with different app logic`
- `unclear`
- `unsupported`

## Expected Artifacts

```text
scripts/
  mistral_realtime_probe.py

backend/tests/fixtures/
  <fixture>/
    mistral/
      trace.jsonl

docs/references/
  2026-04-13-item9-voxtral-realtime-spike-findings.md
```

Exact filenames can vary, but the spike must preserve the raw traces and a short
written conclusion.

## Success Criteria

This item is complete when:

- we have real Voxtral traces from prerecorded audio
- the stop path has an evidence-backed conclusion
- we know whether `TranscriptionStreamDone.text` should be the future stop-time
  transcript source of truth
- we have a short seam-mapping table that separates:
  - fits as-is
  - fits with different app logic
  - unclear
  - unsupported
- we have enough evidence to write Item 9.1 without relying mainly on doc
  inference

## Expected Next Deliverable

- Item 9.1: single-stream Voxtral integration design, written from the spike
  findings

## References

- `research/item9-mistral-streaming-strategy.md`
- `docs/superpowers/specs/2026-04-10-item8-stt-provider-abstraction-design.md`
- Mistral realtime transcription docs:
  `https://docs.mistral.ai/capabilities/audio_transcription/realtime_transcription`
- Mistral model page:
  `https://docs.mistral.ai/models/voxtral-mini-transcribe-realtime-26-02`
