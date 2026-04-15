# Building Phased Specs And Plans With Acceptance Criteria

This note defines how phased specs and phased plans should be written in this
repo, and how acceptance criteria, acceptance tests, and verification tests
relate to phase completion.

## Core Principle

A phase is defined by a behavioral change, not by an implementation chunk.

Each phase must introduce one coherent behavioral delta that can be judged on
its own.

The judgment that a phase is complete, also known as its definition of done,
happens through acceptance criteria.

Acceptance criteria are hard for that phase:

- the next phase must not begin until the current phase's acceptance criteria
  are implemented and verified
- acceptance criteria define when the phase is actually done

## Definitions

`Phase`
- The smallest independently valuable behavioral change that can be judged on
  its own.

`Behavioral delta`
- The externally observable behavior introduced by the phase.
- This must be phrased in system or product terms, not code-structure terms.

`Acceptance criteria`
- The human-readable conditions that define when a phase's behavioral delta is
  done.
- A phase may have multiple acceptance criteria.
- More than about three acceptance criteria is usually a signal that the phase
  is too large or mixes multiple behavioral changes.

`Acceptance test`
- The concrete automated proof that an acceptance criterion is met.
- An acceptance test captures part of the current behavioral contract of the
  app.
- In phased work, acceptance tests are the tests that prove the current phase
  is complete.
- The spec and plan are the source of truth for which tests count as
  acceptance tests for a given change.
- The usual mapping is one acceptance criterion to one acceptance test,
  although a single criterion may sometimes need two or three tests to prove it
  well.
- A single acceptance test should generally not be used as the proof for
  multiple acceptance criteria. If that starts happening, the criteria or the
  test boundary should be reconsidered.

`Verification test`
- Any unit, integration, replay, seam, helper, or regression test that
  improves implementation confidence.
- Verification tests are often necessary, but they do not by themselves define
  done unless the spec or plan explicitly names them as acceptance tests for
  that behavior.

## Requirements For Specs

For each phase, a spec must explicitly define:

1. `Objective`
- What behavior this phase introduces.

2. `Behavioral delta`
- What is different from before this phase.

3. `Non-goals`
- What this phase does not attempt to change.

4. `Acceptance criteria`
- The human-readable conditions that define done for this phase.
- These should be phrased in behavior terms, not implementation steps.
- A phase may have multiple criteria, but the list should stay small enough
  that a human can quickly judge what success means.

5. `Acceptance tests`
- The tests intended to prove the acceptance criteria.
- The spec should identify the expected test ownership and location as
  concretely as possible.
- The spec should make it clear which acceptance criteria those tests are meant
  to prove.
- The mapping should usually be one criterion to one test, with exceptions
  called out explicitly when a criterion needs multiple tests.
- When known, name the suite, file path, and test name or command that will
  prove the behavior.
- If exact identifiers are not final yet, the spec must still identify the
  expected harness and subsystem clearly enough that the plan can pin them
  down.

## Requirements For Plans

For each phase, a plan must include:

1. Tasks that implement only that phase's behavioral delta.
2. Supporting verification tasks and tests that help development confidence but
   are not the phase's definition of done.
3. Exact commands or procedures for the acceptance tests that prove the phase.
4. An explicit checkpoint stating that the next phase must not begin until the
   current phase's acceptance criteria are implemented and verified.

Plans must not blur implementation tasks, supporting verification work, and
acceptance completion.

## Acceptance Criteria And Acceptance Tests

Acceptance criteria and acceptance tests serve different purposes and should be
written differently.

Acceptance criteria define the human judgment of done.

Acceptance tests provide the concrete automated proof for that judgment.

Acceptance criteria and acceptance tests should remain traceable to each other.

The default shape is:

- one acceptance criterion
- one acceptance test that proves it

Sometimes a criterion needs more than one acceptance test. That is acceptable
when the behavior cannot be proved credibly by a single test.

A single acceptance test should generally not be stretched across multiple
acceptance criteria. If one test appears to satisfy several criteria, that is
usually a sign that the criteria are too broad or that the proof should be
split into clearer tests.

### Good Acceptance Criteria

Good acceptance criteria are:

`Phase-specific`
- They describe the behavioral delta introduced by the phase, not unrelated
  behavior.

`Human-readable`
- They are easy for a reviewer to read and use as an alignment tool.

`Externally meaningful`
- They describe observable outputs, user-visible behavior, protocol behavior,
  or state transitions.

`Minimal`
- They are only numerous enough to define the phase's contract.

### Acceptance Criteria Traits

Bad traits:

- says what the system `accepts`, `maps`, `preserves`, or `is`, instead of
  saying what happens
- talks about hidden machinery instead of the thing the actor does or gets
- describes a judgment in someone's head instead of a system output
  - examples: `can understand`, `legible`, `readable`
- uses vague scope words that are not defined in the sentence
  - examples: `minimal`, `shared benchmark system`
- uses passive phrasing that hides who is acting
  - examples: `a benchmark can be declared`, `a recording can be added`
- states what is no longer true instead of stating the new behavior positively
  - example: `no longer assumes`
- makes the criterion about a detail the actor does not care about directly
  - examples: `lock artifact`, `target_streaming_delay_ms`

Good traits:

- starts from a clear actor and a clear action
- names the concrete thing that comes out of the system
  - examples: `get a report`, `writes audio.pcm`, `is visible from another worktree`
