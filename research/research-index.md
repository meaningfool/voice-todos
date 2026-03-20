# Research Index

Topics to explore in depth, organized by roadmap item. Each topic captures what we know so far, what's unclear, and links to a dedicated file when the research is done.

## Item 1: Live Transcript in Browser

### Completed

- **Audio Formats, Frames, and Capture** (topics 1 & 5) — `research/item1-audio-formats-and-capture.md`
- **Transcript Token Lifecycle** (topic 2) — `research/item1-transcript-lifecycle.md`

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

