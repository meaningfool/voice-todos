# Item 8: Logfire Analyst Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-01-item8-logfire-analyst-design.md`

**Goal:** Add a project-scoped custom Codex subagent that can analyze Logfire traces through a dedicated remote MCP connection, relate telemetry to the checked-out codebase, and propose remediation or eval improvements without making code changes.

**Architecture:** Keep the main project session free of Logfire MCP and place the Logfire-specific tool surface only on a custom agent file under `.codex/agents/`. Pair that agent config with one short repo reference note that explains when to use the agent, how authentication works in this project, and how to validate that the MCP capability stays isolated to the custom subagent.

**Tech Stack:** Codex custom subagents, TOML agent config, remote Logfire MCP, repo documentation, light shell/TOML validation, manual Codex smoke tests

**References:** `.codex/agents/`, `backend/.logfire/logfire_credentials.json`, `docs/references/logfire-trace-analysis.md`, `docs/superpowers/specs/2026-04-01-item8-logfire-analyst-design.md`

---

## Scope

This plan covers exactly four deliverables:

1. Add a project-scoped custom agent file for `logfire_analyst`.
2. Add a small repo reference note for usage, authentication, and isolation.
3. Add an opt-in probe emitter for fresh Logfire round-trip validation.
4. Validate syntax, discoverability, telemetry retrieval, and MCP isolation assumptions.

Out of scope for this plan:

- implementing Query API support
- adding a personal `~/.codex/agents/` version
- giving the main parent session Logfire MCP access
- writing code that consumes Logfire data outside the agent workflow
- any application code or eval harness changes
- adding a CI-stable remote integration test that runs automatically

---

## Design Gates

These two design gates are already resolved for implementation:

### Design Gate 1 - Endpoint and auth path

Decision:

- this repo’s Logfire project is in the EU region
- use `https://logfire-eu.pydantic.dev/mcp` for the custom agent
- default auth mode is browser-authenticated remote MCP
- sandboxed or headless fallback is a Bearer API key with `project:read`
- do not commit secrets or auth headers to the repository

Evidence source:

- `backend/.logfire/logfire_credentials.json` currently points at `logfire-eu.pydantic.dev`

### Design Gate 2 - Isolation model

Decision:

- keep the Logfire MCP definition inside `.codex/agents/logfire-analyst.toml`
- do not add project-level `mcp_servers.logfire` to `.codex/config.toml`
- document that personal global Codex config can still override the intended isolation model if the developer has already added Logfire MCP globally

This keeps the repo implementation narrow while being honest about the limit of project-scoped isolation.

### Design Gate 3 - Round-trip validation strategy

Decision:

- do not rely on a fixed historical trace for acceptance testing
- add a small opt-in probe emitter that writes a fresh uniquely identifiable Logfire span on demand
- use that probe for the manual end-to-end smoke test of MCP retrieval plus analysis
- keep this out of the default pytest suite because it depends on live Logfire auth, remote ingestion, and MCP availability

This avoids the 7-day MCP age-window staleness problem while keeping the validation realistic.

---

## File Map

### New files

| File | Responsibility |
|------|----------------|
| `.codex/agents/logfire-analyst.toml` | Project-scoped custom agent definition with read-only instructions and agent-specific Logfire MCP wiring |
| `docs/references/logfire-analyst.md` | Short usage note covering when to use the agent, auth/setup expectations, isolation caveats, and example prompts |
| `backend/scripts/emit_logfire_probe.py` | Opt-in helper that emits a fresh uniquely identifiable Logfire probe span for MCP smoke testing |

### Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/.logfire/logfire_credentials.json` | Confirms the current Logfire project URL and region without needing to guess the MCP endpoint |
| `backend/app/main.py` | Shows the current Logfire project wiring and `send_to_logfire="if-token-present"` convention already used by the backend |
| `docs/references/logfire-trace-analysis.md` | Existing project Logfire reference note that already uses the EU project URL and query terminology |
| `docs/superpowers/specs/2026-04-01-item8-logfire-analyst-design.md` | Source of truth for the agent role, workflow, and MCP constraints |

---

## Task 1: Add the project-scoped custom agent file

**Files:**
- Create: `.codex/agents/logfire-analyst.toml`

This task creates the actual custom subagent definition and keeps the Logfire MCP tool surface attached only to that agent.

