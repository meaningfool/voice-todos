# Spike: Shape B Durable Object Session

## Context

Shape `B` proposes one Durable Object per live session. After the previous spikes, this is the strongest Cloudflare-native candidate for the current portfolio-demo use case. The open question is what this shape means concretely for session ownership, free-tier fit, hibernation, and runtime behavior.

## Goal

Turn Shape `B` into a concrete session model and clarify whether it is a credible fit for the current public-demo use case.

## Questions

| ID | Question |
|---|---|
| X3-Q1 | What is the concrete runtime responsibility split for a one-Durable-Object-per-session design? |
| X3-Q2 | Does hibernation materially help this app shape, given that the session also needs an outbound provider WebSocket? |
| X3-Q3 | Is Shape `B` a credible Workers Free fit for the intended one-to-two-minute demo session? |
| X3-Q4 | Are there latency or lifecycle concerns that materially weaken Shape `B` for the portfolio-demo use case? |

## Findings

### Finding 1

Shape `B` maps cleanly to the current live-session boundary.

Repo evidence:

- The current live path is already one browser WebSocket session, one STT session, and one extraction loop with no shared cross-session coordinator.

Relevant code:

- [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/ws.py:92)
- [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/extraction_loop.py:15)

Cloudflare evidence:

- Durable Objects are single-threaded, stateful instances with unique identity.
- Durable Objects are intended for long-lived WebSocket sessions and can scale horizontally across many objects.

Relevant sources:

- https://developers.cloudflare.com/durable-objects/concepts/what-are-durable-objects/
- https://developers.cloudflare.com/durable-objects/best-practices/rules-of-durable-objects/
- https://developers.cloudflare.com/durable-objects/best-practices/websockets/

Impact:

- A practical `B` shape is:
  - Worker front door accepts the initial request and routes it to a new or deterministic session object
  - one Durable Object owns the browser session
  - that Durable Object opens and owns the outbound provider connection
  - extraction state, transcript accumulation, and finalization state live with that object for the duration of the session

### Finding 2

Hibernation is not the main value of `B` for the active transcription session.

Cloudflare evidence:

- The Hibernation API keeps inbound client WebSockets connected while the Durable Object sleeps.
- Outgoing WebSockets do not hibernate.
- A Durable Object that is active or idle-but-non-hibernateable incurs duration charges.

Relevant sources:

- https://developers.cloudflare.com/durable-objects/best-practices/websockets/
- https://developers.cloudflare.com/durable-objects/examples/websocket-hibernation-server/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/durable-objects/concepts/durable-object-lifecycle/

Impact:

- During the live session, the outbound Soniox-style provider connection means hibernation is not the primary cost story.
- For this app shape, the main value of `B` is session ownership and runtime fit, not hibernation economics.
- If the app closes the session promptly after stop, hibernation may be unnecessary for the public-demo path.

### Finding 3

Shape `B` is a credible Workers Free fit for the intended demo usage.

Cloudflare evidence:

- Durable Objects are available on Free and Paid plans.
- Free includes 100,000 requests/day and 13,000 GB-s/day of duration.
- CPU per Durable Object request or WebSocket message is 30 seconds by default.

Relevant sources:

- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/limits/

Inference:

- If one active session lasts 120 seconds and is billed at the standard 128 MB allocation, that is approximately:
  - `120 seconds * 0.128 GB = 15.36 GB-s` per two-minute session
- At that rate, the Free plan's 13,000 GB-s/day duration allowance corresponds to roughly:
  - `13,000 / 15.36 = ~846` fully active two-minute sessions per day

Impact:

- This is comfortably above the expected portfolio-demo traffic described so far.
- `B` should be treated as a plausible Free-tier candidate for the current use case.

### Finding 4

Shape `B` has a cleaner platform fit than `A`, but it is still Cloudflare-specific at the session-runtime boundary.

Cloudflare evidence:

- Durable Objects are a Cloudflare-specific stateful runtime primitive.
- Objects are created close to where they are first requested and remain tied to that object identity and location model.

Relevant sources:

- https://developers.cloudflare.com/durable-objects/concepts/what-are-durable-objects/
- https://developers.cloudflare.com/durable-objects/reference/data-location/

Impact:

- `B` is not a portable runtime shape in the same way `C` is.
- It can still share business logic with other runtimes if the session/runtime adapter boundary is kept clean.
- The Cloudflare-specific pieces are:
  - session object routing
  - WebSocket acceptance in the Durable Object
  - object lifecycle and optional hibernation handling

### Finding 5

No material latency blocker was found for `B`, but there is also no published startup number comparable to the one Cloudflare gives for Containers.

Cloudflare evidence:

- Durable Objects "start up quickly when needed".
- An object's constructor runs on first access and again after hibernation or restart.
- The docs do not publish a concrete cold-start latency target for Durable Objects in the inspected sources.

Relevant sources:

- https://developers.cloudflare.com/durable-objects/concepts/what-are-durable-objects/
- https://developers.cloudflare.com/durable-objects/concepts/durable-object-lifecycle/

Impact:

- `B` does not carry the explicit one-to-three-second cold-start warning that `C` does.
- The safer statement is that no specific cold-start figure was found for Durable Objects, but the platform positions them as quick-starting stateful compute.

## Conclusion

Shape `B` is now concrete enough to reason about:

- one Durable Object per demo session is a natural match for the current live-session boundary
- the object can own both browser and provider traffic for the duration of the session
- hibernation is optional rather than central for the current capped-session use case
- the public-demo traffic model makes Workers Free plausible for `B`
- `B` is still a Cloudflare-native runtime shape, not a portability-first shape

## Shape Impact

This spike suggests the current wording of `B` is directionally correct, but its practical interpretation should now be:

- `B` is a session-owned Cloudflare-native runtime shape
- its main benefit is platform fit for live WebSocket session handling
- its main tradeoff is portability, not likely cost
