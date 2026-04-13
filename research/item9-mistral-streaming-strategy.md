# Mistral Realtime Streaming Strategy

Research for the Mistral live STT track. This note documents what Mistral's
realtime transcription API appears to expose today, how the documented
dual-delay example works, why that merge strategy is only a UI heuristic, and
why the first product implementation should start with a single stream instead
of dual-delay.

## What Mistral Realtime Appears To Expose

From the current realtime transcription docs and the installed `mistralai`
Python SDK in this repo:

- the model under consideration is `voxtral-mini-transcribe-realtime-2602`
- realtime transcription emits additive text deltas (`TranscriptionStreamTextDelta`)
- the stream ends with a final completion event (`TranscriptionStreamDone`)
- there is a configurable `target_streaming_delay_ms`
- the connection supports separate audio flush and end operations
- the installed SDK also includes a realtime `transcription.segment` event with
  `text`, `start`, and `end` fields

What it does **not** appear to expose in the Soniox sense:

- per-token `is_final` flags
- replaceable interim token batches
- explicit provider-native markers equivalent to Soniox `<fin>` or `<end>`

Important clarification:

- the absence claim above is based on the current official realtime docs plus
  local SDK inspection
- this is an evidence-based inference, not a proof that no such feature exists
  anywhere in Mistral's platform
- what we can say confidently is that the documented realtime integration path
  we found does not describe Soniox-style final-token or endpoint semantics

## Clarification: What "Counts Of Finalized Tokens" Means In Our Current App

When I referred to "counts of finalized tokens," I was talking about our
**current Soniox-backed app behavior**, not a Mistral capability.

Today the app works like this:

- Soniox events are translated into normalized tokens with an `is_final` flag
- the translation layer also marks whether Soniox control markers like `<end>`
  and `<fin>` were observed
- the transcript accumulator counts how many tokens in the current message are
  final
- the websocket relay uses either:
  - an endpoint boundary, or
  - a positive count of newly-final tokens
  to decide when to notify the extraction loop

In code:

- `translate_soniox_event(...)` maps raw Soniox tokens to `SttToken(..., is_final=...)`
  and detects `<end>` / `<fin>` in `backend/app/stt_soniox.py`
- `TranscriptAccumulator.apply_stt_event(...)` computes
  `final_token_count = sum(1 for token in tokens if token.is_final)` in
  `backend/app/transcript_accumulator.py`
- `ws.py` then does:
  - `if result.has_endpoint: await extraction_loop.on_endpoint()`
  - `elif result.final_token_count > 0: extraction_loop.on_tokens(...)`

So:

- `endpoint boundary` is a provider signal we currently get from Soniox
- `count of finalized tokens` is our own app-side derivative of Soniox's
  per-token `is_final` data

That mechanism is not something I have confirmed for Mistral.

## What I Confirmed From Mistral's Realtime Docs

From the official realtime transcription page:

- their basic streaming example handles `TranscriptionStreamTextDelta` and
  `TranscriptionStreamDone`
- `target_streaming_delay_ms` is the documented knob for delaying transcription
  in exchange for more context
- their dual-delay example runs two realtime streams with different delay
  values and merges them at the UI layer

What I did **not** find documented there:

- a per-token `is_final` field
- an endpoint-detection event analogous to Soniox `<end>`
- a documented "finalized token count" concept

The installed SDK reinforces that picture:

- realtime event parsing includes:
  - `transcription.text.delta`
  - `transcription.segment`
  - `transcription.done`
- I did not find event names or fields containing `is_final` or `endpoint`
  during local SDK inspection

## What `transcription.segment` Does And Does Not Tell Us Yet

The installed SDK includes a `TranscriptionStreamSegmentDelta` model with:

- `text`
- `start`
- `end`
- optional `speaker_id`

That suggests the realtime API may expose segment-level timing information.

But I have **not** found official docs saying that:

- `transcription.segment` should be treated as an endpoint signal
- segments are guaranteed to be stable or finalized
- segment emission is equivalent to Soniox's utterance-boundary behavior

So for design purposes, we should not treat `transcription.segment` as a proven
replacement for Soniox endpoint detection until we have explicit documentation
or direct empirical traces showing that behavior.

This matters because the current app relies on a real tentative/confirmed token
distinction:

- the UI renders confirmed text plus gray italic interim text
- the transcript accumulator keeps a replaceable interim tail
- the extraction loop can read that tail while the user is still speaking

Mistral does not appear to provide that same contract directly.

## Discrepancies And Their Behavioral Impact

This is the practical view: what the current Soniox implementation depends on,
what Mistral appears to expose instead, and what behavior that may block or
change.

### 1. Confirmed vs provisional tokens

**Current Soniox behavior**

- Soniox gives us per-token `is_final`
- non-final tokens are replaceable
- final tokens are append-only

**What that enables today**

- gray interim text in the UI
- a transcript accumulator with a replaceable interim tail
- a way to count newly-finalized tokens in each event

