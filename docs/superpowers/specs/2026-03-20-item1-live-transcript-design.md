# Item 1 Design: Live Transcript in Browser

Scope: Item 1 from the roadmap. The user opens the web app, clicks Start, speaks, and sees their words appear as a live transcript on screen. Clicks Stop when done. No todo extraction — just proof that live voice-to-text works end-to-end.

## Stack

- **Frontend:** React + Vite (TypeScript)
- **Backend:** FastAPI (Python)
- **STT:** Soniox, model `stt-rt-v4`, WebSocket streaming API
- **No database, no auth, no extraction** — those are Item 2+

## Architecture

```
Browser (React)  ←— WebSocket —→  FastAPI  ←— WebSocket —→  Soniox Cloud
```

Single WebSocket between browser and server carries:
- Start/stop control signals (JSON)
- Audio frames upstream (binary)
- Transcript tokens downstream (JSON)

FastAPI manages the Soniox session — opens the Soniox WebSocket on start, relays audio and transcript tokens, closes on stop.

### Sequence

1. User clicks **Start** → browser opens WebSocket to FastAPI
2. FastAPI opens WebSocket to Soniox, sends config (model, audio format)
3. Browser captures mic via `getUserMedia`, sends audio frames to FastAPI
4. FastAPI relays audio frames to Soniox
5. Soniox returns transcript tokens (interim + final) → FastAPI relays to browser
6. Browser renders tokens — interim text updates in place, final text locks in
7. User clicks **Stop** → browser sends stop signal → FastAPI closes Soniox session

## Project Structure

```
voice-todos/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, startup
│   │   ├── ws.py            # WebSocket endpoint (browser ↔ Soniox bridge)
│   │   └── config.py        # Soniox API key, settings
│   └── .env                 # SONIOX_API_KEY
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── hooks/
│       │   └── useTranscript.ts
│       └── components/
│           ├── TranscriptArea.tsx
│           └── RecordButton.tsx
├── .gitignore
└── roadmap.md
```

## WebSocket Protocol

### Browser → Server

| Message | Format | When |
|---------|--------|------|
| Start | `{ "type": "start" }` | User clicks Start |
| Audio | Binary frames (raw PCM or WebM/Opus) | While recording |
| Stop | `{ "type": "stop" }` | User clicks Stop |

### Server → Browser

| Message | Format | When |
|---------|--------|------|
| Started | `{ "type": "started" }` | Soniox session ready |
| Transcript | `{ "type": "transcript", "tokens": [{ "text": "...", "is_final": bool }] }` | As Soniox returns results |
| Stopped | `{ "type": "stopped" }` | Session closed cleanly |
| Error | `{ "type": "error", "message": "..." }` | Something went wrong |

## Frontend State

### `useTranscript` hook

```
State:
  status: "idle" | "connecting" | "recording" | "stopping"
  finalText: string        # Confirmed text, appended as tokens finalize
  interimText: string      # Unconfirmed text, replaced on each message
```

### State transitions

- `idle` → click Start → `connecting` → receive `started` → `recording`
- `recording` → click Stop → `stopping` → receive `stopped` → `idle`
- Any state → receive `error` → `idle`

### Components

**RecordButton:**
- `idle` → "Start" (enabled)
- `connecting` → "Connecting..." (disabled)
- `recording` → "Stop" (enabled, visually distinct — red/pulsing)
- `stopping` → "Stopping..." (disabled)

**TranscriptArea:**
- Renders `finalText` + `interimText`
- Interim text is visually dimmed (lighter color or italic)

## Audio Format

Browser captures audio via `getUserMedia`. The exact encoding (raw PCM 16-bit 16kHz mono, or WebM/Opus) will be determined by what's simplest to capture in the browser and accepted by Soniox's WebSocket API. An `AudioWorklet` may be needed for raw PCM; `MediaRecorder` works for WebM/Opus.

## Out of Scope

- Todo extraction (Item 2)
- Turn detection / automatic slicing (Item 3)
- Tentative/confirmed todo states (Item 4)
- Error handling beyond basic connection errors
- Mobile support
- Authentication
- Persistence
