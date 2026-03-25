# Architecture Walkthrough: Decisions, Revisions, and Gotchas

This is the high-level walkthrough for the current `voice-todos` architecture.

It is not a file-by-file code tour. It focuses on the places where the original plan turned out to be incomplete, where implementation reality forced a change, and where future work is most likely to go wrong if you miss an architectural assumption.

## Why this document exists

There are two stories in this repo:

1. the planned architecture in the item specs and plans
2. the corrected architecture we arrived at after debugging real Soniox behavior, hardening the runtime, and revising the product direction

The tricky parts live in the gap between those two stories.

## The System In One Page

The current runtime shape is:

`browser mic -> frontend WebSocket -> FastAPI -> Soniox RT -> TranscriptAccumulator -> ExtractionLoop -> Gemini -> todos snapshots -> frontend`

The important thing is not the boxes. It is the ownership boundaries:

- Soniox owns streaming speech recognition
- the backend owns transcript assembly and stop-time correctness
- Gemini owns todo extraction from transcript snapshots
- the frontend owns presentation and session lifecycle, but not canonical transcript truth

If you keep those boundaries clear, the rest of the codebase makes sense.

## Read In This Order

If you are onboarding or revisiting the architecture, read these first:

1. `docs/references/soniox.md`
2. `learnings.md`
3. `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`
4. `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`
5. `docs/superpowers/specs/2026-03-24-item4-ui-redesign-design.md`
6. `backend/app/transcript_accumulator.py`
7. `backend/app/extraction_loop.py`
8. `backend/app/ws.py`
9. `frontend/src/hooks/useTranscript.ts`

That sequence gives the design intent, the debugging lessons, and then the runtime seams.

## The Architectural Choices That Actually Matter

### 1. Stop correctness is a Soniox protocol problem, not a browser flush problem

This was the biggest design correction.

The first assumption was: if trailing words are missing, audio is probably being lost between the browser and the backend during stop. That led to stop-delay experiments and a now-removed 300ms flush idea.

What we learned instead:

- Soniox `b""` means "no more audio"
- it does not mean "finalize pending interim tokens"
- Soniox needs an explicit `{"type": "finalize"}` control message before the stream is ended

That distinction is the reason the trailing-word bug existed.

The key invariant is:

- do not treat stop as complete until the backend has allowed Soniox finalization to flow through the relay path

Two related gotchas:

- `<fin>` is a protocol marker, not transcript text, so it must be filtered
- after `<fin>`, previously tracked interim text is stale and must be cleared or you can duplicate transcript text

Important nuance:

- the current frontend still has a 200ms mic-tail delay
- that is not the root transcript fix
- the root transcript fix is manual finalization

If someone "optimizes" stop handling without understanding this, trailing words will come back as a bug.

### 2. The backend owns the canonical final transcript

Originally the frontend reconstructed transcript state from streaming token events and tried to preserve the tail on stop.

That turned out to be the wrong ownership model for session completion.

The current design is:

- live token messages are for responsive UI updates
- the backend-assembled transcript sent in `stopped` is the source of truth for the final session result

Why this matters:

- the backend sees the full Soniox stream, including finalize semantics
- the backend owns `TranscriptAccumulator`
- the frontend should not have to reverse-engineer stop-time transcript correctness from UI timing

This choice prevents a whole class of "the UI lost text but the backend had it" bugs.

Rule of thumb:

- if you are changing final transcript behavior, start in the backend, not the React hook

### 3. `TranscriptAccumulator` is a core seam, not a helper

`backend/app/transcript_accumulator.py` looks small, but architecturally it is one of the most important files in the repo.

It centralizes:

- final token accumulation
- interim token replacement
- `<fin>` handling
- `<end>` filtering and detection
- stop-time full transcript assembly

The important design choice here was to stop duplicating transcript logic in tests and runtime.

That is why replay tests now run through production accumulation behavior instead of a test-only reconstruction path. Without that change, we could have green tests that blessed the wrong algorithm.

