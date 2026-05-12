# Spike: Python Worker Live Path Feasibility

## Context

Shape `A` proposes adapting the current live voice backend to Cloudflare Python Workers. The main open questions are whether the current browser WebSocket path, the outbound Soniox WebSocket client, and the current Python dependency graph can run in that environment without falling back to Durable Objects or Containers.

This spike investigates mechanics and feasibility, not implementation effort.

## Goal

Learn whether the current live path can plausibly run as a Cloudflare Python Worker, and identify the concrete adaptation points or blockers that matter to shaping.

## Questions

| ID | Question |
|---|---|
| X1-Q1 | Can Cloudflare Python Workers host the browser-facing live WebSocket path in a way that matches the current session behavior? |
| X1-Q2 | Can the current outbound Soniox WebSocket client run in Python Workers as written? |
| X1-Q3 | Which current backend dependencies materially complicate Python Worker deployment? |
| X1-Q4 | When do Durable Objects become required, optional, or preferred for this app shape? |

## Findings

### Finding 1

The current repo live path is per-session and does not require shared cross-session coordination.

Repo evidence:

- The current backend accepts one browser WebSocket connection at `/ws`, creates one `TranscriptAccumulator`, one STT session, and one `ExtractionLoop` per connection.
- There is no application-level shared room, lobby, or cross-client state in the live path.

Relevant code:

- [backend/app/ws.py](../../../backend/app/ws.py)
- [backend/app/extraction_loop.py](../../../backend/app/extraction_loop.py)

Impact:

- Durable Objects are not required by the current product behavior.
- The main reason to introduce Durable Objects would be runtime mechanics or future session ownership concerns, not current requirements.

### Finding 2

The current outbound Soniox client cannot be carried into Python Workers unchanged.

Repo evidence:

- The Soniox adapter uses Python `websockets.connect` and a `websockets.ClientConnection`.

Relevant code:

- [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py)
- [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py)

Cloudflare evidence:

- Python Workers run on Pyodide in a WebAssembly environment.
- In Cloudflare's Python Workers standard library notes, `sockets` are present but not functional.
- Cloudflare's official Python outbound WebSocket example does not use Python `websockets`; it uses `js.WebSocket.new(...)` through Pyodide FFI inside a Durable Object, and the example comments say native Python websocket APIs are planned for the future.

Relevant sources:

- https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/
- https://developers.cloudflare.com/workers/languages/python/stdlib/
- https://github.com/cloudflare/python-workers-examples/tree/main/14-websocket-stream-consumer

Example details:

- The official example creates the outbound socket with `js.WebSocket.new(...)` and attaches event listeners through `create_proxy`, not `websockets.connect`.
- The example explicitly notes that native Python websocket APIs are a future capability.

Impact:

- Shape `A` remains possible only with a rewrite of the Soniox transport layer to Worker-native WebSocket APIs or a different Cloudflare-native runtime boundary.
- A drop-in port of the current Soniox adapter is not viable.

### Finding 3

The browser-facing WebSocket path is supported by Cloudflare Workers in principle, but a direct FastAPI WebSocket port is not proven by this spike.

Repo evidence:

- The current app uses FastAPI with `@router.websocket("/ws")`.

Relevant code:

- [backend/app/main.py](../../../backend/app/main.py)
- [backend/app/ws.py](../../../backend/app/ws.py)

Cloudflare evidence:

- Cloudflare documents Python FastAPI support through its ASGI runtime.
- Cloudflare documents Worker WebSocket support and Durable Object WebSocket support.
- The official Python example set includes:
  - a FastAPI HTTP example
  - a WebSocket chatroom example using `WebSocketPair` and a Durable Object
- This spike did not find an official Python Workers example of FastAPI ASGI WebSockets.

Relevant sources:

- https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- https://developers.cloudflare.com/workers/runtime-apis/websockets/
- https://github.com/cloudflare/python-workers-examples/tree/main/15-chatroom

Impact:

- Browser-facing WebSockets are clearly available on the platform.
- What remains unproven is whether the current FastAPI `@router.websocket` surface can move over with minimal change.
- A Worker-native WebSocket handler is better supported by current examples than a FastAPI-WebSocket-first port.

### Finding 4

The current Python dependency graph is broader than the app's visible runtime needs and increases Python Worker risk.

Repo evidence:

- The backend currently depends on `pydantic-ai`, `mistralai`, `soniox`, `uvicorn`, and `websockets`.
- The lockfile shows top-level `pydantic-ai` pulling `pydantic-ai-slim` with a very broad extras set, including `google`, `mistral`, `openai`, `temporal`, `xai`, and others.
- The lockfile includes compiled or platform-specific packages such as `grpcio`, `temporalio`, and `tiktoken`.

Relevant code and lock data:

- [backend/pyproject.toml](../../../backend/pyproject.toml)
- [backend/uv.lock](../../../backend/uv.lock)
- [backend/uv.lock](../../../backend/uv.lock)
- [backend/uv.lock](../../../backend/uv.lock)

Cloudflare evidence:

- Python Workers support pure Python packages and Pyodide-supported packages.
- Cloudflare specifically calls out async HTTP clients such as `aiohttp` and `httpx`.

Relevant source:

- https://developers.cloudflare.com/workers/languages/python/packages/

Impact:

- Shape `A` should not assume the current lockfile can be deployed as-is.
- The current dependency graph likely needs deliberate slimming before Python Workers becomes a credible target.
- This is not the same as proving Python Workers cannot work. It means the packaging story must be part of the shape.

### Finding 5

Containers remain the lowest migration-risk path for preserving the current backend shape.

Cloudflare evidence:

- Cloudflare Containers are intended for applications and libraries that require a full filesystem, a specific runtime, or a Linux-like environment.
- Containers are fronted by a Worker and backed by Durable Object infrastructure.

Relevant sources:

- https://developers.cloudflare.com/containers/
- https://developers.cloudflare.com/containers/get-started/

Repo evidence:

- The current backend assumes a normal Python runtime with:
  - FastAPI + `uvicorn`
  - Python `websockets`
  - optional session recording to local disk

Relevant code:

- [backend/pyproject.toml](../../../backend/pyproject.toml)
- [backend/app/session_recorder.py](../../../backend/app/session_recorder.py)

Impact:

- Shape `C` is still the fallback with the least runtime adaptation.
- Shape `C` adds platform complexity, but it preserves more of the current backend assumptions.

## Conclusion

The spike narrows the decision materially:

- Cloudflare can host the app shape.
- The current live path does not require Durable Objects for business behavior.
- The current Python backend cannot move to Python Workers unchanged because the outbound Soniox client depends on Python websocket mechanics that are not the platform's current Python pattern.
- Python Workers remain plausible only if the shape accepts:
  - a Worker-native WebSocket rewrite for the live transport layer
  - likely dependency slimming
  - possibly a Durable Object as the per-session runtime owner even without a business requirement for shared coordination
- Containers remain the lowest-risk way to preserve the existing backend runtime shape.

## Shape Impact

This spike suggests the current shape set is too coarse.

It likely needs the following refinement:

- Narrow `A` so it explicitly means a Worker-native rewrite of the live relay path.
- Promote `B` from reserve to candidate, because official Cloudflare Python WebSocket examples lean on Durable Objects for long-lived connection ownership even when they are not solving chat-room style shared coordination.
- Keep `C` as the low-migration-risk runtime-preservation option.

It also suggests one likely future requirement decision:

- Decide whether session recording to local files matters in the hosted Cloudflare path. If not, that concern should be removed from the live-hosting shape.