- [x] **Step 1: Confirm the project wiring decisions**

Resolved choices for implementation:

- agent name: `logfire_analyst`
- file path: `.codex/agents/logfire-analyst.toml`
- sandbox mode: `read-only`
- MCP endpoint: `https://logfire-eu.pydantic.dev/mcp`
- default auth expectation: browser-authenticated remote MCP
- fallback auth path: Bearer API key documented outside the committed file

- [ ] **Step 2: Verify the custom agent file does not exist yet**

Run:

```bash
test -f .codex/agents/logfire-analyst.toml
```

Expected: exit status `1` because the agent file has not been created yet

- [ ] **Step 3: Create the `.codex/agents/` directory and write the agent file**

Create `.codex/agents/logfire-analyst.toml` with a narrow, analysis-only definition.

Recommended content:

```toml
name = "logfire_analyst"
description = "Use when a task depends on analyzing Logfire traces, telemetry, or observability signals and relating them to the checked-out codebase."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Investigate telemetry-heavy questions through Logfire MCP and the local codebase.
Stay in analysis mode.
Distinguish observed telemetry, observed code, and inference.
Report evidence, code-path explanation, ranked hypotheses, remediation options, and eval or observability improvements.
Do not edit code, configuration, or git state.
If MCP authentication or data access fails, say so plainly and continue with repo-only reasoning where possible.
Be explicit about confidence and limits.
Treat Logfire MCP as a narrow, remote-first interactive surface.
If a request appears blocked by MCP age limits or missing tool coverage, say so instead of over-promising.
"""

[mcp_servers.logfire]
url = "https://logfire-eu.pydantic.dev/mcp"
```

Implementation guidance:

- keep the description trigger-focused
- do not add Query API instructions in v1
- do not add auth headers to the committed file
- do not broaden the agent into an implementation worker
- teach the agent to surface confidence and MCP access limits explicitly

- [ ] **Step 4: Parse the TOML and assert the critical fields**

Run:

```bash
python3 - <<'PY'
import pathlib
import tomllib

data = tomllib.loads(pathlib.Path(".codex/agents/logfire-analyst.toml").read_text())
assert data["name"] == "logfire_analyst"
assert data["sandbox_mode"] == "read-only"
assert "Use when" in data["description"]
assert "Do not edit code" in data["developer_instructions"]
assert data["mcp_servers"]["logfire"]["url"] == "https://logfire-eu.pydantic.dev/mcp"
print("ok")
PY
```

Expected: prints `ok`

- [ ] **Step 5: Commit the agent file**

```bash
git add .codex/agents/logfire-analyst.toml
git commit -m "feat: add project-scoped Logfire analyst agent"
```

---

## Task 2: Add the companion reference note

**Files:**
- Create: `docs/references/logfire-analyst.md`

The agent file should stay concise. Put usage guidance, authentication notes, and the isolation caveat into a short reference note that teammates can read without opening the spec.

- [ ] **Step 1: Verify the reference note does not exist yet**

Run:

```bash
test -f docs/references/logfire-analyst.md
```

Expected: exit status `1` because the note has not been created yet

- [ ] **Step 2: Write the companion note**

Create `docs/references/logfire-analyst.md` with these sections:

- `## When to Use`
- `## What It Does`
- `## What It Will Not Do`
- `## Authentication`
- `## Limits`
- `## Isolation`
- `## Example Prompts`

Recommended content direction:

```md
# Logfire Analyst

## When to Use
- telemetry-heavy debugging questions
- trace analysis
- latency investigations
- situations where repo-only reasoning is not enough

## What It Does
- inspects Logfire through MCP
- correlates traces with code
- forms ranked hypotheses
- suggests remediation and eval improvements

## What It Will Not Do
- edit code
- change configuration
- commit fixes

## Authentication
- default: browser-authenticated remote MCP
- sandbox/headless fallback: Bearer API key with `project:read`
- do not commit keys

## Limits
- remote MCP is the only supported access path in v1
- the MCP tool surface is narrow and not a full replacement for the entire Logfire UI
- some investigations may be blocked by MCP time-window or tool-surface limits
- local MCP is deprecated and should not be the default recommendation

## Isolation
- this repo keeps Logfire MCP on the custom agent only
- if your personal `~/.codex/config.toml` already defines Logfire MCP globally, that personal setup overrides the repo’s intended isolation model

## Example Prompts
- "Spawn logfire_analyst and explain why this trace produced these todos."
- "Spawn logfire_analyst and investigate where this request spends time."
```