Rule of thumb:

- if transcript semantics change, update `TranscriptAccumulator` first and make tests use that path

### 4. Todo extraction is snapshot-based, not patch-based

This is the second major architectural shift after Soniox finalization.

The tempting design would have been:

- give todos stable IDs
- send incremental patches
- mark items as tentative vs confirmed

That is not how the current system actually works.

The current design is:

- Gemini receives the full current transcript
- optionally receives `previous_todos`
- returns the updated complete todo list
- the backend sends the full list snapshot
- the frontend replaces its rendered todo list with the latest snapshot

This matters because later speech can:

- refine an earlier todo
- merge two earlier todos
- remove a mistaken earlier todo
- reorder the list slightly

In other words, the extraction model is "current best understanding," not append-only event sourcing.

Important consequence:

- the frontend must not assume item identity is stable across snapshots

That is also why item 4 changed direction. Tentative-vs-confirmed UI was the wrong abstraction for a system whose real behavior is repeated snapshot replacement with best-effort refinement.

### 5. `ExtractionLoop` is intentionally collapse-based, not queue-based

`backend/app/extraction_loop.py` is where the repo makes its main concurrency tradeoff.

The choice was:

- do not queue every trigger
- do not run overlapping extractions
- use a dirty flag to collapse multiple triggers into one rerun

Why this is the right shape:

- extraction is expensive
- the transcript can change while an extraction is in flight
- the user cares about the latest good snapshot, not every intermediate snapshot

So the loop behaves like this:

- endpoint or token-threshold trigger starts extraction
- if another trigger arrives while extraction is running, mark the loop dirty
- when the current extraction finishes, run again once with the latest transcript

That keeps the system current without spawning redundant LLM work.

One more implementation detail matters here:

- the original item 3 design started with a 30-token fallback threshold
- the current runtime in `backend/app/ws.py` is tuned to `TOKEN_THRESHOLD = 10`
- Soniox endpoint detection is enabled with `max_endpoint_delay_ms = 1000`

Treat those numbers as runtime tuning knobs, not as fixed product semantics.

### 6. Stop is special: it must produce one final pass from finalized transcript state

The stop path is not just "another trigger."

This is a real architectural rule:

- if an extraction is already running when stop is requested, let it finish
- then run exactly one final extraction pass from the finalized transcript
- only then send `stopped`

That guarantees the session ends from finalized transcript state rather than from an arbitrary mid-stream snapshot.

There is also an important protocol guarantee in `backend/app/ws.py`:

- the session should still emit `todos` before `stopped`

Even in degraded cases:

- if final extraction times out, we send an empty or last-known `todos` snapshot plus a warning
- if final extraction fails, we preserve the last good snapshot and still complete the stop flow

This avoids silent data loss and keeps the frontend state machine simple.

The gotcha to remember is that stop behavior is partly about user-facing protocol stability, not just correctness inside the backend.

### 7. Relative dates need explicit runtime context

This looks like a prompt detail, but it is really an architecture decision.

The original extraction idea asked the model to resolve phrases like "tomorrow" or "next Friday" without a concrete reference datetime or timezone.

That is under-specified.

The corrected design is:

- build extraction input with current local datetime, date, and timezone
- validate `due_date` as `date`
- validate `notification` as `datetime`

Why this matters:

- temporal extraction is not deterministic without grounding
- accepting arbitrary strings makes downstream behavior look structured when it really is not

If you touch extraction prompting or schema, preserve both of these safeguards:

- explicit temporal context
- typed validation at the model boundary

### 8. Reliability hardening is part of the architecture, not cleanup work

Item 2.5 matters because it changed what "safe enough" means in this repo.

The important choices were:

- session recording is opt-in, not always on
- warnings are surfaced to the user instead of hiding degradation
- default tests are deterministic and vendor-independent
- live Soniox and Gemini tests are opt-in

These are not just DX details. They protect privacy, keep CI stable, and make debugging meaningful.

