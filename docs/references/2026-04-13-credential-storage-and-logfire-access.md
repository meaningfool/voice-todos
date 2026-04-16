# Credential Storage And Logfire Access

This repo uses a file-backed credential model so Conductor worktrees and coding
sessions behave consistently without relying on ad-hoc shell exports.

## Storage Contract

- `backend/.env`
  - canonical shared store for provider secrets and repo-managed Logfire tokens
  - shared across Conductor worktrees via the symlink created by
    `scripts/conductor-setup.sh`
- `backend/.logfire/logfire_credentials.json`
  - canonical shared store for CLI-managed Logfire credentials metadata
  - also shared across Conductor worktrees via `scripts/conductor-setup.sh`
- `.env.dev`
  - repo-local non-secret toggles only
  - examples: `BENCHMARK_ENABLE_LIVE_SMOKE=1`
- shell `export ...`
  - temporary override only
  - never the intended persistent setup

Because `backend/.env` is a symlink in Conductor worktrees, editing
`backend/.env` from any worktree edits the shared root-checkout file.

## Recommended Persistent Keys

Keep these in the shared `backend/.env` when needed:

- `SONIOX_API_KEY`
- `GEMINI_API_KEY`
- `MISTRAL_API_KEY`
- `DEEPINFRA_API_KEY`
- `LOGFIRE_READ_TOKEN`
- `LOGFIRE_DATASETS_TOKEN`
- `LOGFIRE_TOKEN` only if you intentionally want repo-managed write credentials

Keep these in `backend/.logfire/logfire_credentials.json`:

- `token`
- `project_name`
- `project_url`
- `logfire_api_url`

Keep these in `.env.dev`:

- `BENCHMARK_ENABLE_LIVE_SMOKE`
- similar local opt-in flags

## Logfire Credential Roles

- `LOGFIRE_READ_TOKEN`
  - used for Logfire queries and benchmark reporting
- `LOGFIRE_DATASETS_TOKEN`
  - dataset-scoped API key for hosted dataset CRUD
  - required for bootstrap and later hosted dataset updates
- `LOGFIRE_TOKEN`
  - write token for sending traces when you choose to manage that token in
    `backend/.env`
- `.logfire/logfire_credentials.json`
  - CLI-managed fallback for Logfire write credentials and project metadata

Do not assume the `.logfire` token has hosted dataset scopes. Hosted dataset
access should use a dedicated dataset-scoped API key in `LOGFIRE_DATASETS_TOKEN`.

## Precedence

Runtime helpers in this repo generally resolve values in this order:

1. exported environment variable
2. `backend/.env`
3. `backend/.logfire/logfire_credentials.json` for Logfire project/write
   fallbacks only

`.env.dev` is only for repo-level non-secret toggles and is read separately.

## Conductor Workflow

1. Create or update the shared root-checkout `backend/.env`.
2. Re-run `scripts/conductor-setup.sh` if a worktree is missing the symlink.
3. Keep `.env.dev` for non-secret opt-in flags only.
4. Avoid one-off exports unless you intentionally want a temporary override for
   the current shell session.

## Adding The Hosted Dataset Key

To make hosted dataset bootstrap reproducible in all worktrees:

1. create a Logfire API key with dataset scopes
   - `project:read_datasets`
   - `project:write_datasets`
2. add it to the shared `backend/.env` as:

```bash
LOGFIRE_DATASETS_TOKEN=...
```

After that, any Conductor worktree that symlinks `backend/.env` will inherit the
same dataset access automatically.
