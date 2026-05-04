# Spike X6: Local Cloudflare Session Skeleton

This is an isolated Python Worker + Durable Object prototype for the selected
Cloudflare shape `B`.

## Run

```bash
uv sync
uv run pywrangler dev --port 8788
```

Then open:

- `http://127.0.0.1:8788/`

## What it proves

- Worker `/ws` ingress works locally in the simulated Cloudflare runtime
- one Durable Object can own one browser session
- browser WebSocket messages can drive a session lifecycle
- the Durable Object can send `started`, `transcript`, `todos`, and `stopped`
- a server-side session cap can end the session cleanly

## What it does not prove

- real Soniox outbound transport
- real extraction logic
- shared-core integration with the current backend