**What Mistral appears to expose**

- additive text deltas
- no documented per-token `is_final`
- no documented replaceable interim batch

**Impact**

- we cannot faithfully preserve the Soniox-style "confirmed text plus gray
  tentative tail" contract on the first Mistral path
- we also cannot reuse the current "final token count" mechanism as-is, because
  that mechanism depends on per-token finality data

**Decision for first implementation**

- render Mistral live transcript in all-confirmed style

**Confidence**

- documented discrepancy

### 2. Endpoint boundary detection

**Current Soniox behavior**

- Soniox can emit an explicit endpoint marker (`<end>`)
- the relay maps that to `has_endpoint`
- the extraction loop can trigger immediately on endpoint boundaries

**What that enables today**

- a provider signal that roughly says "an utterance boundary just happened"
- a natural moment to launch incremental extraction

**What Mistral appears to expose**

- no documented endpoint event in the realtime docs
- no documented equivalent of Soniox `<end>`

**Impact**

- we should not assume the current endpoint-triggered extraction path can be
  reused for Mistral
- Mistral likely needs a different trigger strategy for live extraction while
  recording

**Candidate replacements**

- transcript-growth thresholds
- time-based throttling
- possibly `transcription.segment` later, if verified

**Confidence**

- documented discrepancy

### 3. Final extraction on stop

**Current Soniox behavior**

- we explicitly send `finalize`
- Soniox emits a finalization marker (`<fin>`)
- we wait for that signal before running the final extraction pass
- this protects against dropping the last unfinalized tail

**What that enables today**

- a clear stop barrier: "all pending text is now committed"
- a reasoned answer to "should we run one last extraction?"

**What Mistral appears to expose**

- separate audio flush/end operations in the SDK
- a final `TranscriptionStreamDone` event
- the SDK model for `TranscriptionStreamDone` includes a final `text` field

**Impact**

- the stop barrier likely shifts from Soniox `<fin>` semantics to Mistral
  `transcription.done`
- the implementation probably should not ask "did some tokens become final?"
- it probably should ask either:
  - "did the final transcript differ from what we had before stop?", or
  - more simply, "always run one final extraction on the final transcript"

This is an important difference:

- with Soniox, the guard is tied to token finalization
- with Mistral, the guard is more naturally tied to the final full-transcript
  event

**What we still do not know**

- whether `TranscriptionStreamDone.text` is always the authoritative final full
  transcript for the session
- whether there can still be meaningful text updates after the last visible
  delta but before `done`
- whether using `done.text` as the stop source of truth is always sufficient

**Confidence**

- partially documented, partially inferred from the SDK

### 4. Segment events

**Current Soniox behavior**

- we already have an explicit endpoint concept

**What Mistral appears to expose**

- the SDK includes `transcription.segment` with `text`, `start`, and `end`

**Possible impact**

- segment events might become useful for throttling extraction or structuring
  transcript updates

**What we do not know**

- whether segments are stable
- whether they correspond to endpoint-like boundaries
- whether they are emitted consistently enough to drive product behavior

**Confidence**

- unknown behavior; SDK evidence only

## What Is Documented vs What Is Still Unknown

### Documented discrepancies

These are the differences we can state with relatively high confidence from the
official docs:

- Mistral realtime is documented around additive text deltas and a final done
  event, not around per-token finality
- Mistral documents `target_streaming_delay_ms`
- Mistral documents a dual-delay UI strategy
- Mistral realtime docs do not describe a Soniox-like endpoint marker

### SDK-backed inferences

These are not clearly described in the docs, but the installed SDK strongly
suggests them:

- realtime connections support separate audio flush and end operations
- `TranscriptionStreamDone` carries a `text` field and optional `segments`
- realtime parsing includes a `transcription.segment` event

### Open questions

These are the parts we should treat as unresolved until we test real traces:

- Is `TranscriptionStreamDone.text` always the authoritative final transcript?
- Do segment events arrive in a way that is useful for extraction triggering?
- Are segment events stable enough to act like boundaries?
- What is the right live extraction trigger for a single-stream Mistral path:
  transcript-growth thresholds, time-based throttling, or both?
- How much does `target_streaming_delay_ms` change quality and latency in
  practice?

## What The Docs Recommend For Dual Delay

Mistral documents a dual-delay pattern for balancing speed and accuracy:

- a fast stream with low `target_streaming_delay_ms`
- a slow stream with high `target_streaming_delay_ms`
- both streams receive the same audio in parallel
- the UI displays the slow transcript as the stable base
- the UI appends only the fast words that appear to be ahead of the slow stream

The documented merge logic is roughly:

1. keep `fast_full_text`
2. keep `slow_full_text`
3. split both into words
4. normalize words by lowercasing and stripping punctuation
5. run `difflib.SequenceMatcher` on the normalized word sequences
6. find the matching block that gets furthest through the slow transcript
7. treat everything in `fast` after that point as the temporary tail
8. display `slow + fast_tail`

