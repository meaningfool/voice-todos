# Phased Specs And Plans: Acceptance Gates

This note defines how phased specs and phased plans must be written in this
repo.

## Core Principle

A phase is defined by a behavioral change, not by an implementation chunk.

Each phase must introduce one coherent behavioral delta that can be judged on
its own. A phase is complete only when its acceptance gates pass.

## Definitions

`Phase`
- The smallest independently valuable behavioral change that can be judged on
  its own.

`Behavioral delta`
- The externally observable behavior introduced by the phase.
- This must be phrased in system/product terms, not code-structure terms.

`Acceptance gate`
- A durable, scenario-based test that proves the behavioral delta introduced by
  the phase works in a realistic flow.
- Acceptance gates define completion.
- If an acceptance gate is red, the phase is not complete.

`Verification test`
- Any unit, integration, replay, or helper test that supports implementation
  confidence.
- Verification tests are useful and often necessary, but they do not define
  phase completion.

## Requirements For Specs

For each phase, a spec must explicitly define:

1. `Objective`
- What behavior this phase introduces.

2. `Behavioral delta`
- What is different from before this phase.

3. `Non-goals`
- What this phase does not attempt to change.

4. `Acceptance gates`
- The minimal durable scenarios that prove the behavioral delta of the phase.
- These are hard gates.

5. `Supporting verification`
- Useful lower-level tests that help implementation but do not define
  completion.

6. `Phase boundary rule`
- The next phase must not begin until all current-phase acceptance gates pass.

## Requirements For Plans

For each phase, a plan must include:

1. Tasks that implement only that phase's behavioral delta.
2. Supporting verification tasks.
3. Exact commands or procedures for the phase acceptance gates.
4. An explicit checkpoint stating that the next phase must not begin until all
   current-phase acceptance gates pass.

Plans must not blur implementation tasks, verification work, and acceptance
completion.

## Acceptance Gate Requirements

A good acceptance gate must be:

`Phase-specific`
- It proves the behavior introduced in that phase, not unrelated behavior.

`Externally meaningful`
- It validates observable outputs, protocol behavior, state transitions, or
  live execution behavior.

`Minimal`
- Only enough scenarios to prove the phase's behavioral delta.

`Durable`
- It remains in the test suite after the phase is complete.

`Runnable`
- It has a concrete scenario, concrete inputs, and concrete expected outcomes.

`Hard-gated`
- If it fails, the phase is incomplete.

## What Acceptance Gates Are Not

Acceptance gates are not:

- unit tests of helper functions
- purely structural tests
- implementation-detail assertions
- broad regression checks unless the phase's behavioral delta is itself broad

Those are verification tests, not acceptance gates.

## How Acceptance Gates Evolve

Acceptance gates are permanent regression assets.

Default rule:
- earlier phase acceptance gates remain in the test suite
- later phases must continue passing them

Allowed exception:
- if intended behavior changes, the spec must explicitly state that an earlier
  acceptance gate is being replaced or revised

Acceptance gates must not be throwaway scaffolding.

## Hard Rule

A phased spec or phased plan is incomplete if it does not state:

- the behavioral delta of each phase
- the acceptance gates for each phase
- that the next phase cannot begin until the current phase's acceptance gates
  pass

This rule is mandatory.