Implementation guidance:

- mention the EU endpoint for this repo
- explicitly mention the global-config caveat so the user is not surprised by inherited MCP access
- explicitly mention the MCP limits so the agent does not imply full UI parity
- keep the note short enough to scan quickly

- [ ] **Step 3: Validate that the note contains the required sections**

Run:

```bash
rg -n "^## (When to Use|What It Does|What It Will Not Do|Authentication|Limits|Isolation|Example Prompts)$" docs/references/logfire-analyst.md
```

Expected: seven matches, one for each required section

- [ ] **Step 4: Commit the reference note**

```bash
git add docs/references/logfire-analyst.md
git commit -m "docs: add Logfire analyst usage reference"
```

---

## Task 3: Add the Logfire probe emitter

**Files:**
- Create: `backend/scripts/emit_logfire_probe.py`

This task creates a fresh-data smoke helper so the Logfire analyst can be validated against newly emitted telemetry instead of against a fixed trace that falls out of the MCP age window.

The validation must be challenge-response based, not just presence-based. A fresh `probe_id` alone is not enough because an agent could still pretend it found the probe if it knows the expected static fields from the repo.

- [ ] **Step 1: Verify the probe emitter does not exist yet**

Run:

```bash
test -f backend/scripts/emit_logfire_probe.py
```

Expected: exit status `1` because the probe emitter has not been created yet

- [ ] **Step 2: Write the probe emitter**

Create `backend/scripts/emit_logfire_probe.py` as a small standalone script that:

- configures Logfire for this project using the existing send convention
- creates a unique `probe_id`
- creates a separate random `verification_token`
- emits one easily-queryable span with stable identifying attributes
- stores the plaintext `verification_token` only in the emitted telemetry, not in repo files
- prints only a verifier hash, not the plaintext token
- flushes and shuts down Logfire before exit
- prints a small JSON payload to stdout so the next smoke-test step can reuse the probe ID

Recommended implementation shape:

```python
from __future__ import annotations

import json
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import logfire

PROBE_SERVICE = "voice-todos-logfire-probe"
PROBE_SPAN = "codex.logfire_probe"


def main() -> None:
    probe_id = uuid.uuid4().hex
    verification_token = secrets.token_hex(32)
    verification_hash = hashlib.sha256(verification_token.encode()).hexdigest()
    emitted_at = datetime.now(timezone.utc).isoformat()

    logfire.configure(
        service_name=PROBE_SERVICE,
        send_to_logfire="if-token-present",
    )

    with logfire.span(
        PROBE_SPAN,
        probe_id=probe_id,
        probe_kind="logfire_analyst_smoke",
        verification_token=verification_token,
        project_name="voice-todos",
        expected_region="eu",
    ):
        logfire.info("codex.logfire_probe_marker", probe_id=probe_id)

    logfire.force_flush()
    logfire.shutdown()

    print(
        json.dumps(
            {
                "probe_id": probe_id,
                "service_name": PROBE_SERVICE,
                "span_name": PROBE_SPAN,
                "verification_hash": verification_hash,
                "emitted_at": emitted_at,
                "suggested_age_minutes": 15,
            }
        )
    )


if __name__ == "__main__":
    main()
```

Implementation guidance:

- keep the span name and service name stable so the smoke test has unambiguous filters
- keep the `probe_id` unique per run so the query never depends on stale data
- generate the `verification_token` at runtime with `secrets`, not a predictable source
- never print or persist the plaintext `verification_token` outside the emitted telemetry
- print only the verifier hash so the human can validate the retrieved token later
- use `logfire.force_flush()` and `logfire.shutdown()` so short-lived script execution still exports the span
- keep the script opt-in and standalone; do not wire it into the default pytest suite
- document that the script expects working Logfire write auth through the existing project setup, environment token, or equivalent local credentials

- [ ] **Step 3: Run the emitter and verify it prints a probe payload**

Run:

```bash
cd backend && uv run python scripts/emit_logfire_probe.py
```

Expected:

