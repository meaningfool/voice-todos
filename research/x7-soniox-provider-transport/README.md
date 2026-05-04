# Spike X7: Soniox Provider Transport

This spike proves the outbound Soniox transport inside a Python Durable Object.

## Run

1. Put `SONIOX_API_KEY` in `.dev.vars` next to `wrangler.jsonc`.
2. Install dependencies:

```bash
uv sync
```

3. Start local dev:

```bash
uv run pywrangler dev --port 8789
```

4. POST a base64-encoded PCM fixture to:

- `POST http://127.0.0.1:8789/prove-soniox?finalize=1`
- `POST http://127.0.0.1:8789/prove-soniox?finalize=0`

## What it proves

- a Python Durable Object can open an outbound Soniox WebSocket
- binary audio frames can be streamed from the Durable Object
- finalize and EOS ordering can be tested inside the Cloudflare runtime
- Soniox token and finalization responses can be collected from the Durable Object

## What it does not prove

- browser-to-Worker live integration
- extraction logic
- final shared-core integration
