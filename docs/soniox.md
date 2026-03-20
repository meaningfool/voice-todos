# Soniox STT — Usage Reference

How we use Soniox in voice-todos, and what we've learned.

## Connection

- **Protocol:** WebSocket — `wss://stt-rt.soniox.com/transcribe-websocket`
- **Model:** `stt-rt-v4` (strongest context support)
- **Audio format:** `pcm_s16le`, 16kHz, mono
- **Python SDK:** `soniox` (pip/uv). We use the raw WebSocket protocol directly (not the SDK's session API) because our FastAPI server bridges browser audio to Soniox.

## Context Customization

Soniox supports a `context` object in the initial WebSocket config message. This is the main tool for improving transcription accuracy in our domain. The entire context must fit within 8,000 tokens (~10,000 characters).

### `context.terms` — Domain vocabulary

Array of strings. Words the model should prefer when audio is ambiguous. This is the most impactful setting for us.

```json
"terms": ["todo", "todos"]
```

**Insight:** Without this, Soniox transcribed "todo" as "tuto" in French speech. Adding the term fixed it. Add new terms here as we discover misrecognitions.

### `context.general` — Structured metadata

Array of `{key, value}` objects. Keep to ~10 pairs. Helps the model understand the domain.

```json
"general": [
  { "key": "domain", "value": "Task management" },
  { "key": "topic", "value": "Voice-driven todo list application" }
]
```

### `context.text` — Free-form background

A string with paragraph-level background. Least influential but useful for longer reference material.

### `context.translation_terms` — Not used (translation only)

## Language Settings

| Parameter | Value | Why |
|-----------|-------|-----|
| `language_hints` | `["fr"]` | Primary user speaks French |
| `language_hints_strict` | `true` | Prevents wrong-language guesses |

Adjust `language_hints` if the app needs to support other languages later.

## Other Useful Parameters

| Parameter | Type | Purpose |
|-----------|------|---------|
| `enable_endpoint_detection` | bool | Detect speech boundaries (relevant for Item 3) |
| `max_endpoint_delay_ms` | int | 500-3000ms end-of-speech delay (v4 only) |
| `enable_speaker_diarization` | bool | Label different speakers (not needed yet) |
| `enable_language_identification` | bool | Auto-detect language (off — we use strict hints) |

## Current Config in Code

See `backend/app/ws.py` — the `soniox_config` dict is built inside the WebSocket endpoint handler. Update it there when changing Soniox settings.

## Docs

- [Context](https://soniox.com/docs/stt/concepts/context)
- [WebSocket API](https://soniox.com/docs/stt/api-reference/websocket-api)
- [Models](https://soniox.com/docs/stt/models)
