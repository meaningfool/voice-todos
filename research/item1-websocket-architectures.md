# WebSocket connections

This report covers how WebSocket connections work, how they fail, how to manage them reliably, and alternative ways to architect them for a voice transcription app.

## How does the browser connect to the speech-to-text service?

**How many WebSocket connections are involved?** Two, arranged in series. The browser opens a WebSocket to the app's backend server. The server, in turn, opens a second WebSocket to the STT provider (Soniox). The server sits in the middle, relaying audio upstream and transcript tokens downstream.

```
Browser  ──ws──>  Server  ──ws──>  Soniox
```

The second connection (server to Soniox) is dictated by Soniox's API. It stays the same regardless of how the browser-to-server side is designed. All the architectural choices discussed here are about the first connection only.

**What travels on the browser-to-server connection?** Three kinds of traffic, multiplexed on a single WebSocket:

1. Control messages (JSON): `{"type": "start"}` and `{"type": "stop"}`, sent by the browser to begin or end a session.
2. Audio frames (binary): raw PCM data from the microphone, streamed continuously while recording.
3. Transcript updates (JSON): `{"type": "transcript", "tokens": [...]}`, sent by the server as Soniox produces results.

The server distinguishes control from audio by checking whether the incoming message is text (JSON) or binary (audio).

**What happens when the user stops recording?** The stop is not instant. It propagates through all three systems:

1. The browser sets its state to "stopping" (the button becomes disabled), sends `{"type": "stop"}` to the server, and kills the microphone immediately. Audio stops flowing.
2. The server receives the stop message and sends an empty byte frame to Soniox, which is Soniox's protocol for "end of audio."
3. Soniox processes any buffered audio it hasn't transcribed yet, sends back the final tokens, then sends `{"finished": true}`.
4. The server's relay function sees `finished` and forwards `{"type": "stopped"}` to the browser. It then closes the Soniox connection.
5. The browser receives "stopped," clears its safety timeout, and transitions back to idle.

Both the browser and the server have timeout guards (5 seconds each) in case the round trip never completes.

**How does React know about any of this?** The entire recording lifecycle lives inside a custom hook (`useTranscript`). The hook exposes three pieces of React state (`status`, `finalText`, `interimText`) and two functions (`start`, `stop`). The UI components receive these as props and render accordingly: `RecordButton` uses `status` to switch between "Start," "Connecting...," "Stop," and "Stopping..." labels. `TranscriptArea` displays the text.

The WebSocket, AudioContext, MediaStream, and AudioWorkletNode all live inside the hook as `useRef` values. Refs don't trigger re-renders. Only the `useState` values cause the UI to update. The hook is a state machine that bridges browser APIs to React's rendering cycle.

## What states can a WebSocket connection be in?

A WebSocket connection has four states, always moving in one direction:

```
CONNECTING  →  OPEN  →  CLOSING  →  CLOSED
```

There's no going back. Once a connection leaves a state, it never returns to it. To connect again, you create a new `WebSocket` object.

- **CONNECTING:** the initial state. The browser has sent an HTTP request with an `Upgrade: websocket` header, and the server hasn't agreed yet. You can't send anything — calling `ws.send()` here throws an error. Two outcomes: the server accepts (moves to OPEN, `ws.onopen` fires) or something fails (jumps to CLOSED, `ws.onerror` then `ws.onclose` fire).
- **OPEN:** both sides can send messages freely. Three events can fire: `ws.onmessage` (message arrived), `ws.onerror` (something went wrong), `ws.onclose` (connection is closing).
- **CLOSING:** a brief transitional state. It starts when either side calls `close()`. The WebSocket protocol has a closing handshake — one side sends a close frame, the other acknowledges. You can't send messages here either.
- **CLOSED:** terminal. `ws.onclose` has fired. The object is done — it can't be reopened or reused.

The server has the same four states, but tracks them independently. The two sides communicate over a network, so there's always a delay between one side changing state and the other finding out. This mismatch is the source of most WebSocket bugs.

## How does a connection open and close normally?

**Opening** starts as a regular HTTP request. The browser sends a GET with `Upgrade: websocket` and `Connection: Upgrade` headers. The server responds with HTTP 101 (Switching Protocols). From that point on, the TCP connection carries the WebSocket protocol instead of HTTP. Both sides are in OPEN.

