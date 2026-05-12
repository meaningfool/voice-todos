# Spike: X7 Soniox Provider Transport

## Context

Shape `B` is selected:

- Worker front door
- one Durable Object per live session
- shared live-session core later
- Cloudflare-specific provider transport adapter

After `X6`, the main open question was `B5`: whether a Python Durable Object can
carry the current Soniox streaming contract inside the Cloudflare runtime.

## Goal

Prove the outbound Soniox transport boundary inside a Python Durable Object
without mixing in browser integration, extraction logic, or the shared-core
refactor.

## Questions

| ID | Question |
|---|---|
| X7-Q1 | Can a Python Durable Object open and use an outbound Soniox WebSocket connection in local Cloudflare simulation? |
| X7-Q2 | Can the Durable Object stream the existing PCM fixture and preserve the current `finalize -> empty-frame EOS` ordering? |
| X7-Q3 | Does the Soniox stop contract that matters to this app depend on provider `finished`, or only on the `<fin>` boundary already used in the repo? |

## Implementation Artifact

- Prototype project: [research/x7-soniox-provider-transport](../../../research/x7-soniox-provider-transport/README.md)

## Findings

### Finding 1

The outbound Soniox transport is mechanically viable inside a Python Durable Object.

Evidence:

- `uv run pywrangler dev --port 8789` successfully ran the local Worker + Durable Object proof.
- `POST /prove-soniox?finalize=1` returned `200` with:
  - `transcript: "Stop the button."`
  - `saw_fin: true`
  - `events_seen: 6`
- `POST /prove-soniox?finalize=0` returned `200` with:
  - `transcript: ""`
  - `saw_fin: false`
  - `events_seen: 5`

Impact:

- `B5` is no longer blocked at the basic runtime-feasibility level.
- The selected `B` shape can keep a provider relay if we still want that architecture.

### Finding 2

The current app's stop contract is tied to Soniox finalization, not to provider `finished`.

Evidence:

- The existing backend sets its final-transcript event when `translate_soniox_event()` sees `<fin>` in [backend/app/stt_soniox.py](../../../backend/app/stt_soniox.py).
- The current stop path waits for `stt_session.wait_for_final_transcript()` or the relay's finalized event in [backend/app/ws.py](../../../backend/app/ws.py).
- In the Durable Object proof, `finalize=1` produced the full transcript and observed `<fin>`, but did not emit provider `finished` before the idle cutoff.

Impact:

- For this app, successful finalization should be judged against `<fin>` and final tokens, not against provider socket closure or a `finished` event.
- The transport adapter can match the existing `SttSession` contract without inventing a new stop rule.

### Finding 3

The Cloudflare Python transport surface has two non-obvious mechanics that matter to the real adapter.

Evidence:

- Cloudflare's `fetch()`-based WebSocket path must use `https://...` with `Upgrade: websocket`, not `wss://...`.
- In Python Workers, the upgraded socket is accessible via `resp.js_object.webSocket`, not `resp.webSocket`.

Impact:

- A direct translation from JavaScript examples into Python wrapper code is not enough.
- The real `B5` adapter should hide these runtime-specific details behind the existing `SttSession` boundary.

### Finding 4

The local Cloudflare proof aligns with the existing real Soniox baseline.

Evidence:

- A direct baseline run with the repo's normal Python `websockets` client and the same fixture produced:
  - without finalize: no complete transcript
  - with finalize: `Stop the button.`
- The Durable Object proof produced the same qualitative behavior.

Impact:

- The local Durable Object path is not merely "connecting somehow"; it is preserving the behavior that matters to the current app.

## Practical Read

`B5` is now proven at the transport-mechanics level.

What is confirmed:

- outbound Soniox handshake from a Python Durable Object
- binary PCM streaming from the Durable Object
- `finalize -> EOS` ordering
- receipt of Soniox token events
- observation of the `<fin>` boundary used by the current app

What remains open:

- integration of this transport into a real `SttSession` adapter
- extraction of the shared live-session core
- end-to-end browser + Worker + Durable Object + Soniox integration

## Outcome

This spike is a positive result.

It does not finish the refactor, but it removes the main remaining feasibility
question against the selected `B` shape.

## Shape Impact

- `B5` provider transport adapter: mechanically viable in the selected runtime shape
- `B1` shared live-session core: still needs extraction
- `B2` local FastAPI adapter: still needs to be reshaped around the shared core

## Recommended Next Step

Do not reopen the top-level shape decision.

The next useful shaping move is to start slicing around the selected `B` shape,
with `B5` treated as implementation work rather than open feasibility risk.
