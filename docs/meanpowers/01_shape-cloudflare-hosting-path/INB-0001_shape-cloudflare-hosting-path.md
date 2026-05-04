# Shape Cloudflare Hosting Path

**Baseline:** The app currently runs as a browser WebSocket frontend talking to a FastAPI backend that relays audio to Soniox and sends todo snapshots back to the browser.

**Target:** The project has a shaped hosting strategy for whether the backend should run on Cloudflare Workers, Durable Objects, or Containers.

**Intent:** Decide whether Cloudflare can host the current live voice pipeline with the least necessary runtime complexity, starting from the hypothesis that a plain Worker may be enough if each browser session is independent.

**Questions for later:** Does the current Python/PydanticAI backend run cleanly in Cloudflare Python Workers? Do Soniox streaming and LLM calls fit Worker runtime limits? Is per-session coordination, resumability, persistent state, or WebSocket hibernation actually needed?

## Source Context

The source discussion proposes Cloudflare as a possible hosting target for the current voice todo project.

The key hypothesis is that a plain Cloudflare Worker may be sufficient for the current flow:

1. The browser opens one WebSocket to the app.
2. The app forwards audio and events to an STT service.
3. The app receives transcript chunks back.
4. The app calls an LLM for structured extraction.
5. The app sends extracted todos back to the same browser.

This is framed as a single-session relay and transform pipeline. If each browser connection can be handled independently, the source discussion argues that Durable Objects are not required just because WebSockets are involved.

## Hypotheses To Shape

- A plain Worker is the simplest first Cloudflare target if each browser session is independent.
- Durable Objects become relevant if the system needs a stable per-session coordinator, persistent per-object state, coordination among multiple clients or connections, resumability, or WebSocket hibernation.
- Containers become relevant if the current Python backend, PydanticAI usage, or dependencies do not fit Cloudflare's Python Workers runtime.

## Notes

- The current architecture is `browser mic -> frontend WebSocket -> FastAPI -> Soniox RT -> TranscriptAccumulator -> ExtractionLoop -> Gemini -> todos snapshots -> frontend`.
- The runtime-fit question is likely more important than the Durable Object question at first.
- The next workflow step should be `meanpowers:shape`, because this is a hosting/runtime architecture decision with material uncertainty.