**Closing** has its own handshake. One side calls `close()`, which sends a close frame with a status code. The other side responds with its own close frame. Both transition through CLOSING to CLOSED. Both `onclose` events fire with `wasClean: true`.

## How can WebSocket connections fail?

**What's a dirty close?** A connection that ends without the closing handshake. The network drops, the browser crashes, the server process dies, the user's laptop lid closes. No close frame is sent. The surviving side eventually discovers the other is gone, but there's a gap where it doesn't know. When `onclose` finally fires, `wasClean` is `false`.

**How long before the surviving side notices?** It depends on what's happening on the connection. If the surviving side is actively sending data (like audio frames every few milliseconds), the TCP stack detects the failure within seconds — frames pile up with no acknowledgment, and the OS gives up. If the connection is idle, it can take 30-60 seconds or more, because TCP timeouts are long by default and neither side is sending anything to trigger a failure.

**What makes this harder than HTTP?** With HTTP, every interaction is a request followed by a response. If the server crashes mid-response, the browser gets a network error immediately. There's no ambiguous state — either you got a response or you didn't. With WebSocket, the connection stays open indefinitely. Either side can send, close, or disappear at any moment. The number of things that can happen is larger, and the timing is unpredictable. A few situations that don't exist with HTTP:

- The user clicks Start while a previous connection is still in the CLOSING state.
- The server sends a transcript token at the exact moment the browser sends Stop.
- The browser calls `close()` but the server never acknowledges.
- Both a `"stopped"` message and an `onclose` event fire, triggering cleanup twice.

## How do you manage WebSocket connections reliably?

**Guard state transitions with a state machine.** Only allow operations that make sense from the current state. If `start()` is called while the connection is anything other than idle, bail out immediately. This prevents duplicate connections — like the bug where calling `start()` during CONNECTING would open a second Soniox session without cleaning up the first. The same applies to incoming messages: ignore a transcript token that arrives after the user already stopped.

**Release local resources on user intent, not on server confirmation.** When the user clicks Stop, kill the microphone, disconnect the audio worklet, and close the AudioContext immediately. Don't hold them open while waiting for a three-system round trip. The server confirmation updates the UI state later. This pattern requires a timeout as a safety net — if the confirmation never arrives, clean up anyway.

**Make cleanup idempotent.** Multiple code paths can trigger cleanup: a `"stopped"` message arriving, an `onclose` event firing, a timeout expiring. If two of these fire in sequence, cleanup runs twice. The fix: check whether each resource still exists before closing it, and set references to `null` after closing. The second call finds everything already null and does nothing.

**Assume the other side might not respond.** Every message sent to the server should have a local fallback. Connection attempt fails? Reset to idle. Stop message gets no response? Timeout and clean up. Unexpected close? Reset to idle. With HTTP, the framework provides request timeouts automatically. With WebSocket, you build them yourself.

**Use ping/pong to detect dead connections.** The WebSocket protocol has built-in ping and pong frames. One side sends a ping; the other must respond with a pong. If no pong arrives within a timeout, the connection is dead. On the server side, the `websockets` Python library sends pings automatically (every 20 seconds by default). If the browser doesn't respond, the library closes the connection. On the browser side, the `WebSocket` API responds to pings automatically but can't initiate them. For connections that stream data continuously (like audio), this doesn't matter — the data itself acts as an implicit heartbeat. For connections that sit idle for long periods, you'd need to implement your own ping using regular messages.

**On the server side, always clean up in a finally block.** If the browser disappears mid-stream, the server is still holding resources (a Soniox connection, a relay task). A `try/finally` around the entire WebSocket handler ensures cleanup runs regardless of how the connection ends — clean close, dirty close, exception, or timeout.

## What are the alternatives to a single WebSocket?

The two main alternatives split the browser-to-server connection into separate channels for control, audio, and transcript. Each trades simplicity for a specific benefit.

### What does the REST + WebSocket split look like?

Control messages (start, stop, and any future actions) move to standard HTTP endpoints. The WebSocket carries only the stream: audio up, transcript down.

