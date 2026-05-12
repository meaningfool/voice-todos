# Deep Dive: The Later Architectural Recommendations Behind Item 2.5 and Item 3

This document is intentionally narrow.

It does not try to summarize the whole project. It focuses on the later architectural recommendations that were introduced in:

- item 2.5 hardening: commit `96cb58e`
- the refinement pass on the item 3 spec: commit `3323d46`
- the item 3 implementation plan: commit `fce1e64`

That scope is deliberate. Those are the places where the architecture was not just extended, but corrected and tightened.

## Method and Limits

I cannot directly open prior chat threads from this environment. The strongest evidence I have is the repo itself:

- the item 2.5 spec
- the original item 3 spec versus the refined item 3 spec
- the item 3 implementation plan
- the runtime code those docs shaped

So when this document says "the later recommendation was X," it means:

- X appears in the later spec or plan
- X materially differs from the earlier framing
- X explains a meaningful runtime or architectural boundary that matters today

## The Short Version

The most important later recommendations were not "add more features."

They were:

1. turn reliability into an explicit architectural concern rather than post-hoc cleanup
2. move transcript correctness into one shared backend seam
3. make degraded stop behavior explicit in the protocol instead of silent
4. ground extraction in real time context and typed outputs
5. redefine incremental todo extraction as snapshot replacement, not stable identity
6. redefine stop as a concurrency boundary with one guaranteed final finalized pass
7. make deterministic tests the primary confidence mechanism, with live-vendor tests as secondary

The rest of this document explains those recommendations in depth.

## Part I: What Item 2.5 Was Really Doing

The item 2.5 spec looks like a hardening pass, but architecturally it was more than that. It changed what the system was allowed to assume.

Before item 2.5, the app already worked. The problem was that several parts of the design were still too optimistic:

- they assumed the runtime would degrade cleanly
- they assumed tests that duplicated logic were good enough
- they assumed model output that looked structured was structured enough
- they assumed frontend resource cleanup could stay implicit

Item 2.5 replaced those assumptions with explicit invariants.

### Recommendation 1: Treat hardening as architecture, not polish

This is the most important frame to keep in mind when reading item 2.5.

The spec is not saying "the feature is done, now let us tidy up." It is saying:

- the first working version exposed real architectural risks
- those risks are part of the design, not noise around the design

That matters because without this framing, later contributors tend to deprioritize the exact parts that keep the system honest:

- failure surfacing
- typed boundaries
- cleanup discipline
- test trustworthiness

In other words, item 2.5 is where the project stopped treating correctness as an implementation detail.

### Recommendation 2: Stop using eager global settings; make runtime controls explicit

Item 2.5 replaced module-level eager settings with `get_settings()`, and added:

- `record_sessions`
- `soniox_stop_timeout_seconds`

At first glance that can look minor, but the design intent is important.

The earlier shape effectively blurred three concerns together:

- environment loading
- runtime policy
- test setup

The later recommendation separated them.

Why this mattered:

- tests need to override runtime behavior deterministically
- session recording should be a policy choice, not an always-on side effect
- stop timeout is not a magic constant; it is a runtime control that defines degradation behavior

Architectural consequence:

- the runtime becomes configurable at the seam where policy actually belongs
- hardening features become predictable under tests
- privacy-sensitive behavior can be turned on deliberately instead of happening by default

This is the difference between "the app has options" and "the runtime has explicit operational policy."

### Recommendation 3: Make session recording opt-in, because debugging tooling is also product behavior

This recommendation is easy to understate.

The earlier system wrote raw mic audio, Soniox traffic, and extracted results to disk by default. That was useful for debugging, but it was also a silent privacy and operational choice.

The item 2.5 recommendation was:

- recording should not be the default
- recording is a debugging mode
- debugging mode must be explicit

Why this mattered architecturally:

- audio capture is not harmless incidental logging
- debug observability should not silently become baseline product behavior
- local persistence changes the trust boundary of the app

The deeper lesson is that debugging affordances are not neutral. If a tool captures sensitive artifacts, its default matters architecturally, not just ergonomically.

### Recommendation 4: Move transcript assembly into a shared runtime module

This is one of the strongest recommendations in item 2.5.

