## Live Validation

- For browser-facing work, use the `agent-browser` skill and run a live browser check before calling the task done.
- Backend/frontend test suites do not count as live validation.
- Use `agent-browser eval` to inspect or patch page state, but use real `agent-browser` interaction commands for user actions like clicks, typing, and presses.
- Prefer an existing smoke script. If it is stale or missing, update or add it in the same task.
- In the final handoff, report the exact browser validation command or script you ran and whether it passed.

## Specs And Plans

- When writing specs or plans, the phased acceptance-gate guidance in [docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md](/Users/josselinperrus/conductor/workspaces/voice-todos/andorra/docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md:1) takes precedence over the default superpowers skill instructions.
