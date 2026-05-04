# Spike: FastAPI WebSocket Boundary on Python Workers

## Context

After Spike `X1`, Shape `A` remained plausible only as a Worker-native rewrite of the live transport layer. One narrower uncertainty remained: whether the browser-facing WebSocket path could still stay on a FastAPI ASGI WebSocket route inside Cloudflare Python Workers, even if the outbound Soniox side needed a rewrite.

This spike investigates that narrower boundary question.

## Goal

Determine whether the current browser-facing `/ws` route can plausibly remain a FastAPI ASGI WebSocket endpoint on Cloudflare Python Workers, or whether that boundary also needs to become Worker-native.

## Questions

| ID | Question |
|---|---|
| X2-Q1 | Does the current repo rely on normal FastAPI WebSocket behavior at the browser boundary? |
| X2-Q2 | Does Cloudflare's documented FastAPI path for Python Workers include WebSocket handling, or only HTTP request handling? |
| X2-Q3 | Does Cloudflare's Python ASGI bridge implement the WebSocket ASGI events that FastAPI and Starlette normally expect? |

## Findings

### Finding 1

The current browser-facing live path is a normal FastAPI WebSocket route with standard Starlette/FastAPI connection handling.

Repo evidence:

- The app exposes `@router.websocket("/ws")`.
- The route immediately calls `await browser_ws.accept()`, then enters a long-lived receive loop for browser control and audio messages.

Relevant code:

- [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/ws.py:92)

Impact:

- Any Cloudflare Python Worker path that keeps the current browser boundary intact must support the normal ASGI WebSocket lifecycle that FastAPI expects.

### Finding 2

Cloudflare's published FastAPI path for Python Workers documents HTTP request handling through `asgi.fetch`, not WebSocket upgrade handling.

Cloudflare evidence:

- The FastAPI documentation says the Workers runtime provides an ASGI server to Python Workers.
- The published example uses `return await asgi.fetch(app, request, self.env)`.
- The official FastAPI example in `cloudflare/python-workers-examples` also routes requests through `asgi.fetch`.

Relevant sources:

- https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- https://raw.githubusercontent.com/cloudflare/python-workers-examples/main/03-fastapi/src/worker.py

Impact:

- The documented and example-backed FastAPI path is an HTTP path.
- This spike did not find an official FastAPI WebSocket example from Cloudflare.

### Finding 3

Cloudflare's current Python ASGI bridge separates HTTP handling from WebSocket handling instead of treating `asgi.fetch` as a unified HTTP-plus-WebSocket server entry point.

Cloudflare evidence:

- In `workers-py`, `fetch()` calls `process_request(...)`, which builds an HTTP scope and handles `http.request`, `http.response.start`, and `http.response.body`.
- WebSockets are handled by a separate `websocket()` helper, which calls `process_websocket(...)`.

Relevant source:

- https://raw.githubusercontent.com/cloudflare/workers-py/main/packages/runtime-sdk/src/asgi.py

Impact:

- A plain `return await asgi.fetch(app, request, self.env)` path is not evidence that FastAPI WebSocket routes work.
- A Python Worker would need explicit upgrade branching at the fetch boundary to even attempt an ASGI-WebSocket path.

### Finding 4

Cloudflare's current Python ASGI WebSocket bridge does not appear to implement the normal FastAPI/Starlette handshake lifecycle fully.

Primary protocol evidence:

- The ASGI WebSocket spec requires the application to respond to `websocket.connect` with either `websocket.accept` or `websocket.close` before data flow proceeds.
- Starlette's WebSocket interface explicitly expects `await websocket.accept()` as the normal accept step.

Cloudflare bridge evidence:

- The `workers-py` `ws_send(...)` handler implements `websocket.send`.
- Other outbound ASGI WebSocket message types are logged as `Not implemented`.

Relevant sources:

- https://asgi.readthedocs.io/en/stable/specs/www.html
- https://www.starlette.io/websockets/
- https://raw.githubusercontent.com/cloudflare/workers-py/main/packages/runtime-sdk/src/asgi.py

Impact:

- A normal FastAPI or Starlette WebSocket route is expected to emit `websocket.accept`.
- This spike found no evidence that Cloudflare's current Python ASGI bridge fully supports that lifecycle.
- The bridge source instead suggests that the WebSocket path is partial or immature for framework-managed WebSocket endpoints.

### Finding 5

Cloudflare's official Python WebSocket examples use Worker-native APIs, not FastAPI WebSocket routes.

Cloudflare evidence:

- The chatroom example uses `WebSocketPair` and Durable Object methods for incoming browser connections.
- The outbound stream-consumer example uses `js.WebSocket` through Pyodide interop.

Relevant sources:

- https://raw.githubusercontent.com/cloudflare/python-workers-examples/main/15-chatroom/src/entry.py
- https://github.com/cloudflare/python-workers-examples/tree/main/14-websocket-stream-consumer

Impact:

- Cloudflare's current example set reinforces Worker-native WebSocket handling as the supported path.
- It does not reinforce FastAPI-managed WebSocket routes as a stable path for the live session boundary.

## Conclusion

This spike does not exclude Python Workers.

It does narrow Shape `A` further:

- The browser-facing live WebSocket boundary should not be assumed to remain on the current FastAPI `@router.websocket` route.
- The current evidence supports Python Workers only if Shape `A` accepts Worker-native handling on the inbound browser WebSocket path as well as the outbound provider path.

In short:

- `A` still works as a rewrite shape.
- `A` is now better understood as a rewrite of both live WebSocket legs, not only the Soniox leg.
- A direct FastAPI-WebSocket-first port is not supported by the current evidence.

## Shape Impact

This spike suggests the current shapes are directionally right, but the wording of `A` should now be read more strictly:

- Shape `A` means Worker-native live-session handling, with FastAPI retained only where it still fits cleanly, not as the primary live WebSocket boundary.
- Shape `B` becomes even more credible because it matches Cloudflare's documented long-lived connection ownership pattern.
- Shape `C` remains unchanged as the lowest migration-risk option.