The repo is explicitly designed so that:

- normal test runs do not depend on external vendors
- when you need real-vendor confidence, you run dedicated integration or e2e checks
- if runtime behavior degrades, the system says so instead of pretending everything is fine

### 9. The UI roadmap was revised because the architecture changed underneath it

The original roadmap for item 4 focused on tentative vs confirmed todos.

That no longer matches the real system.

After item 3, the more important truths were:

- todos arrive while speaking
- todo lists are snapshots, not stable objects
- the product should feel todo-first, not transcript-first
- transcript and raw recording are still valuable, but mainly as secondary debug surfaces

So the revised item 4 is a UI rewrite, not a workflow rewrite.

That is an important product-architecture decision:

- the main shell should present evolving task output
- debugging data should remain available without dominating the main interaction model

If someone revisits the UI later, they should start from the item 4 spec, not from the older "tentative vs confirmed" framing.

Also note:

- the current `frontend/src/App.tsx` still reflects the pre-refresh shell
- the item 4 spec and plan describe the intended UI direction more accurately than the current rendered surface

## The Main Gotchas Future Work Can Trip Over

- Do not confuse Soniox "finalize" with "finish".
- Do not rebuild final transcript truth in the frontend.
- Do not add a second transcript assembly path in tests.
- Do not assume todo snapshots have stable identity.
- Do not queue overlapping extractions unless you are intentionally changing system behavior.
- Do not let stop skip the final extraction pass on finalized transcript state.
- Do not add silent fallback behavior when a warning would be more honest.
- Do not let vendor-dependent tests become the default confidence mechanism.
- Do not reintroduce always-on session recording by accident.

## Suggested Walkthroughs By Topic

### If you want to understand stop-time correctness

Read:

- `docs/references/soniox.md`
- `learnings.md`
- `backend/app/transcript_accumulator.py`
- `backend/app/ws.py`
- `backend/tests/test_soniox_integration.py`
- `backend/tests/test_ws.py`

### If you want to understand incremental todos while speaking

Read:

- `docs/superpowers/specs/2026-03-24-item3-todos-while-speaking-design.md`
- `backend/app/extraction_loop.py`
- `backend/app/extract.py`
- `backend/tests/test_extraction_loop.py`
- `backend/tests/test_e2e.py`

### If you want to understand why the frontend contract looks the way it does

Read:

- `frontend/src/hooks/useTranscript.ts`
- `frontend/src/hooks/transcriptReducer.ts`
- `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`
- `docs/superpowers/specs/2026-03-24-item4-ui-redesign-design.md`

### If you want to understand the trust model of the test suite

Read:

- `docs/handoff-interim-text-and-testing.md`
- `docs/superpowers/specs/2026-03-24-item2.5-reliability-hardening-design.md`
- `backend/tests/test_replay.py`
- `backend/tests/test_ws.py`
- `backend/tests/test_soniox_integration.py`
- `backend/tests/test_e2e.py`

## Historical Turning Points

If you want the shortest history of the key architecture corrections, these commits are the most informative:

- `6561f30` - preserve transcript on stop and use interim fallback
- `10da487` - interim-tail debugging and stop-sequence hypothesis
- `6b1773f` - explicit Soniox finalize before end-of-stream
- `96cb58e` - reliability hardening and shared transcript/runtime cleanup
- `0f83d3c` - item 3 design for while-speaking snapshots

The most important thing about that history is that the first fixes were locally reasonable but incomplete. The durable improvements came when we corrected the architectural assumptions, not just the symptoms.

## The Mental Model To Keep

If you only remember five things, remember these:

1. Soniox stop correctness depends on explicit finalization semantics.
2. Final transcript truth belongs to the backend.
3. Incremental todos are full-list snapshots, not stable entities.
4. Extraction concurrency is intentionally collapsed, not queued.
5. Reliability here means explicit degradation, deterministic tests, and opt-in vendor checks.

That is the real architecture of this project.
