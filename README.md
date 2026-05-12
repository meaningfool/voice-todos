# voice-todos

Browser-based voice-to-todo demo with two runtime paths:

- a local FastAPI + React development path
- a Cloudflare-hosted path for the public demo

The core app flow is simple: stream audio, build transcript state, extract todos, and show the current best todo snapshot in the UI.

## Repo Map

- `frontend/`: React app
- `backend/`: local FastAPI runtime, extraction code, and backend test suite
- `cloudflare/`: hosted runtime and public deploy runbook
- `evals/`: benchmark definitions, locks, reports, and CLI entrypoints
- `docs/references/`: durable architecture and operator guidance
- `research/`: dated notes, spike findings, and historical investigations

## Local Quick Start

Prerequisites:

- Python `3.11+` with `uv`
- Node.js with `pnpm`

1. Create `backend/.env` with the keys you need for local runs.
2. Optionally copy `.env.dev.example` to `.env.dev` for repo-local non-secret toggles.
3. Install dependencies:

```bash
cd backend && uv sync
cd ../frontend && pnpm install
```

4. Start the local app:

```bash
./scripts/dev.sh
```

5. Open `http://localhost:5173`.

Required keys for the standard local Soniox + Gemini path:

- `SONIOX_API_KEY`
- `GEMINI_API_KEY`

Optional keys:

- `MISTRAL_API_KEY`
- `LOGFIRE_READ_TOKEN`
- `LOGFIRE_DATASETS_TOKEN`
- `LOGFIRE_TOKEN`
- `GOOGLE_CLOUD_PROJECT_ID`

For credential storage conventions, see [docs/references/2026-04-13-credential-storage-and-logfire-access.md](docs/references/2026-04-13-credential-storage-and-logfire-access.md).

## Validation

Backend tests:

```bash
cd backend && uv run pytest
```

Frontend tests:

```bash
cd frontend && pnpm test:run
```

Deterministic browser smoke:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:5173 while-speaking-two-todos
```

## Deployment

The public Cloudflare deployment path is documented in [cloudflare/README.md](cloudflare/README.md).

## Evals

The benchmark-first eval surface is documented in [evals/README.md](evals/README.md).
