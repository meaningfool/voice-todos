# Acceptance Tests And Verification Policy

This note defines how this repo should use acceptance tests, verification
tests, and phase gates in specs, plans, and implementation work.

## Core Distinction

`Acceptance test`
- An acceptance test captures part of the current behavioral contract of the
  app.
- It is the smallest realistic test that proves a specific intended behavior.
- In phased work, acceptance tests are the tests that can serve as phase
  completion gates.

`Verification test`
- A verification test improves confidence in the implementation.
- It may be a unit test, integration test, replay test, browser test, helper
  test, or regression test.
- Verification tests are often necessary, but they do not by themselves define
  phase completion unless the spec or plan explicitly names them as acceptance
  tests for that behavior.

## Acceptance Is A Role, Not A Layer

Acceptance is orthogonal to the test pyramid.

An acceptance test may live at different sizes or layers depending on what is
required to prove the behavior:

- a backend unit test
- a backend integration test
- a CLI-driven integration test
- a browser-driven end-to-end test
- a frontend test

The test should live where it naturally belongs technically.

Do not move a test into a special folder just because it is used as an
acceptance test. If a backend integration test is the right proof, it should
stay under the backend test suite. If a browser flow is the right proof, it
should live with the browser-facing test harness.

## Source Of Truth

The canonical place that identifies acceptance tests is the spec and plan for
the work.

Specs and plans must explicitly distinguish:

- `Acceptance tests`
  - the minimal tests that prove the intended behavioral delta
- `Supporting verification`
  - other tests that improve confidence but do not define completion

The repo may additionally use language-specific markers or tags when helpful,
but those are secondary. The spec and plan remain the source of truth for what
counts as an acceptance test for a given change.

Examples:

- a Python test may use `@pytest.mark.acceptance_test` if that improves local
  discovery
- a frontend test suite may use its own tagging mechanism if useful

Those tags are optional implementation aids, not the primary definition.

## Acceptance Tests In Phased Work

In a phased spec or phased plan:

- each phase is defined by a behavioral delta
- each phase must name the acceptance tests that prove that behavioral delta
- the next phase must not begin until the current phase's acceptance tests pass

Acceptance tests are phase gates because they prove the behavior that the phase
exists to deliver.

## Placement Rules

Place tests according to the subsystem and harness that make the most sense:

- backend-only behavior: keep the test in the backend suite
- frontend-only behavior: keep the test in the frontend suite
- CLI-owned behavior: keep the test with the CLI or backend suite, whichever
  provides the clearest ownership and execution path
- cross-system or browser-driven behavior: use a shared root-level location if
  that is the cleanest place
- non-pytest automated live validations: keep them in a test-owned location
  such as `tests/live/`, not in a generic utility folder like `scripts/`

Acceptance status does not determine placement. Technical ownership and the
best execution harness determine placement.

## Automated Suite Assets vs Utility Scripts

Not every automated test in the repo needs to be `pytest`-backed.

Two different kinds of executable Python files may exist:

`Automated suite assets`
- These are part of the test suite.
- They run by concrete command.
- They produce a structured outcome such as `PASS`, `FAIL`, or `WARN`.
- They are named in the spec or plan as required validation commands.
- When they are not `pytest` tests, they should live under a test-owned tree
  such as `tests/live/`.

`Utility scripts`
- These are operational helpers such as bootstraps, conversions, or local dev
  utilities.
- They are not themselves test-suite assets.
- They may still be exercised by tests, but they should remain under
  `scripts/` or another utility-oriented location.

This distinction exists to avoid mixing runnable test-suite assets with generic
maintenance or developer utilities.

## Minimality Rule

For each behavior area, maintain a small acceptance surface that reflects the
current intended behavior.

The goal is not one new permanent acceptance test for every change request.
The goal is a small set of durable acceptance tests that describe the current
behavioral contract.

For each behavior change, the plan should explicitly decide whether acceptance
coverage needs to:

- `update` an existing acceptance test
- `replace` an existing acceptance test
- `add` a new acceptance test
- `remove` an obsolete acceptance test

That decision should be made behavior area by behavior area, not item number by
item number.

## Avoiding Combinatorial Explosion

The main hygiene rules are:

1. Organize acceptance tests by stable behavior area, not by item number or
   implementation phase number.
2. Prefer updating an existing acceptance test when the intended behavior of
   that area evolves.
3. Add a new acceptance test only when the change introduces a genuinely new
   behavioral contract that is not already represented.
4. Move edge cases, seam checks, and internal regressions into supporting
   verification tests rather than growing the acceptance surface without bound.
5. Delete or replace obsolete acceptance tests when the product contract
   changes.

This keeps the acceptance surface small and durable while allowing the broader
verification surface to grow where needed.

## Duplication Hygiene

Do not create a duplicate "acceptance copy" of a test if an existing test is
already the smallest realistic proof of the behavior.

If an existing backend or frontend test already proves the behavior well enough,
that same test can be the acceptance test named in the spec or plan.

Supporting verification should complement acceptance coverage, not mirror it.

## Naming Rules

Do not name tests after temporary planning artifacts such as:

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
2. Which tests are the acceptance tests for that behavioral delta?
3. Where do those tests naturally belong?
4. Is each acceptance test being updated, replaced, added, or removed?
5. What supporting verification is needed beyond the acceptance tests?

If those questions are not answered, the testing strategy is incomplete.
