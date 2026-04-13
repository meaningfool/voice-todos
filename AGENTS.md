## Live Validation

- For browser-facing work, use the `agent-browser` skill and run a live browser check before calling the task done.
- Backend/frontend test suites do not count as live validation.
- Use `agent-browser eval` to inspect or patch page state, but use real `agent-browser` interaction commands for user actions like clicks, typing, and presses.
- Prefer an existing smoke script. If it is stale or missing, update or add it in the same task.
- In the final handoff, report the exact browser validation command or script you ran and whether it passed.

## Specs And Plans

- When writing specs or plans, the phased acceptance-gate guidance in [docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md](/Users/josselinperrus/conductor/workspaces/voice-todos/kingston/docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md:1) takes precedence over the default superpowers skill instructions.

## Acceptance Tests

- Treat acceptance tests as the behavioral contract tests explicitly named by the current spec or plan.
- Acceptance is a role, not a test layer: an acceptance test may be unit, integration, CLI, browser, backend, or frontend depending on what is required to prove the behavior.
- Keep tests where they naturally belong technically. Do not move a test into a special location just because it is used as an acceptance test.
- Distinguish acceptance tests from supporting verification in specs and plans.
- When behavior changes, update, replace, add, or remove acceptance tests deliberately to keep the acceptance surface small and current.
- Do not name tests after item numbers or phase numbers.
- Reference: `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
