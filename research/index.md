# Research Index

Topics to explore in depth, organized by roadmap item. Each topic captures what we know so far, what's unclear, and links to a dedicated file when the research is done.

## Item 1: Live Transcript in Browser

### 1. Audio Formats and Frames

**Status:** To explore

**What came up:** The design spec mentions "binary frames" sent over WebSocket, and references raw PCM (16-bit, 16kHz mono) and WebM/Opus as possible formats. The browser captures audio via `getUserMedia`, but the exact encoding and framing is undecided.

**What I want to understand:**
- What is an audio frame? What are its boundaries?
- What's the difference between raw PCM and WebM/Opus? Why would you pick one over the other?
- What does the browser actually produce from `getUserMedia` — and how do you get it into a format Soniox accepts?
- What role does `AudioWorklet` vs `MediaRecorder` play here?

**File:** `research/item1-audio-formats.md` (not yet created)

---

### 2. Transcript Token Lifecycle

**Status:** To explore

**What came up:** Soniox returns tokens with an `is_final` boolean. The design says interim tokens get replaced on each update while final tokens are appended permanently. But the full picture of what Soniox actually sends, how often, and how the UI should handle it needs more detail.

**What I want to understand:**
- What does a real Soniox WebSocket response look like? Walk through concrete examples.
- How frequently do transcript messages arrive? Per word? Per phrase? Per silence gap?
- How does interim text evolve — does it grow, get replaced entirely, or get corrected mid-stream?
- What's the full lifecycle from spoken word → Soniox token → UI update? Step by step with real data.
- How does the FastAPI bridge affect timing or batching?

**File:** `research/item1-transcript-lifecycle.md` (not yet created)

---

### 3. WebSocket Architecture Alternatives

**Status:** To explore

**What came up:** We chose the simplest architecture (single WebSocket carries everything: control signals, audio, transcript). During brainstorming, two alternatives were discussed:
- **Option B:** REST for start/stop control + separate WebSocket for audio/transcript streaming
- **Option C:** WebSocket for audio upload + Server-Sent Events (SSE) for transcript delivery

**What I want to understand:**
- What are the concrete limitations of the single-WebSocket approach we chose?
- In what scenarios would Option B (REST + WebSocket) be the better fit?
- In what scenarios would Option C (WebSocket + SSE) be the better fit?
- Are there production voice apps that use each pattern, and why?
- At what scale or complexity does the single-WebSocket approach start to break down?

**File:** `research/item1-websocket-architectures.md` (not yet created)

---

### 4. WebSocket Connection Lifecycle — Opening, Closing, and What Goes Wrong

**Status:** To explore

**What came up:** During implementation, 6 out of 10 code review issues were related to opening or closing WebSocket connections — both on the Python server side (`websockets` library) and the browser side (`WebSocket` API). These edge cases felt harder to get right than with standard HTTP request/response.

**Concrete issues we hit:**
- Double "start" leaking the first Soniox connection (no cleanup of old session)
- Soniox connection dropping mid-stream with no logging (silent `ConnectionClosed`)
- Browser `ws.onerror` handler getting overwritten during the connection handshake
- `stop()` relying on the server to respond — no fallback if server crashes
- Double cleanup when both "stopped" message and `onclose` event fire
- No guard against calling `start()` while already connecting

**What I want to understand:**
- What is the WebSocket connection lifecycle? What states can a connection be in, and what events fire during transitions?
- Why is cleanup harder than with HTTP? What makes WebSocket connections more error-prone?
- What are the common patterns for robust WebSocket lifecycle management — both client-side (browser) and server-side (Python asyncio)?
- How do you handle "the other side disappeared" gracefully? (server crash, network drop, browser refresh)
- What's the standard approach to preventing duplicate connections and ensuring cleanup always runs?

**File:** `research/item1-websocket-lifecycle.md` (not yet created)

---

### 5. Audio Capture and the Web Audio API (AudioWorklet, getUserMedia)

**Status:** To explore

**What came up:** We use `getUserMedia` to capture mic audio and an `AudioWorklet` (`pcm-worklet.js`) to convert Float32 samples to Int16 PCM for Soniox. During review, we found the worklet was accidentally connected to the speaker output (causing echo). The audio pipeline works but feels like a black box.

**What I want to understand:**
- How does audio capture work in the browser? What is the path from microphone hardware → `getUserMedia` → usable audio data?
- What is the Web Audio API graph model? Sources, nodes, destinations — how do they connect and why?
- What is an AudioWorklet and how does it differ from the deprecated ScriptProcessorNode?
- What does `getUserMedia` actually produce? Sample rate, format, buffering — and how much control do you have?
- How does `AudioContext({ sampleRate: 16000 })` interact with the device's native sample rate? Does the browser resample?
- What are the equivalents on native platforms (iOS, Android)? How different is audio capture outside the browser?
- What are audio sources and destinations beyond mic → speaker? (e.g., system audio, files, other apps)

**File:** `research/item1-audio-capture.md` (not yet created)