- the command exits successfully in an environment with working Logfire write auth
- stdout is one JSON object containing `probe_id`, `service_name`, `span_name`, `verification_hash`, and `suggested_age_minutes`
- stdout does not reveal the plaintext `verification_token`
- if write auth is missing or broken, the failure is explicit enough for the implementer to diagnose setup instead of silently passing

- [ ] **Step 4: Commit the probe emitter**

```bash
git add backend/scripts/emit_logfire_probe.py
git commit -m "test: add Logfire probe emitter for analyst smoke checks"
```

---

## Task 4: Validate discoverability, telemetry round-trip, and MCP isolation

**Files:**
- Review: `.codex/agents/logfire-analyst.toml`
- Review: `docs/references/logfire-analyst.md`
- Review: `backend/scripts/emit_logfire_probe.py`

This task verifies the implementation behaves like the spec says: project-scoped, read-only, discoverable, able to retrieve fresh telemetry through MCP, and honest about auth failures.

- [ ] **Step 1: Confirm the repo does not define a parent-level Logfire MCP server**

Run:

```bash
test ! -f .codex/config.toml || ! rg -n "^\[mcp_servers\.logfire\]$" .codex/config.toml
```

Expected: success, meaning this repo does not define a project-level parent MCP server for Logfire

- [ ] **Step 2: Re-check the final agent config**

Run:

```bash
python3 - <<'PY'
import pathlib
import tomllib

data = tomllib.loads(pathlib.Path(".codex/agents/logfire-analyst.toml").read_text())
print(data["name"])
print(data["description"])
print(data["mcp_servers"]["logfire"]["url"])
PY
```

Expected:

- first line: `logfire_analyst`
- second line: a trigger-focused description
- third line: `https://logfire-eu.pydantic.dev/mcp`

- [ ] **Step 3: Run a fresh-session discoverability smoke test**

In a fresh Codex session rooted at this repo, prompt:

```text
Spawn the logfire_analyst agent and have it summarize its job in three bullets.
```

Expected:

- Codex recognizes the custom agent name
- the agent spawns successfully
- the response stays in analysis-only mode and does not propose editing code directly
- the response mentions Logfire/telemetry plus code-path correlation, not generic implementation help

- [ ] **Step 4: Emit a fresh Logfire probe**

Run:

```bash
cd backend && uv run python scripts/emit_logfire_probe.py
```

Expected:

- stdout includes a fresh `probe_id`
- stdout includes `span_name` = `codex.logfire_probe`
- stdout includes `service_name` = `voice-todos-logfire-probe`
- stdout includes `verification_hash` but not the plaintext token
- the probe is fresh enough to fit comfortably inside the MCP age window

- [ ] **Step 5: Run a fresh-session MCP retrieval smoke test using that probe ID**

In that same fresh session, prompt:

```text
Spawn logfire_analyst and ask it to use Logfire MCP to find the most recent probe emitted by this run with probe_id=<PASTE_PROBE_ID>, confirm the service name and span name, and return the span attribute verification_token exactly. If it cannot access the data, it must report the auth/setup blocker plainly.
```

Run this in an environment where browser-authenticated remote MCP can actually complete, or be prepared for the auth-blocked branch below.

Expected:

- if browser auth is already available, the agent identifies the exact `probe_id`
- if browser auth is available, the agent reports `voice-todos-logfire-probe` and `codex.logfire_probe`
- if browser auth is available, the agent returns a plaintext `verification_token`
- if browser auth is available, that token is not guessable from the repo because only its hash was printed locally
- if auth is not available, the agent reports the auth/setup blocker clearly instead of hallucinating telemetry access

- [ ] **Step 6: Verify the returned token matches the printed verifier hash**

Run:

```bash
python3 - <<'PY'
import hashlib

returned_token = "<PASTE_RETURNED_TOKEN>"
expected_hash = "<PASTE_VERIFICATION_HASH>"
assert hashlib.sha256(returned_token.encode()).hexdigest() == expected_hash
print("ok")
PY
```

Expected:

- prints `ok` when the agent truly retrieved the token from Logfire
- fails if the agent guessed, hallucinated, or returned the wrong value

- [ ] **Step 7: If validation exposed any wording or setup gaps, make the smallest doc/config fix and rerun the affected validation steps**

Possible follow-up commands if a wording-only fix is needed:

```bash
git add .codex/agents/logfire-analyst.toml docs/references/logfire-analyst.md
git commit -m "docs: refine Logfire analyst setup and wording"
```
