# Acceptance Tests And Verification Policy

This document defines the durable verification policy for this repo.

## Acceptance Tests

- Acceptance is a role, not a test layer.
- The acceptance tests for a change are the behavioral contract tests explicitly named by the current spec or plan.
- An acceptance test may be unit, integration, CLI, browser, backend, or frontend depending on what actually proves the behavior.
- Keep acceptance tests where they naturally belong technically. Do not move them into a separate folder just because they are used for acceptance.
- Keep the acceptance surface small and current. When behavior changes, update, replace, add, or remove acceptance tests deliberately.
- Do not name tests after item numbers or phase numbers.

## Supporting Verification

- Supporting verification is everything that helps build confidence without being the contract surface for the change.
- Examples include broader regression suites, linting, type checks, fixture generation, exploratory runs, and ad hoc debugging commands.
- Specs and plans should distinguish clearly between acceptance tests and supporting verification.

## Phased Gates

For multi-phase specs or plans:

- each phase should state the behavior being proven
- each phase should name the exact proving command or commands
- each phase should state what evidence those commands are expected to produce
- unresolved or contradictory evidence should be treated as an open gate, not rounded into success

## Browser-Facing Work

- Browser-facing changes require live validation.
- Backend or frontend test suites do not replace live validation.
- Prefer deterministic smoke scripts when the repo already has them.

## Final Handoff

- Report the exact acceptance commands that were run.
- Report whether each command passed or failed.
- If browser validation was required, report the exact browser command or script and the outcome.
- If something was not run, say so explicitly.
