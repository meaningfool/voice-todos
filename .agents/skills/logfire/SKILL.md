---
name: logfire
description: Use when working with Logfire in this project: querying traces or spans, investigating latency or model usage, checking Logfire credentials, using the Logfire CLI, configuring or debugging the Codex Logfire MCP server, hosted eval datasets, or benchmark Logfire enrichment.
---

# Logfire In Voice Todos

Use this skill for Logfire work in this repo. Keep secrets redacted. Do not print token values.

## Current Project Map

Important files:

- `backend/.env`: repo-local secrets loaded by backend helpers.
- `backend/.logfire/logfire_credentials.json`: Logfire CLI/project metadata and fallback token.
- `.codex/config.toml`: project-level Codex MCP config.
- `/Users/josselinperrus/.codex/config.toml`: global Codex config.
- `/Users/josselinperrus/.logfire/default.toml`: Logfire CLI user-auth store.

Current expected credential roles:

- `LOGFIRE_READ_TOKEN`: Query API read token. Used for trace/span SQL queries and benchmark report enrichment.
- `LOGFIRE_DATASETS_TOKEN`: hosted dataset API key. Used for eval dataset CRUD/bootstrap/export.
- `LOGFIRE_TOKEN`: write token for sending telemetry, if explicitly managed in `backend/.env`.
- `backend/.logfire/logfire_credentials.json.token`: CLI-managed fallback/project token. Do not assume it has dataset scopes.
- `LOGFIRE_MCP_TOKEN`: bearer token expected by this repo's project-level Codex MCP config.

## Safe Inspection

Use redacted checks:

```bash
rg -n "LOGFIRE|logfire" backend/.env backend/.logfire/logfire_credentials.json .codex/config.toml /Users/josselinperrus/.codex/config.toml
jq 'keys' backend/.logfire/logfire_credentials.json
jq '{project_name, project_url, logfire_api_url, token_present:(.token!=null)}' backend/.logfire/logfire_credentials.json
codex mcp list --json
```

Do not run `cat backend/.env` or print token values.

## Choosing API, CLI, Or MCP

Use the **Query API** for deterministic trace/span data:

- last session analysis
- model usage and token/cost data
- latency breakdowns
- benchmark report enrichment
- arbitrary SQL against `records`

Use `evals/logfire_query.py` or direct HTTP with:

- `Authorization: Bearer $LOGFIRE_READ_TOKEN`
- endpoint from `backend/.logfire/logfire_credentials.json.logfire_api_url`, usually `https://logfire-eu.pydantic.dev`
- `project_name` from repo helpers/credentials

Avoid hardcoding the default US API endpoint. EU tokens must query the EU endpoint.

Use the **CLI** for setup/admin:

- `logfire auth`: browser/device login, stored under `~/.logfire/default.toml`.
- `logfire whoami`: show current auth/project info.
- `logfire projects list/new/use`: project management.
- `logfire read-tokens --project meaningfool/voice-todos create`: create read tokens.
- `logfire prompt --project meaningfool/voice-todos ...`: get an investigation prompt and optionally configure MCP.
- `logfire info` / `--version`: package and platform info.
- `logfire inspect`: recommend missing instrumentation packages.
- `logfire clean`: remove local Logfire data files.
- `logfire run`: run Python with Logfire instrumentation.

Logfire CLI 4.29.0 has no general SQL query command. Use Query API or MCP for query data.

Use **MCP** when available for interactive agent investigation:

- schema lookup
- arbitrary Logfire SQL queries
- exception/span context lookup
- trace investigation from an agent

The project-level MCP config currently uses hosted remote MCP:

```toml
[mcp_servers.logfire]
url = "https://logfire-eu.pydantic.dev/mcp"
bearer_token_env_var = "LOGFIRE_MCP_TOKEN"
```

If tools are unavailable, check whether `LOGFIRE_MCP_TOKEN` is set in the environment Codex sees. A hosted MCP token should be a Logfire API key with at least `project:read` scope.

## Known Version Caveats

The repo currently has Logfire CLI `4.29.0`.

- Correct read-token command shape:
  `logfire read-tokens --project meaningfool/voice-todos create`
- Incorrect shape:
  `logfire read-tokens create --project meaningfool/voice-todos`
- Running `logfire read-tokens create` without `--project` can crash with an internal `AttributeError` instead of a helpful argparse error.
- `logfire prompt --codex` in 4.29.0 writes old local stdio MCP config:
  `command = "uvx"`, `args = ["logfire-mcp@latest"]`, `env = { "LOGFIRE_READ_TOKEN" = "..." }`.
- Current Logfire docs and upstream work have moved toward hosted remote MCP using `url = ".../mcp"`.
- Never mix `url = ...` with `command`/`args` in the same `[mcp_servers.logfire]` section; Codex rejects that as `url is not supported for stdio`.

## Investigation Workflow

1. Identify the question: trace timing, model usage, eval dataset, CLI auth, or MCP setup.
2. Inspect active credentials and MCP config with redacted commands.
3. Prefer MCP if Logfire MCP tools are already available in the session.
4. If MCP is unavailable, use Query API with `LOGFIRE_READ_TOKEN` and the configured EU endpoint.
5. Use CLI only for auth/setup/project/token/prompt tasks, not for SQL trace retrieval.
6. Report which credential path was used and whether any token/env mismatch remains.