- says what happens in plain words without requiring knowledge of the internals
- states the new behavior positively
- keeps the main criterion about the behavior, not about the plumbing
- uses details only when they define the scope in a meaningful way
- works as a short answer to: `What is newly possible after this phase?`
- is easy to imagine proving with one test

### Don't / Do

- Don't: `The shared benchmark system accepts that STT benchmark as a valid benchmark definition.`
- Do: `A developer can define a benchmark on the STT dataset.`

- Don't: `Each Voxtral profile maps to an explicit target_streaming_delay_ms value.`
- Do: `A developer can define a benchmark with the intended Voxtral delay profiles.`

- Don't: `A developer can understand the Soniox-versus-Voxtral tradeoff from that comparison.`
- Do: `Running the STT benchmark produces a report.`

- Don't: `The comparison makes transcript quality and latency legible enough to judge the tradeoff.`
- Do: `The report shows transcript quality and latency for each benchmark entry.`

- Don't: `Recorded session layout no longer assumes Soniox is the only provider that matters for STT curation.`
- Do: `Starting a recorded STT session writes a trace file named after the active provider.`

- Don't: `A curated recording can be added to the STT dataset with its reviewed reference transcript.`
- Do: `A developer can add a new STT case from an existing recording.`

- Don't: `A benchmark can be declared on that STT dataset with Soniox and one named Voxtral profile.`
- Do: `A developer can define a benchmark on the STT dataset.`

- Don't: `A developer can prepare that benchmark for execution and get one lock artifact that still refers to the same curated STT cases.`
- Do: `A developer can run the benchmark on the curated STT cases.`

### Good Acceptance Tests

Good acceptance tests are:

`Behavior-oriented`
- They prove the intended behavior, not the implementation structure.

`Smallest realistic proof`
- They are the smallest tests that still prove the behavior credibly.

`Durable`
- They remain useful as part of the regression surface after the phase lands.

`Runnable`
- They have concrete inputs, concrete execution steps, and concrete expected
  outcomes.

`Non-duplicative`
- They should not create an "acceptance copy" of a test if an existing test
  already provides the smallest realistic proof of the behavior.

## Acceptance Is A Role, Not A Layer

Acceptance is orthogonal to the test pyramid.

An acceptance test may live at different sizes or layers depending on what is
required to prove the behavior:

- a backend unit test
- a backend integration test
- a CLI-driven integration test
- a browser-driven end-to-end test
- a frontend test
- a non-pytest automated live validation named explicitly in the spec or plan

The test should live where it naturally belongs technically.

Do not move a test into a special folder just because it is used as an
acceptance test.

If a backend integration test is the right proof, it should stay under the
backend suite. If a browser flow is the right proof, it should live with the
browser-facing harness. If a non-pytest automated validation is the right
proof, it should live under a test-owned location such as `tests/live/`, not in
`scripts/`.

Acceptance status does not determine placement. Technical ownership and the
best execution harness determine placement.

## Maintaining Acceptance Coverage

Acceptance tests are regular tests that, for a given behavior change, are
identified as the behavioral contract that defines done.

When intended behavior changes, the spec and plan should explicitly decide
whether acceptance coverage for that behavior area needs to:

- `update` an existing acceptance test
- `replace` an existing acceptance test
- `add` a new acceptance test
- `split` an existing acceptance test into a smaller set of clearer behavioral
  proofs
- `remove` an obsolete acceptance test

That decision should be made by stable behavior area, not by item number or
phase number.

Once a test is part of the acceptance coverage for a behavior area, later work
should continue passing it unless the behavioral contract has intentionally
changed and the spec or plan explicitly updates, replaces, or removes that
coverage.

The goal is a small, durable acceptance surface that reflects the current
behavioral contract without growing by default for every change request.

Avoid combinatorial explosion by choosing the smallest durable proof surface
that still captures the real contract:

- keep an existing broad acceptance test when it already proves the behavioral
  contract that matters
- prefer narrower acceptance or verification coverage for new seams,
  integrations, or adapters when the broad behavior is already covered
- split an acceptance test when one broad proof is no longer the clearest or
  most maintainable way to represent the behavior
- use one-off supporting verification when needed to validate a specific
  combination without permanently expanding the acceptance surface

Supporting verification should complement acceptance coverage, not mirror it.

## What Acceptance Criteria And Acceptance Tests Are Not

Acceptance criteria and acceptance tests are not:

- implementation task lists
- helper-level checks that do not prove user-visible or externally meaningful
  behavior
- purely structural assertions
- implementation-detail assertions
- broad regression sweeps unless the phase's behavioral delta is itself broad

Those belong in implementation planning or supporting verification, not in the
definition of done.

## Naming Rules

Do not name acceptance tests after temporary planning artifacts such as:

- item numbers
- phase numbers
- one-off rollout labels

Name them after the behavior or component they cover.

Good examples:

- `test_first_run_creates_benchmark_lock`
- `test_run_stops_when_hosted_dataset_has_drifted`
- `test_run_requires_explicit_stale_handling`

Bad examples:

- `test_item75_phase2`
- `validate_item75_phase3`

## Review Rule For New Specs And Plans

When writing or reviewing a spec or plan, check that it answers all of these:

1. What is the behavioral delta of this phase or change?
2. What are the acceptance criteria for that behavioral delta?
3. Which tests prove those criteria?
4. Where do those tests naturally belong?
5. Is each acceptance test being updated, replaced, added, or removed?
6. What supporting verification is needed beyond the acceptance tests?

If those questions are not answered, the spec or plan is incomplete.