The later spec introduced `TranscriptAccumulator` as a dedicated module responsible for:

- final token accumulation
- interim token replacement
- `<fin>` handling
- final transcript assembly

That was a direct response to a deeper problem: transcript logic existed in more than one place, and replay tests were green partly because they reimplemented logic instead of exercising the production path.

Why this mattered:

- transcript assembly is not trivial string glue
- it contains protocol semantics
- it is exactly the kind of logic that drifts if tests and runtime diverge

What the recommendation changed:

- transcript logic became a first-class seam
- replay tests were required to use production accumulation behavior
- future transcript changes had a single ownership point

This recommendation is important because it is really about truth ownership.

Before item 2.5, the system had more than one place that could claim to know how the transcript should be assembled.

After item 2.5, that answer became:

- the backend accumulator owns transcript assembly
- tests must defer to that same path

That is a major architectural clarification.

### Recommendation 5: Stop treating stop-time degradation as invisible

This is another core item 2.5 recommendation.

The later spec explicitly says that if finalize times out or extraction fails:

- the system must still complete the stop flow
- the user must receive a `warning`
- degradation must be surfaced instead of hidden

That recommendation introduced an important protocol idea:

- `stopped` is no longer just a lifecycle event
- it is also the place where the backend can tell the frontend whether completion was degraded

Why this mattered:

- before this, a degraded stop path could look like a normal finish
- silent degradation is especially dangerous in voice systems because users cannot easily see what was lost
- hiding the problem encourages downstream components to act as if the data is reliable

Architectural consequence:

- the protocol becomes honest about quality, not just state
- the frontend can present failure without inventing its own heuristics
- stop completion becomes explicit even under partial failure

This is a subtle but important shift:

- the system no longer treats "we returned control to the UI" as equivalent to "the result is trustworthy"

### Recommendation 6: Put explicit time context into extraction input

Item 2.5 added `_build_extraction_input()` and required extraction to include:

- current local datetime
- current local date
- current timezone

This was not prompt ornamentation. It was an architectural correction.

Without this, the system was asking the model to resolve phrases like:

- tomorrow
- next Friday
- tonight

without actually defining the temporal frame of reference.

Why this mattered:

- relative dates are underspecified without context
- if the model infers them from invisible runtime state, the system is non-deterministic
- tests cannot confidently validate date extraction if the reference frame is implicit

Architectural consequence:

- extraction becomes anchored to explicit runtime context
- tests can assert behavior with real reference datetimes
- the system stops pretending that vague temporal resolution is "close enough"

This is one of the more important later recommendations because it is exactly the kind of thing that seems fine in demos and then becomes a source of quietly wrong structured data.

### Recommendation 7: Make the schema actually typed at the boundary

Item 2.5 changed the `Todo` model so that:

- `due_date` is `date | None`
- `notification` is `datetime | None`

The significance of this is architectural, not cosmetic.

Before that change, the backend was effectively willing to accept "anything string-like that looks structured enough" as valid output.

The recommendation corrected that by saying:

- structured extraction is only structured if the boundary enforces the structure

Why this mattered:

- stringly typed dates make downstream correctness look stronger than it is
- the model boundary is the right place to reject malformed temporal output
- UI serialization can still remain simple by dumping JSON ISO strings after validation

Architectural consequence:

- the model layer becomes a real contract rather than a polite suggestion
- validation failures become visible earlier
- the frontend gets normalized output without having to become the validator

This recommendation was important because it prevented the backend from laundering ambiguous model text into apparently trustworthy task metadata.

### Recommendation 8: Treat frontend resource cleanup as one lifecycle system

One of the quieter but more important item 2.5 recommendations was the refactor of `useTranscript()` around centralized cleanup.

The spec calls out all the browser resources in play:

- `WebSocket`
- `MediaStream`
- `MediaRecorder`
- `AudioContext`
- `AudioWorkletNode`
- blob URLs
- stop timers

The recommendation was not just "clean up more carefully." It was:

- these resources form one session lifecycle
- they should be managed by one teardown path

Why this mattered:

- fragmented cleanup creates partial shutdown states
- partial shutdown states are exactly where double-stop, stale blob URLs, and leaked tracks come from
- browser media/resource bugs are often lifecycle bugs, not rendering bugs

