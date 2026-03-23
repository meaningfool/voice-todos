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

## Ending a Stream

Three distinct control signals — order matters:

1. **`{"type": "finalize"}`** — Forces all pending interim tokens to be emitted as `is_final: true`, followed by a `<fin>` marker token (`{"text": "<fin>", "is_final": true}`). The session stays open. **You must send this before ending the stream**, otherwise any tokens still in interim state are silently dropped.

2. **`b""`** (empty binary frame) — Signals "no more audio". Soniox responds with `{"tokens": [], "finished": true}`. Does NOT finalize pending tokens.

3. **Close the WebSocket** — Tears down the session.

**Correct stop sequence:** `finalize` → wait for `<fin>` token → `b""` → wait for `finished: true` → close.

**Without finalize**, the RT model only finalizes tokens when enough subsequent audio context arrives (lookahead). For short utterances or speech that runs right up to the end of the stream, trailing words stay interim and are lost when `b""` arrives.

The `<fin>` token must be filtered out of the transcript. After `<fin>`, all interim state is stale and must be discarded.

See [Manual Finalization](https://soniox.com/docs/stt/rt/manual-finalization).

## Gotchas

- **Auth is not checked at connection time.** Soniox accepts the WebSocket connection and the initial config message even with an invalid API key. The failure comes later (when streaming audio or receiving results), not on connect. This means you can't rely on a connection error to detect a bad key — you need to watch for errors during the streaming phase.

- **Finalize vs Finish are independent.** Sending `b""` does not finalize. Sending `finalize` does not end the stream. You need both.

- **Stale interim after finalize.** After finalize promotes all tokens to final, any previously tracked interim text is stale. If you append interim to finals (as a fallback), you must clear it when you see `<fin>`, or you'll get duplicated text.

## Parameters for Later Items

- `enable_endpoint_detection` — speech boundary detection (Item 3)
- `max_endpoint_delay_ms` — 500-3000ms end-of-speech delay, v4 only (Item 3)

## Docs

- [Context](https://soniox.com/docs/stt/concepts/context)
- [Manual Finalization](https://soniox.com/docs/stt/rt/manual-finalization)
- [Endpoint Detection](https://soniox.com/docs/stt/rt/endpoint-detection)
- [WebSocket API](https://soniox.com/docs/stt/api-reference/websocket-api)
- [Models](https://soniox.com/docs/stt/models)
- [Python SDK](https://soniox.com/docs/stt/SDKs/python-SDK)