This is a reasonable demo for live captioning. It is not the same thing as a
provider-native confirmed/unconfirmed token model.

## Why The Dual-Delay Merge Is Only A Heuristic

The documented merge is fundamentally a best-effort alignment between two full
transcripts. It does not prove that the fast tail is truly "unconfirmed text"
in the way Soniox interim tokens are unconfirmed.

What the merge can do well:

- use the slow stream as the authoritative stable prefix
- use the fast stream to show text that appears to be ahead
- avoid leaking early fast errors if there is a later clean overlap

What the merge cannot guarantee:

- that the overlap boundary is semantically correct
- that repeated words or phrases will align safely
- that punctuation or tokenization differences will not move the handoff
- that a locally messy boundary will not produce duplication or skipped words

In other words, dual-delay gives a plausible UI approximation of tentative text,
not a formal confirmation signal.

## Example Of Where The Heuristic Can Mislead

Clean case:

- `slow`: `Today is Christmas, we are going to get some presents`
- `fast`: `Today is Chris miss, we are going to get some presents for the kids`

There is still a strong later overlap:

- `we are going to get some presents`

The merged display is likely:

- stable: `Today is Christmas, we are going to get some presents`
- temporary tail: ` for the kids`

That is a good outcome.

Riskier case:

- `slow`: `Today is Christmas, we are going to get some presents`
- `fast`: `Today is Chris miss, we are going to get some pretzels presents for the kids`

Now the boundary area is messy:

- there is overlap before the boundary
- there may also be a later single-word overlap on `presents`
- the fast stream contains conflicting material near the handoff

A global diff may still decide the overlap is good enough and append
`for the kids`, even though the boundary evidence is weak. That can make the
merged output look cleaner and more certain than the underlying evidence really
supports.

For product behavior, that is a warning sign. The heuristic is useful for a
display experiment, but it should not be treated as ground truth without
evaluation.

## What We Would Do Differently If We Revisit Dual Delay

If dual-delay becomes necessary later, the merge should be more conservative
than the docs' demo:

- keep the slow stream as the only authoritative stable prefix
- derive the fast tail only from the end of the slow transcript, not from an
  arbitrary global overlap
- require a minimum contiguous suffix overlap near the handoff point
- if the overlap is weak or ambiguous, show less fast-tail text rather than
  forcing a merge
- treat merged text as a display artifact first, not the canonical transcript

That would bias toward safety over aggressiveness.

## Decision For The First Implementation

The first Mistral product integration should use **one stream, not dual-delay**.

Reasons:

- the provider seam should first prove that Mistral can run end-to-end in the
  live `/ws` path at all
- single-stream integration is materially simpler than managing two provider
  sessions, two transcript states, and a merge algorithm
- the dual-delay merge is still a heuristic and introduces product-risk before
  we have baseline evidence on quality and latency
- we do not yet know whether the difference between a low-delay and a
  high-delay Mistral stream is large enough to justify the extra complexity

So the first version should answer the simpler question:

- can a single Mistral realtime stream replace Soniox behind the existing live
  provider seam while keeping the app usable?

## Evaluation Work That Should Follow

Before considering dual-delay, we should measure the tradeoff between a
"faster" and a "slower" single Mistral stream.

Questions to answer:

- how much transcript quality improves as `target_streaming_delay_ms` increases
- how much additional latency the user sees in live transcript updates
- whether the slower stream is already accurate enough for the product
- whether the faster stream is inaccurate enough to need a dual-delay fallback
- whether stop/final transcript behavior differs materially across delay values

The likely next experiment is not "implement dual-delay." It is:

- run the same audio corpus through Mistral with at least one low-delay and one
  higher-delay configuration
- compare transcript quality and timing
- decide whether single-stream tuning is sufficient before introducing a
  dual-delay UI

## Implications For The New Item 9 Spec

The new Mistral-focused Item 9 should reflect:

- Mistral as an additive live provider alongside Soniox
- Soniox remaining the default
- first implementation using a single Mistral realtime stream
- explicit follow-up evaluation of fast-vs-slow delay settings
- deferral of dual-delay until that evaluation shows it is justified

The previous benchmark/evals Item 9 should move to Item 10.

## References

- Mistral realtime transcription docs:
  `https://docs.mistral.ai/capabilities/audio_transcription/realtime_transcription`
- Mistral model page for the realtime transcription model:
  `https://docs.mistral.ai/models/voxtral-mini-transcribe-realtime-26-02`
- Local SDK inspection in `backend/.venv`:
  - `client.audio.realtime.transcribe_stream(...)`
  - `RealtimeConnection.send_audio(...)`
  - `RealtimeConnection.flush_audio(...)`
  - `RealtimeConnection.end_audio(...)`
  - realtime event parsing includes `transcription.text.delta`,
    `transcription.segment`, and `transcription.done`