Architectural consequence:

- the hook becomes the owner of session teardown semantics
- lifecycle behavior becomes testable at the hook level
- resource cleanup stops being spread across ad hoc callbacks

This recommendation matters because it acknowledges that for this app, the frontend is not "just a view." It is an active participant in a real-time audio session with non-trivial resource ownership.

### Recommendation 9: Make deterministic tests the primary trust source

This may be the single most important testing recommendation introduced in item 2.5 and carried into item 3.

The spec explicitly moved confidence toward:

- deterministic mocked tests
- replay tests through production logic
- hook-level tests

and away from:

- default reliance on live Gemini
- default reliance on live Soniox

Why this mattered:

- live-vendor tests are useful, but they are expensive, flaky, and not suitable as the baseline CI contract
- duplicated test logic can produce false confidence
- if a test suite only passes when external services behave perfectly, it stops being a reliable engineering tool

Architectural consequence:

- there is a layered trust model
- deterministic tests prove the software’s own invariants
- live integration checks are opt-in validation of the external pipeline, not the default definition of correctness

This recommendation is easy to miss because it sounds like test strategy. In reality it defines what the team considers trustworthy evidence.

That is an architectural decision.

## Part II: What Changed In The Refined Item 3 Spec

The refined item 3 spec is where several important assumptions were corrected.

The easiest way to see the significance is to compare the original and refined versions.

The original version already had the right broad shape:

- `ExtractionLoop`
- endpoint-triggered extraction
- token-threshold fallback
- previous todo context

The refinement pass made the semantics much sharper.

### Recommendation 10: Stop thinking of the todo list as monotonically growing

This is one of the clearest conceptual corrections in the spec diff.

The original item 3 goals included:

- "The todo list never loses items during a session"

The refined version replaced that with:

- later speech can merge or remove earlier todos when later context shows the earlier extraction was wrong

This is a major architectural reframe.

Why it mattered:

- real-time extraction is interpretive, not append-only
- early extractions are provisional in meaning even if the UI shows them immediately
- if later speech changes understanding, the system needs permission to correct itself

The original monotonic-growth idea sounds user-friendly, but it would have pushed the system toward the wrong abstraction:

- it would reward over-preserving mistakes
- it would make cleanup and merge behavior feel like regressions instead of intended corrections

Architectural consequence:

- the backend is allowed to revise meaning, not just add more items
- the extraction prompt must support merge/remove behavior
- the frontend must treat each `todos` payload as the latest snapshot of understanding

This is one of the most important later recommendations because it changes what the product is fundamentally doing.

The system is not "streaming immutable todos."

It is "streaming the best current structured interpretation of a growing transcript."

### Recommendation 11: Abandon position-based identity

The original item 3 spec said:

- the LLM returns the full current list
- position in the list is the stable identity

The refined spec explicitly removed that and replaced it with:

- this is a snapshot, not a patch
- the frontend replaces the whole list
- it must not assume stable identity across extractions

This was a necessary correction once merge/remove behavior was accepted.

Why this mattered:

- if items can merge, disappear, or be reordered, index-based identity is not real identity
- pretending otherwise would leak a false invariant into the UI layer
- later features like change highlighting would become brittle if they assumed identity where none exists

Architectural consequence:

- the protocol remains simple: one `todos` snapshot message
- the frontend avoids building identity-heavy state on top of unstable semantics
- future diffing is explicitly best-effort, not truth-bearing

This recommendation matters because it prevents the architecture from drifting toward a fake event-sourcing model that the extraction system cannot actually support.

### Recommendation 12: Make stop semantics precise, not approximate

The refined spec tightened the stop story in several ways.

Original framing:

- on stop, do one final extraction on the complete transcript

Refined framing:

- on stop, do one final extraction on the complete finalized transcript
- if an extraction is already in flight, let it finish
- then do exactly one final finalized pass
- only after that can `stopped` be sent

This is one of the deepest later recommendations, because it defines stop as a concurrency boundary rather than a button event.

Why this mattered:

- without this rule, stop can race with a background extraction
- if stop reuses a speculative mid-stream snapshot, the final result is not actually final
- sending `stopped` too early collapses "recording has ended" and "final understanding is complete" into one event, even when they are not the same

