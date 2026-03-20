# Item 1: Live Transcript in Browser — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** User opens web app, clicks Start, speaks, and sees their words appear as a live transcript. Clicks Stop when done.

**Architecture:** React+Vite frontend connects via WebSocket to a FastAPI backend, which bridges to Soniox's real-time STT WebSocket. Audio flows browser→server→Soniox, transcript tokens flow Soniox→server→browser.

**Tech Stack:** React 19, Vite, TypeScript, FastAPI, websockets (Python), soniox Python SDK, PCM audio via AudioWorklet. **Tooling:** uv (Python), pnpm (JS).

**Spec:** `docs/superpowers/specs/2026-03-20-item1-live-transcript-design.md`

---

## File Map

```
voice-todos/
├── backend/
│   ├── pyproject.toml              # Python deps: fastapi, uvicorn, websockets, soniox
│   ├── .env                        # SONIOX_API_KEY=...
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, CORS config, mount ws router
│   │   ├── config.py               # Settings via pydantic-settings, reads .env
│   │   └── ws.py                   # WebSocket endpoint: browser ↔ Soniox bridge
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py          # Config loads from env
│       └── test_ws.py              # WebSocket endpoint tests with mock Soniox
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts              # Dev server proxy for /ws to backend
│   ├── index.html
│   └── src/
│       ├── main.tsx                # Entry point
│       ├── App.tsx                 # Layout: RecordButton + TranscriptArea
│       ├── hooks/
│       │   └── useTranscript.ts    # WebSocket connection + transcript state machine
│       └── components/
│           ├── RecordButton.tsx     # Start/Stop button, reads status
│           └── TranscriptArea.tsx   # Renders final + interim text
├── .gitignore
└── roadmap.md
```

---

