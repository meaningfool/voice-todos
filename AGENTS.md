## Live Validation

- For browser-facing work, use the `agent-browser` skill and run a live browser check before calling the task done.
- Backend/frontend test suites do not count as live validation.
- Prefer an existing smoke script. If it is stale or missing, update or add it in the same task.
- In the final handoff, report the exact browser validation command or script you ran and whether it passed.
