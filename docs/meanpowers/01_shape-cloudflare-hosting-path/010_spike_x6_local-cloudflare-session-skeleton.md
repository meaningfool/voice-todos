# Spike: X6 Local Cloudflare Session Skeleton

## Context

Shape `B` is selected:

- Worker front door
- one Durable Object per live session
- shared live-session core later
- Cloudflare-specific transport adapter later

The remaining question is whether the selected runtime shape is practical enough
to exercise locally before any real refactor begins.

## Goal

Prove the selected `B` runtime skeleton locally with a minimal Python Worker +
Durable Object prototype:

- accept a browser WebSocket at `/ws`
- route one session to one Durable Object
- keep session state in the Durable Object
- send browser messages that match the current protocol shape
- enforce a short server-side session cap and close cleanly

## Questions

| ID | Question |
|---|---|
| X6-Q1 | Can Python `Worker + Durable Object` local development run the selected session shape at all? |
| X6-Q2 | Can one Durable Object own one browser session cleanly enough to support the current app boundary? |
| X6-Q3 | Can the browser-facing message protocol be preserved in a Worker/DO skeleton? |
| X6-Q4 | Can a server-side session cap be demonstrated locally in the simulated Cloudflare runtime? |

## Implementation Artifact

- Prototype project: [research/x6-cloudflare-session-skeleton](../../../research/x6-cloudflare-session-skeleton/README.md)

## Findings

### Finding 1

The local Cloudflare simulation path is practical for this shape.

Evidence:

- `uv run pywrangler dev --port 8788` successfully launched the Python Worker locally.
- Wrangler exposed a local Durable Object binding and served the worker at `http://localhost:8788`.

Impact:

- The selected `B` shape can be explored and debugged locally before deployment.
- This removes a large amount of workflow uncertainty from the shape.

### Finding 2

The `Worker -> Durable Object -> browser WebSocket` ownership model maps cleanly to one session.

Evidence:

- The Worker accepted `/ws` and routed each browser connection by `session` query parameter to one Durable Object instance.
- The Durable Object accepted the browser WebSocket and owned the session state and teardown behavior.

Impact:

- `B3` and `B4` are confirmed at the runtime-skeleton level.
- The selected shape still matches the current app boundary well.

### Finding 3

The current browser-facing protocol shape can be preserved in a local Worker/DO skeleton.

Evidence:

- The prototype emitted:
  - `started`
  - `transcript`
  - `todos`
  - `stopped`
- These shapes match the current browser expectations closely enough to validate the runtime boundary.

Impact:

- The frontend protocol does not appear to force a redesign just because the runtime moves to `B`.

### Finding 4

Server-side session-cap enforcement works locally.

Evidence:

- The Durable Object used an alarm to enforce a `5s` cap.
- In live browser validation, the session emitted `stopped` and closed with code `1000` after the cap.

Impact:

- `B6` is confirmed at the runtime-skeleton level.
- The portfolio-demo session-cap requirement is compatible with this shape.

### Finding 5

Two Python Worker / Durable Object API details matter for the real implementation.

Evidence from the spike:

- WebSocket enumeration inside the Python Durable Object alarm path worked with `self.ctx.getWebSockets()`, not `get_websockets()`.
- Binary browser frames should be ignored by checking for text positively (`isinstance(message, str)`), because incoming binary messages do not arrive as ordinary Python `bytes`.

Impact:

- The main runtime mechanics are workable, but the real implementation will need careful API-level adaptation rather than assumption from ordinary Python websocket code.

### Finding 6

This spike does not reduce the main provider-side risk.

Evidence:

- The prototype used no outbound Soniox connection.
- The current backend still depends on `websockets.connect` in [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py).

Impact:

- `B5` remains the main unresolved technical component.
- If more proof is needed before slicing, the next spike should focus specifically on the outbound provider transport.

## Practical Read

`B` is now proven locally at the runtime-skeleton level.

What is confirmed:

- local Cloudflare simulation workflow
- Worker front door
- one-session-per-Durable-Object shape
- browser protocol preservation at the message-shape level
- server-side session cap and clean close

What remains open:

- real outbound provider transport
- shared-core extraction from the current backend
- final packaging choice if a Deploy to Cloudflare button is wanted later

## Outcome

This spike is a positive result.

It does not prove the entire implementation, but it does prove that the chosen
Cloudflare runtime shape is real enough to slice against.

## Shape Impact

- `B3` Worker front door: confirmed at the skeleton level
- `B4` session-owned Durable Object runtime: confirmed at the skeleton level
- `B6` session policy and teardown: confirmed at the skeleton level
- `B5` provider transport adapter: still the main open technical risk

## Recommended Next Step

Do not reopen the top-level shape decision.

The next useful shaping move is either:

1. begin slicing around `B1`, `B2`, `B3`, `B4`, and `B6`, or
2. run a narrower provider-transport spike if you want to reduce `B5` before slicing