Architectural consequence:

- stop becomes the place where the backend reconciles concurrency and transcript finalization
- the protocol guarantee becomes `todos` then `stopped`, with the final `todos` representing finalized state
- the system has one clean definition of what "session completion" means

This recommendation is important because it prevents a whole family of bugs where the app appears done while the architecture is still mid-correction.

### Recommendation 13: Do not rely on Soniox defaults for endpoint behavior

The refined spec added an explicit recommendation that `ws.py` must set:

- `enable_endpoint_detection: true`
- `max_endpoint_delay_ms` explicitly

This matters more than it looks.

The original idea assumed endpoint detection conceptually, but it did not fully lock down the configuration responsibility.

The later recommendation corrected that by saying:

- endpoint-based extraction is only a real design choice if the backend config explicitly requests it

Why this mattered:

- default vendor settings are not a stable architectural contract
- endpoint behavior directly affects extraction timing
- timing changes here reshape the user experience of "todos while speaking"

Architectural consequence:

- the backend owns the speech-boundary strategy explicitly
- tuning becomes visible and intentional
- the project avoids hidden dependency on vendor defaults

This is a classic reliability recommendation: if a behavior is important to product semantics, it should not live in undocumented default settings.

### Recommendation 14: Separate background extraction failure semantics from stop-time failure semantics

The item 3 plan makes this explicit in a way the original spec did not:

- background endpoint and token-threshold extractions should log failures and keep the session alive
- the final stop-time extraction must propagate failure so `ws.py` can surface a warning

This is a subtle but excellent architectural recommendation.

Why it mattered:

- not all extraction failures are equally important
- background failures are recoverable because more transcript is still coming
- final stop-time failure is the last chance to produce the authoritative result

If both cases are handled the same way, the architecture becomes confused:

- either background glitches become too disruptive
- or final-pass failures become too easy to ignore

Architectural consequence:

- the loop gets explicit semantic roles for different failure classes
- `ExtractionLoop` and `ws.py` share responsibility in a disciplined way
- the user sees honest degradation only when it actually matters at session completion

The item 3 plan makes one more good recommendation here:

- if the final extraction fails, do not overwrite the last successfully sent todo snapshot with an empty replacement

That is important because an empty list would falsely communicate "there are no todos" when the real truth is "the final refinement failed."

This recommendation is important because it is the difference between "handle all exceptions" and "design failure behavior by lifecycle phase."

### Recommendation 15: Promote deterministic tests to primary status for item 3 too

The spec diff here is extremely revealing.

The original item 3 testing section effectively centered live Soniox + Gemini end-to-end tests as primary.

The refined version changed that to:

- deterministic component and integration tests are primary
- live end-to-end behavioral tests are secondary and opt-in

That is not a small test preference. It is an architectural recommendation about what should carry CI confidence.

Why it mattered specifically for item 3:

- concurrent extraction logic has edge cases that live-vendor tests are actually bad at isolating
- the most important behaviors involve race conditions and semantic guarantees:
  - dirty-flag collapse
  - stop waiting for in-flight work
  - final-pass propagation rules
  - endpoint token filtering
- these are best proven with deterministic tests, not with live services

Architectural consequence:

- `ExtractionLoop` becomes a deliberately isolated unit
- `ws.py` gets deterministic tests around ordering and stop semantics
- live e2e checks become validation of pipeline behavior, not the primary proof of core logic

This recommendation matters because item 3 added concurrency. Once concurrency enters the architecture, deterministic tests stop being "nice to have."

They become the only reliable way to prove core guarantees.

### Recommendation 16: Add a plan that forces the architecture into separable seams

The item 3 implementation plan is valuable not only because it is detailed, but because it decomposes the work along architectural seams rather than along generic implementation chores.

The plan breaks the work into:

- transcript seam
- extraction prompt seam
- extraction loop seam
- observability seam
- WebSocket orchestration seam
- frontend rendering seam
- e2e behavioral seam

That decomposition matters because it reflects a particular recommendation:

- build and test each semantic boundary in isolation before wiring the whole feature together

Why this mattered:

