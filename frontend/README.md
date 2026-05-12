# Frontend

React + Vite frontend for the voice-todos app.

## Development

From `frontend/`:

```bash
pnpm install
pnpm dev
```

The dev server defaults to `http://localhost:5173`.

WebSocket traffic to `/ws` is proxied during development:

- `WS_BACKEND=fastapi` routes to the local FastAPI runtime on `BACKEND_PORT`
- `WS_BACKEND=cloudflare` routes to the local Cloudflare runtime on `CLOUDFLARE_PORT`

The repo-level helper starts the standard local stack together:

```bash
./scripts/dev.sh
```

## Fixture Smoke Mode

The app supports deterministic fixture playback for browser smoke tests.

Example:

```bash
http://localhost:5173/?fixture=while-speaking-two-todos
```

## Commands

```bash
pnpm build
pnpm test:run
pnpm lint
pnpm fmt:check
```