## Task 1: Gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
# Backend
backend/.venv/
backend/.env
backend/__pycache__/
backend/**/__pycache__/
backend/*.egg-info/

# Frontend
frontend/node_modules/
frontend/dist/

# IDE
.idea/
.vscode/
*.swp

# Superpowers
.superpowers/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add gitignore for backend, frontend, and IDE files"
```

---

## Task 2: Backend project scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/.env`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Initialize backend project with uv**

```bash
cd backend
uv init --name voice-todos-backend --python ">=3.11"
uv add fastapi "uvicorn[standard]" websockets soniox pydantic-settings
uv add --dev pytest pytest-asyncio httpx
```

This creates `pyproject.toml` and `uv.lock` automatically.

- [ ] **Step 2: Create `backend/app/__init__.py`**

Empty file.

- [ ] **Step 3: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    soniox_api_key: str

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 4: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Create `backend/.env`**

```
SONIOX_API_KEY=your_key_here
```

- [ ] **Step 6: Create `backend/tests/__init__.py`**

Empty file.

- [ ] **Step 7: Verify dependencies are installed**

```bash
cd backend
uv run python -c "import fastapi; import soniox; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Run the server and verify health endpoint**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
# In another terminal:
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 9: Commit**

```bash
git add backend/ .gitignore
git commit -m "feat: scaffold backend with FastAPI, config, and health endpoint"
```

---

## Task 3: Backend WebSocket endpoint (Soniox bridge)

**Files:**
- Create: `backend/app/ws.py`
- Modify: `backend/app/main.py` (mount ws router)
- Create: `backend/tests/test_ws.py`

- [ ] **Step 1: Write the failing test for WebSocket connection**

Create `backend/tests/test_ws.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


def test_ws_endpoint_accepts_connection():
    """WebSocket endpoint accepts a connection and responds to start."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        # Should get either a "started" or "error" response
        response = ws.receive_json()
        assert response["type"] in ("started", "error")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_ws.py::test_ws_endpoint_accepts_connection -v
```

Expected: FAIL — no `/ws` endpoint exists yet.

- [ ] **Step 3: Create `backend/app/ws.py`**

```python
import asyncio
import json
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
SONIOX_CONFIG = {
    "api_key": settings.soniox_api_key,
    "model": "stt-rt-v4",
    "audio_format": "pcm_s16le",
    "sample_rate": 16000,
    "num_channels": 1,
}


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
):
    """Read transcript events from Soniox and forward to browser."""
    try:
        async for message in soniox_ws:
            event = json.loads(message)
            if event.get("finished"):
                await browser_ws.send_json({"type": "stopped"})
                return
            tokens = event.get("tokens", [])
            if tokens:
                await browser_ws.send_json({
                    "type": "transcript",
                    "tokens": [
                        {"text": t["text"], "is_final": t.get("is_final", False)}
                        for t in tokens
                    ],
                })
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logger.exception("Error relaying from Soniox")
        try:
            await browser_ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    soniox_ws = None
    relay_task = None

    try:
        while True:
            message = await browser_ws.receive()

            # Text message = JSON control signal
            if "text" in message:
                data = json.loads(message["text"])

                if data["type"] == "start":
                    # Open Soniox connection
                    try:
                        soniox_ws = await websockets.connect(SONIOX_WS_URL)
                        await soniox_ws.send(json.dumps(SONIOX_CONFIG))
                        relay_task = asyncio.create_task(
                            _relay_soniox_to_browser(soniox_ws, browser_ws)
                        )
                        await browser_ws.send_json({"type": "started"})
                    except Exception as e:
                        logger.exception("Failed to connect to Soniox")
                        await browser_ws.send_json({
                            "type": "error",
                            "message": f"Soniox connection failed: {e}",
                        })

                elif data["type"] == "stop":
                    if soniox_ws:
                        await soniox_ws.send(b"")  # Empty frame = end of audio
                        # Wait for relay task to finish (Soniox sends "finished")
                        if relay_task:
                            await asyncio.wait_for(relay_task, timeout=5.0)
                            relay_task = None
                        await soniox_ws.close()
                        soniox_ws = None

            # Binary message = audio frame
            elif "bytes" in message:
                if soniox_ws:
                    await soniox_ws.send(message["bytes"])

    except WebSocketDisconnect:
        pass
    finally:
        if relay_task:
            relay_task.cancel()
        if soniox_ws:
            await soniox_ws.close()
```

- [ ] **Step 4: Mount the router in `backend/app/main.py`**

Add to `main.py` after the CORS middleware:

```python
from app.ws import router as ws_router

app.include_router(ws_router)
```

Full `main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ws import router as ws_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/test_ws.py -v
```

Expected: test passes (the endpoint accepts the connection and returns an error since Soniox key is not valid in test, but the connection itself works).

Note: The test will get an `error` response (no valid Soniox key in test env), which is acceptable — the test asserts the endpoint exists and responds. Integration testing with real Soniox comes in Task 6.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ws.py backend/app/main.py backend/tests/test_ws.py
git commit -m "feat: add WebSocket endpoint bridging browser to Soniox STT"
```

---

## Task 4: Frontend project scaffolding

**Files:**
- Create: `frontend/package.json` (via Vite scaffolding)
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: Scaffold React + Vite + TypeScript project**

```bash
pnpm create vite@latest frontend -- --template react-ts
cd frontend
pnpm install
```

- [ ] **Step 2: Configure Vite proxy for WebSocket**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 3: Replace `frontend/src/App.tsx` with minimal shell**

```tsx
function App() {
  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem" }}>
      <h1>Voice Todos</h1>
      <p>Item 1: Live transcript coming soon.</p>
    </div>
  );
}

export default App;
```

- [ ] **Step 4: Verify frontend runs**

```bash
cd frontend
pnpm dev
```

Open http://localhost:5173 — should show "Voice Todos" heading.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React + Vite frontend with WebSocket proxy"
```

---

## Task 5: Frontend transcript hook and components

**Files:**
- Create: `frontend/src/hooks/useTranscript.ts`
- Create: `frontend/src/components/RecordButton.tsx`
- Create: `frontend/src/components/TranscriptArea.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useTranscript.ts`**

```typescript
import { useCallback, useRef, useState } from "react";

export type Status = "idle" | "connecting" | "recording" | "stopping";

interface Token {
  text: string;
  is_final: boolean;
}

interface TranscriptMessage {
  type: "started" | "transcript" | "stopped" | "error";
  tokens?: Token[];
  message?: string;
}

export function useTranscript() {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const start = useCallback(async () => {
    setStatus("connecting");
    setFinalText("");
    setInterimText("");

    try {
      // Open WebSocket to backend
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg: TranscriptMessage = JSON.parse(event.data);

        if (msg.type === "started") {
          setStatus("recording");
        } else if (msg.type === "transcript" && msg.tokens) {
          let newFinal = "";
          let newInterim = "";
          for (const token of msg.tokens) {
            if (token.is_final) {
              newFinal += token.text;
            } else {
              newInterim += token.text;
            }
          }
          if (newFinal) {
            setFinalText((prev) => prev + newFinal);
          }
          setInterimText(newInterim);
        } else if (msg.type === "stopped") {
          setStatus("idle");
          setInterimText("");
          cleanup();
        } else if (msg.type === "error") {
          console.error("Server error:", msg.message);
          setStatus("idle");
          cleanup();
        }
      };

      ws.onerror = () => {
        setStatus("idle");
        cleanup();
      };

      ws.onclose = () => {
        if (status !== "idle") {
          setStatus("idle");
        }
        cleanup();
      };

      // Wait for WebSocket to open
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
      });

      // Start mic capture
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      // Set up AudioWorklet for PCM extraction
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      await audioContext.audioWorklet.addModule("/pcm-worklet.js");
      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, "pcm-processor");
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(event.data);
        }
      };

      source.connect(workletNode);
      workletNode.connect(audioContext.destination);

      // Tell server to start Soniox session
      ws.send(JSON.stringify({ type: "start" }));
    } catch (err) {
      console.error("Failed to start:", err);
      setStatus("idle");
      cleanup();
    }
  }, []);

  const stop = useCallback(() => {
    setStatus("stopping");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
    }
    // Stop mic immediately
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  function cleanup() {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }

  return { status, finalText, interimText, start, stop };
}
```

- [ ] **Step 2: Create the AudioWorklet processor**

Create `frontend/public/pcm-worklet.js`:

```javascript
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input.length > 0) {
      const float32 = input[0];
      // Convert float32 [-1, 1] to int16 PCM
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
```

- [ ] **Step 3: Create `frontend/src/components/RecordButton.tsx`**

```tsx
import type { Status } from "../hooks/useTranscript";

interface Props {
  status: Status;
  onStart: () => void;
  onStop: () => void;
}

export function RecordButton({ status, onStart, onStop }: Props) {
  switch (status) {
    case "idle":
      return <button onClick={onStart}>Start</button>;
    case "connecting":
      return <button disabled>Connecting...</button>;
    case "recording":
      return (
        <button onClick={onStop} style={{ backgroundColor: "#dc2626", color: "white" }}>
          Stop
        </button>
      );
    case "stopping":
      return <button disabled>Stopping...</button>;
  }
}
```

- [ ] **Step 4: Create `frontend/src/components/TranscriptArea.tsx`**

```tsx
interface Props {
  finalText: string;
  interimText: string;
}

export function TranscriptArea({ finalText, interimText }: Props) {
  if (!finalText && !interimText) {
    return (
      <div style={{ marginTop: "1rem", color: "#888", fontStyle: "italic" }}>
        Click Start and begin speaking...
      </div>
    );
  }

  return (
    <div style={{ marginTop: "1rem", lineHeight: 1.6 }}>
      <span>{finalText}</span>
      <span style={{ color: "#888", fontStyle: "italic" }}>{interimText}</span>
    </div>
  );
}
```

- [ ] **Step 5: Update `frontend/src/App.tsx`**

```tsx
import { useTranscript } from "./hooks/useTranscript";
import { RecordButton } from "./components/RecordButton";
import { TranscriptArea } from "./components/TranscriptArea";

function App() {
  const { status, finalText, interimText, start, stop } = useTranscript();

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem" }}>
      <h1>Voice Todos</h1>
      <RecordButton status={status} onStart={start} onStop={stop} />
      <TranscriptArea finalText={finalText} interimText={interimText} />
    </div>
  );
}

export default App;
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/ frontend/public/pcm-worklet.js
git commit -m "feat: add transcript hook, RecordButton, TranscriptArea components"
```

---

## Task 6: End-to-end integration test

**Files:** No new files — manual testing with real Soniox key.

**Prerequisites:** Valid `SONIOX_API_KEY` in `backend/.env`.

- [ ] **Step 1: Start the backend**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Start the frontend (separate terminal)**

```bash
cd frontend
pnpm dev
```

- [ ] **Step 3: Open http://localhost:5173 in Chrome**

- [ ] **Step 4: Click Start, speak a sentence, click Stop**

Verify:
- Button transitions: Start → Connecting... → Stop (red) → Stopping... → Start
- Words appear as you speak (interim text in gray/italic)
- Final text stays after words stabilize
- After Stop, all text is final, button returns to Start

- [ ] **Step 5: Test error cases**

- Start with backend not running → should show error or stay idle
- Start and immediately stop → should handle gracefully
- Refresh page while recording → no server crash

- [ ] **Step 6: Commit any fixes**

```bash
git add -u
git commit -m "fix: address issues found during integration testing"
```