- "todos while speaking" sounds like one feature
- in reality it touches protocol semantics, extraction semantics, concurrency, runtime observability, and frontend rendering
- treating it as one undifferentiated feature would have hidden the exact places most likely to regress

Architectural consequence:

- the plan itself encodes the intended modular boundaries
- it becomes easier to review and test each design claim separately
- later contributors can see which seam owns which kind of correctness

This is why the plan matters as an architectural artifact, not just as task management.

### Recommendation 17: Use Logfire at the orchestration seams, not just at request boundaries

Both item 2.5 and item 3 touch observability, but item 3 makes the recommendation sharper:

- instrument the loop and the WebSocket orchestration where timing and trigger decisions happen

The reason this matters is that normal request-level tracing is not enough for this feature.

The interesting questions are:

- why did extraction fire now?
- was it endpoint-triggered or token-threshold-triggered?
- how long did a cycle take?
- how many previous todos were in play?
- did the final stop pass happen after transcript finalization?

Architectural consequence:

- observability is attached to the semantic seams, not only the transport layer
- future tuning of endpoint delay and token threshold becomes evidence-driven
- debugging can answer "why did the system decide this?" instead of only "what request happened?"

This recommendation matters because real-time extraction problems are usually orchestration problems, not plain HTTP-style request problems.

One useful detail here:

- the item 3 design started with a 30-token fallback threshold as the initial planning value
- the current runtime uses `TOKEN_THRESHOLD = 10` and `max_endpoint_delay_ms = 1000`

Those should be understood as tuning knobs, not core architectural invariants.

## Part III: The Most Important Cross-Cutting Corrections

The later pass on item 2.5 and item 3 introduced three cross-cutting corrections that are easy to miss if you read the docs only as implementation instructions.

### Correction A: The system is snapshot-oriented, not event-sourced

This is the biggest conceptual correction in the later design.

Once you accept:

- merge/remove behavior
- no stable todo identity
- full-list replacement

you are no longer building an append-only todo event stream.

You are building a system that repeatedly publishes the best current structured interpretation of the transcript.

That has consequences everywhere:

- backend prompt design
- loop semantics
- UI rendering
- change highlighting
- tests

Many later decisions only make sense once you see this correction clearly.

### Correction B: "Stop" means architectural convergence, not just user intent

The stop button expresses user intent, but the later design says the architecture is not done when the user clicks it.

The architecture is done only when:

- Soniox finalization has flowed through
- any in-flight extraction has resolved
- the guaranteed final extraction pass has been attempted
- the last `todos` snapshot has been sent
- the frontend has received `stopped` with any warning needed

That is a much better definition of completion.

### Correction C: Test truth must follow runtime truth

This is the testing principle behind both item 2.5 and item 3.

If the runtime owns transcript accumulation and stop semantics, then tests must prove those same paths, not approximate them.

That is why the later design keeps pushing toward:

- shared accumulation logic
- deterministic loop tests
- deterministic ws ordering tests
- opt-in live checks instead of vendor-heavy default CI

This is one of the deepest architectural values introduced in the later pass.

## If You Only Want The Recommendations That Most Changed The Architecture

These are the seven I would keep:

1. Make transcript assembly a single shared backend seam.
2. Surface degraded stop behavior explicitly through `warning`.
3. Ground extraction in explicit datetime/timezone context and typed date fields.
4. Treat todo extraction results as full snapshots, not stable identity updates.
5. Allow merge/remove corrections; do not force monotonic todo growth.
6. Define stop as "wait, finalize, run one final pass, then send `stopped`."
7. Make deterministic tests primary and live-vendor tests secondary.

If you understand those seven, you understand most of the later architectural thinking that shaped the current project.

## Recommended Reading Order For This Topic

For the exact artifact trail behind this deep dive, read:

1. `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`
2. `git show 0f83d3c:docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`
3. `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`
4. `docs/superpowers/plans/2026-03-24-item3-todos-while-speaking.md`
5. `backend/app/transcript_accumulator.py`
6. `backend/app/extraction_loop.py`
7. `backend/app/ws.py`
8. `backend/app/extract.py`
9. `frontend/src/hooks/useTranscript.ts`

That reading order shows the correction from broad design, to refined design, to executable architecture.
