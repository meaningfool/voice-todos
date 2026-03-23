# Handoff: Interim Text Loss + Testing Infrastructure

## What we built

Item 2 of voice-todos: when the user clicks Stop, the full transcript is sent to Gemini 3 Flash via PydanticAI, which extracts structured todos displayed as cards below the transcript.

Branch: `feat/item2-extract-todos`

## The bug we're investigating

When the user clicks Stop, the last 1-2 words they spoke often disappear from the transcript. They don't appear as final OR interim tokens — Soniox never processes them.

### Root cause (confirmed)

Soniox streams tokens progressively: first as interim (tentative), then as final (confirmed). When the audio stream ends (backend sends empty frame to Soniox), Soniox sends a `{"finished": true}` message. But tokens at the tail end of speech may never be finalized — they exist only as interim tokens.

### Fix applied (needs user verification)

In `backend/app/ws.py`, the transcript accumulation now **appends** the last interim text to the final text, instead of only using interim as a fallback when finals are completely empty:

```python
full_transcript = "".join(transcript_parts)
if interim_parts:
    full_transcript += "".join(interim_parts)
```

The same logic is mirrored in `backend/tests/test_replay.py::_accumulate_transcript`.

On the frontend (`frontend/src/hooks/useTranscript.ts`), when the `stopped` message arrives, remaining `interimText` is promoted to `finalText` so the transcript stays visible:

```typescript
if (interimTextRef.current) {
    setFinalText((prev) => prev + interimTextRef.current);
    interimTextRef.current = "";
}
```

### What we disproved

We initially hypothesized that audio bytes were being dropped between the browser's AudioWorklet and the WebSocket (i.e., the worklet had buffered audio that never reached `ws.send()`). We added a 300ms flush delay before sending the stop signal.

We built an integration test using `agent-browser` with Chrome's fake audio (OscillatorNode injected via `eval`) that counts bytes on both sides. **The test showed 0 bytes difference with and without the delay.** Audio bytes are NOT lost — `workletNode.disconnect()` doesn't prevent pending `port.postMessage` messages from being delivered.

The 300ms delay has been removed. The stop sequence is back to synchronous.

## Testing infrastructure built

### Session recording (`backend/app/session_recorder.py`)
Every WebSocket session automatically records:
- `audio.pcm` — raw audio bytes received from browser
- `soniox.jsonl` — all Soniox messages (tokens, finished)
- `result.json` — final transcript + extracted todos

Stored in `sessions/recent/` (last 10 kept, gitignored). Test fixtures are copied to `backend/tests/fixtures/`.

### Replay tests (`backend/tests/test_replay.py`)
Replays recorded `soniox.jsonl` through the accumulation logic without needing a mic or Soniox API:
- `test_transcript_not_empty` — every fixture produces a transcript
- `test_result_matches_transcript` — accumulated text matches saved result
- `test_interim_tail_is_not_lost` — verifies trailing interim text ("Wednesday") is appended

### Audio replay script (`scripts/replay_audio.py`)
Sends recorded `audio.pcm` through the real backend WebSocket → real Soniox → real Gemini extraction. True end-to-end test. Usage:
```bash
cd backend && uv run python ../scripts/replay_audio.py [path/to/audio.pcm]
```

### Audio pipeline test (`scripts/test_audio_pipeline.sh`)
Uses `agent-browser --engine chrome` with an injected OscillatorNode to verify all audio bytes flow through the real browser pipeline to the backend. Compares browser-side byte counter vs backend's `audio.pcm` size.

### Dev server script (`scripts/dev.sh`)
Starts/stops both servers on fixed ports (backend :8000, frontend :5173 with strictPort).

### agent-browser
Installed globally with Chrome engine. Can open the app, inspect elements, click buttons, read page state. Skill installed in `.claude/skills/agent-browser`.

## Current state

- The user needs to manually test whether the interim tail fix resolves their word loss issue
- All automated tests pass (18 backend + 18 frontend = 36)
- The stop sequence is synchronous (no delay) — this is correct per our findings
- Session recording is active — any manual test will produce a new session in `sessions/recent/` that can be inspected

## Key files

- `backend/app/ws.py` — WebSocket handler with transcript accumulation + session recording
- `backend/app/extract.py` — PydanticAI extraction (gemini-3-flash-preview)
- `backend/app/session_recorder.py` — session recording
- `backend/tests/test_replay.py` — replay tests
- `backend/tests/fixtures/call-mom-memo-supplier/` — golden test fixture
- `frontend/src/hooks/useTranscript.ts` — hook with interim text promotion
- `frontend/src/App.tsx` — wires TodoList/TodoSkeleton
- `scripts/dev.sh` — start/stop dev servers
- `scripts/replay_audio.py` — audio replay to Soniox
- `scripts/test_audio_pipeline.sh` — browser pipeline byte test
