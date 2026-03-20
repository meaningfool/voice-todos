# Soniox STT — Usage Reference

How we use Soniox in voice-todos.

## Connection

- **WebSocket:** `wss://stt-rt.soniox.com/transcribe-websocket`
- **Model:** `stt-rt-v4`
- **Audio:** `pcm_s16le`, 16kHz, mono
- We use the raw WebSocket protocol (not the Python SDK's session API) because FastAPI bridges browser audio to Soniox.

## Context

We pass a `context.general` topic description so the model understands the user is dictating tasks. This helps with word disambiguation (e.g., "todo" vs "tuto"). See `backend/app/ws.py` for the current config.

Context options (see [docs](https://soniox.com/docs/stt/concepts/context)):
- **`general`** — structured `{key, value}` pairs, most influential. We use this.
- **`text`** — free-form paragraph, less influential. Good for longer background.
- **`terms`** — array of words to boost. Use when specific jargon is misrecognized.

Max context size: 8,000 tokens (~10,000 chars).

## Language

No language hints set — Soniox auto-detects. Add `language_hints` if needed later.

## Parameters for Later Items

- `enable_endpoint_detection` — speech boundary detection (Item 3)
- `max_endpoint_delay_ms` — 500-3000ms end-of-speech delay, v4 only (Item 3)

## Docs

- [Context](https://soniox.com/docs/stt/concepts/context)
- [WebSocket API](https://soniox.com/docs/stt/api-reference/websocket-api)
- [Models](https://soniox.com/docs/stt/models)
- [Python SDK](https://soniox.com/docs/stt/SDKs/python-SDK)
