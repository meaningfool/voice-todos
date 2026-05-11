# Public Cloudflare Deploy Runbook

This directory is the public deploy boundary for the Cloudflare-hosted app.

## Required Inputs

Required secrets must exist in `backend/.env`:

- `SONIOX_API_KEY`
- `GEMINI_API_KEY`
- `MISTRAL_API_KEY`

Required non-secret runtime config:

- `STT_PROVIDER=soniox`

The deploy script injects `STT_PROVIDER=soniox` automatically. Do not override
it for the first public deploy.

Optional non-secret runtime config:

- `SESSION_CAP_MS`
- `STOP_TIMEOUT_SECONDS`

If omitted, the hosted runtime defaults are:

- `SESSION_CAP_MS=60000`
- `STOP_TIMEOUT_SECONDS=30.0`

## One-Time Cloudflare Auth

Authenticate Wrangler on this machine before the first publish:

```bash
cd cloudflare
uv run pywrangler login
uv run pywrangler whoami
```

## Pre-Publish Smoke

This is the required pre-publish smoke.

Local Cloudflare smoke is a required prerequisite. Run the real app boundary,
not Vite alone.

Terminal A:

```bash
cd frontend
pnpm build
cd ../cloudflare
./scripts/sync_frontend_dist.sh
set -a && source ../backend/.env && set +a
uv run pywrangler dev --port 8788
```

Terminal B, from repo root:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Required result:

- the smoke exits `0`
- the final transcript matches the accepted fixture
- the final todo list matches the accepted fixture
- no visible warning card is present

## Public Deploy

Set the public hostname first:

```bash
export PUBLIC_APP_DOMAIN=voice-todos.meaningfool.net
```

Run the single accepted deploy command:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN"
```

Optional overrides can be passed at publish time:

```bash
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN" \
  --session-cap-ms 60000 \
  --stop-timeout-seconds 30.0
```

What this command owns:

- builds `frontend/`
- syncs the built assets into `cloudflare/public/`
- uploads required Cloudflare secrets from `backend/.env`
- publishes the Worker on the custom domain

Current account note:

- if Cloudflare rejects the publish with a `3 MiB` Worker size-limit error, the
  account is still on the free Worker plan
- the immediate operator fix is upgrading the Worker plan so the deployment can
  use the higher paid-plan size limit
- the engineering alternative is shrinking the Cloudflare runtime bundle in a
  follow-up slice

## Post-Deploy Smoke

This is the required post-deploy smoke.

Public deployment is not complete until the public app passes the deterministic
browser smoke.

From repo root:

```bash
./scripts/browser_ui_smoke.sh "https://$PUBLIC_APP_DOMAIN" while-speaking-two-todos
```

Required result:

- the smoke exits `0`
- the public app reaches the expected final transcript
- the public app reaches the expected final todo list
- no visible warning card is present

## Diagnose

Use Cloudflare tail logs against the deployed Worker:

```bash
cd cloudflare && uv run pywrangler tail voice-todos-cloudflare --format pretty
```

If a public smoke fails, collect:

- the exact smoke command
- the public URL
- the observed transcript and todo output from the smoke
- the relevant `pywrangler tail` output around the failing run

## Recovery

The lightweight recovery path is redeploying a previous known-good commit.

Example:

```bash
git switch --detach <known-good-commit>
cd cloudflare && uv run python scripts/deploy_public_app.py \
  --public-domain "$PUBLIC_APP_DOMAIN"
```

After recovery, rerun the required public smoke:

```bash
./scripts/browser_ui_smoke.sh "https://$PUBLIC_APP_DOMAIN" while-speaking-two-todos
```

## Mistral Note

[2026-05-07-mistral-live-validation-findings.md](/Users/josselinperrus/conductor/workspaces/voice-todos/marseille/docs/references/2026-05-07-mistral-live-validation-findings.md:1)
is linked context only. It does not block the first public deploy because the
deploy contract for this slice is Soniox-based.