1. The browser sends `POST /sessions/start`. The server opens the Soniox connection and returns a session ID.
2. The browser opens `ws://server/stream/{session_id}`. Audio frames flow up, transcript tokens flow down.
3. The browser sends `POST /sessions/{id}/stop`. The server signals Soniox to flush and waits for completion.

The WebSocket handler becomes simpler because it only moves bytes and tokens. The REST side gets standard HTTP middleware (authentication, rate limiting, logging) for free.

**When does this split become worth it?** When the app grows non-streaming features that share the same backend. Consider a todo list that syncs in real time, plus user authentication. With a single WebSocket, authentication is awkward: HTTP has cookies, headers, and middleware that the entire backend framework understands, but none of that applies to WebSocket messages. Auth logic has to be added inside the message handler. Every new feature on the WebSocket needs its own auth check.

Adding todo sync to the same WebSocket means the server's message loop becomes a router: it branches between audio frames, transcript tokens, todo updates, and control messages. The handler that started as a clean loop turns into a dispatcher.

The REST + WebSocket split solves this naturally. REST handles everything that fits request/response (create a todo, start a session, authenticate). The WebSocket only carries the audio/transcript stream. The trigger: non-streaming features are fighting the framework to work over WebSocket.

**What new problems does it introduce?** Race conditions. The REST call to start a session must complete before the WebSocket can open (two round trips instead of one). If the REST call succeeds but the WebSocket connection fails, the app is in a half-started state. Stopping has a similar issue: a POST to `/stop` can arrive while transcript tokens are still flowing on the WebSocket, and someone needs to decide when and how the WebSocket closes.

### What does the WebSocket + SSE split look like?

Audio upload stays on a WebSocket (it needs to be bidirectional for binary streaming). Transcript delivery moves to Server-Sent Events (SSE), a one-way HTTP stream from server to client.

1. The browser sends `POST /sessions/start` to get a session ID.
2. The browser opens `ws://server/audio/{session_id}` and sends audio frames.
3. The browser opens `GET /transcript/{session_id}` as an SSE stream and receives transcript tokens as events.
4. To stop, the browser closes the WebSocket or sends a REST call.

**When does this split become worth it?** When the transcript consumer needs to survive connection drops, but the audio producer does not. Consider live captioning for a conference talk. The speaker's connection is stable (wired, backstage). The audience watches captions on their phones, moving between rooms, losing WiFi.

With a WebSocket delivering the transcript, a drop kills the connection. The client reconnects but misses whatever was said during the gap. SSE has a built-in mechanism for this: each event gets a sequential ID, and when the browser reconnects (which the `EventSource` API does automatically), it sends the last ID it received. The server resumes from that point. No gaps.

The trigger: the transcript consumer and the audio producer are different clients with different reliability needs.

**What new problems does it introduce?** Three connections instead of one. More coordination, more failure modes. The browser also has a limit of roughly six concurrent HTTP connections per domain under HTTP/1.1, and an SSE stream permanently holds one of those slots.

## How does a server push data to a browser without WebSocket?

**Is WebSocket the only option?** No. There are three mechanisms:

1. WebSocket: full duplex, both sides send freely. Best when both directions carry high-frequency streams (continuous audio, real-time cursor positions, multiplayer game inputs).
2. Server-Sent Events (SSE): server-to-client only, over plain HTTP. The browser opens a GET request that stays open, and the server writes events to it. The browser cannot send data back on the same connection.
3. Polling: the client asks "anything new?" on a timer. Not real-time, but simple and sufficient when updates are infrequent.

**When does real-time collaboration need WebSocket vs. SSE?** It depends on the traffic shape. For a collaborative todo list, the traffic is asymmetric: the client sends edits (create, check off, reorder) as one-off actions, and receives other people's changes as a stream. The one-off actions fit standard REST calls. The stream of changes fits SSE. No WebSocket needed.

WebSocket becomes necessary when both directions are high-frequency streams: collaborative cursor tracking (every client continuously broadcasts its position), multiplayer game state, or audio streaming. If the client-to-server direction is occasional actions that fit request/response, REST + SSE is simpler and gets HTTP's auth, caching, and retry tooling for free.
