# Shaping: Cloudflare Hosting Path

## Source

- Originating inbox item: [INB-0001_shape-cloudflare-hosting-path.md](INB-0001_shape-cloudflare-hosting-path.md)
- Source conversation/document: Conductor shaping thread for the Cloudflare hosting-path decision
- Shaping started: 2026-04-30
- Shaping confirmed: 2026-04-30

## Baseline

### Current Actor Journeys

- A browser user opens the local app and starts a live voice session over one browser WebSocket.
- The FastAPI backend opens one Soniox real-time session, forwards browser audio, receives transcript events, runs todo extraction, and sends transcript/todo updates back to the same browser session.
- On stop, the backend requests finalization from Soniox, waits for the final-transcript boundary, runs final todo extraction, and returns the finalized transcript plus the final todo snapshot.

### Current Observable Behavior

- The current app works locally through a browser frontend and a FastAPI backend.
- During a session, the user sees transcript updates and todo snapshots.
- On stop, the user receives a finalized transcript and final todo results.
- The current hosted/demo path does not exist yet.

### Current Components / Internals

- The live session is currently orchestrated largely inside `backend/app/ws.py`.
- The Soniox transport in `backend/app/stt_soniox.py` depends on Python `websockets`.
- `backend/app/stt.py`, `backend/app/transcript_accumulator.py`, `backend/app/extraction_loop.py`, and `backend/app/extract.py` already contain logic that is mostly runtime-neutral.
- Optional session recording writes to the local filesystem and is not required for the hosted demo path.

## Requirements (R)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| R0 | A hosted Cloudflare deployment supports the current live voice todo session from browser audio to transcript and todo updates. | Core goal | |
| R1 | Each browser session is handled independently. | Must-have | Matches the current runtime shape. |
| R2 | The hosted runtime can maintain the browser session while calling external STT and LLM providers. | Must-have | Soniox and extraction calls are in the critical path. |
| R3 | Stop returns a finalized transcript and a final todo snapshot before the session ends. | Must-have | Matches current stop behavior. |
| R4 | The hosted system coordinates shared state across multiple browser sessions. | Out | Not required by the current app behavior. |
| R5 | Session state survives reconnects or resumes after disconnect. | Out | Not part of the current app behavior. |
| R6 | The hosted live path writes session artifacts to a local filesystem. | Out | Not required for the hosted demo path. |
| R7 | Hosted demo sessions are capped to a short maximum duration, likely around one to two minutes. | Must-have | Protects cost and abuse exposure for the public portfolio demo. |
| R8 | The published repo supports local execution without Cloudflare in the same repo as the hosted Cloudflare demo path, while isolating Cloudflare-specific runtime code from the shared live-session core. | Must-have | Protects publishability and local reusability without requiring two repos. |
| R9 | The published repo includes one clear documented deployment path for the hosted Cloudflare demo. | Must-have | A Deploy to Cloudflare button is optional later if the Cloudflare app packaging becomes self-contained enough. |

## Journeys (J)

| ID | Journey / Step | Actor | Description |
|---|---|---|---|
| J1 | Run a live voice todo session | end user | User starts recording in the browser and sees transcript and todos update during the session. |
| J1.1 | Open the session | browser + hosted runtime | Browser opens one WebSocket connection to the hosted app. |
| J1.2 | Stream audio to STT | hosted runtime | Hosted runtime opens the provider connection and forwards audio and control events. |
| J1.3 | Receive live transcript updates | end user | Browser receives transcript token updates while speaking. |
| J1.4 | Receive todo snapshots | end user | Browser receives updated todo snapshots as extraction runs. |
| J1.5 | Stop and finalize | end user | Browser stops recording and receives finalized transcript plus final todos before session close. |

## Shapes (S)

### Shape Options

| ID | Shape | Summary | Status |
|---|---|---|---|
| A | Python Worker live-session rewrite | Rewrite the live session for Python Workers with Worker-native handling for both the inbound browser WebSocket path and the outbound provider WebSocket path, plus a Python-Worker-compatible dependency set, while preserving the current end-user session behavior. | Excluded |
| B | Worker front door + session-owned Durable Object runtime | Route each live demo session through a Worker into one Durable Object that owns the browser WebSocket, the outbound provider connection, and the transcript/extraction/finalization state for that session, with hibernation treated as optional rather than central. | Selected |
| C | Worker front door + Container session runtime | Use a Worker for ingress and routing, and run the near-current Python relay/runtime inside Cloudflare Containers. | Backup |

### Selected Shape Components

| ID | Component | Flag | Notes |
|---|---|:---:|---|
| B1a | Shared session / transcript / finalization core |  | Extract the current session orchestration out of `backend/app/ws.py` and keep transcript accumulation, transcript finalization, and provider-neutral session flow reusable across runtimes. Reuse `backend/app/stt.py` and `backend/app/transcript_accumulator.py` where possible. |
| B1b | Shared todo / extraction core |  | Keep todo extraction triggering and final todo generation reusable across runtimes. Reuse `backend/app/extraction_loop.py` and `backend/app/extract.py` where possible. |
| B2 | Local FastAPI adapter |  | Keep a local non-Cloudflare run path in the same repo. Preserve the current browser contract at `/ws` for local development and source reuse, and adapt the existing FastAPI route into an adapter around the shared cores. |
| B3 | Cloudflare Worker front door |  | Accept the browser session at the edge and route it to one session-owned Durable Object. Keep the browser-visible protocol aligned with `frontend/src/hooks/useTranscript.ts`. |
| B4 | Session-owned Durable Object runtime |  | One Durable Object owns one live session: the inbound browser connection, the outbound provider connection, and the session state through stop/finalization. Hibernation is optional and not central to this demo shape. |
| B5 | Provider transport adapter |  | Replace the current Soniox transport in `backend/app/stt_soniox.py`, which depends on Python `websockets`, with a Cloudflare-compatible transport behind the `SttSession` abstraction. The `X7` spike proved this is mechanically viable. |
| B6 | Session policy and teardown |  | Enforce the public-demo session cap and close browser and provider connections cleanly on stop, timeout, or failure. |
| B7 | Packaging and deployment boundary |  | Keep one repo and separate the shared core, the local adapter, and the Cloudflare adapter clearly enough that the hosted demo can run on Cloudflare while anyone can still run locally without Cloudflare. Treat a documented Cloudflare deploy path as the baseline. |
| B8 | Optional Deploy to Cloudflare packaging | WARNING | Add a self-contained Workers app boundary only if a one-click Deploy to Cloudflare button is later desired. This is optional and depends on packaging discipline, not on core app behavior. |

## Fit Check

| Req | Requirement | Status | A | B | C |
|---|---|---|---|---|---|
| R0 | A hosted Cloudflare deployment supports the current live voice todo session from browser audio to transcript and todo updates. | Core goal | PASS | PASS | PASS |
| R1 | Each browser session is handled independently. | Must-have | PASS | PASS | PASS |
| R2 | The hosted runtime can maintain the browser session while calling external STT and LLM providers. | Must-have | PASS | PASS | PASS |
| R3 | Stop returns a finalized transcript and a final todo snapshot before the session ends. | Must-have | PASS | PASS | PASS |
| R4 | The hosted system coordinates shared state across multiple browser sessions. | Out | PASS | PASS | PASS |
| R5 | Session state survives reconnects or resumes after disconnect. | Out | PASS | PASS | PASS |
| R6 | The hosted live path writes session artifacts to a local filesystem. | Out | PASS | PASS | PASS |
| R7 | Hosted demo sessions are capped to a short maximum duration, likely around one to two minutes. | Must-have | PASS | PASS | PASS |
| R8 | The published repo supports local execution without Cloudflare in the same repo as the hosted Cloudflare demo path, while isolating Cloudflare-specific runtime code from the shared live-session core. | Must-have | PASS | PASS | PASS |
| R9 | The published repo includes one clear documented deployment path for the hosted Cloudflare demo. | Must-have | PASS | PASS | PASS |

**Notes:**

- The fit check does not reveal any missing requirement coverage in the current shape set.
- `B` is selected because of platform fit and refactor tradeoffs, not because `A` or `C` fail a stated requirement.
- `B8` remains optional and packaging-dependent, so it is not a blocker for slicing.

## Selected Shape

**Selected option:**

`B` Worker front door + session-owned Durable Object runtime

**Why this shape:**

`B` is the best fit for the app's current live-session model and the best fit for Cloudflare's current Python WebSocket patterns. The spikes confirmed that:

- one browser session maps cleanly to one Durable Object session owner
- the local Cloudflare runtime can host the Worker + Durable Object session shape
- the outbound Soniox transport is mechanically viable inside that runtime

This shape also preserves one-repo local usability by keeping shared live-session logic separate from the Cloudflare-specific runtime adapters.

**Key tradeoffs:**

- Cloudflare-specific runtime code at the session edge is accepted in exchange for a cleaner platform fit.
- Portability is preserved in the shared cores and local adapter, not by making the hosted runtime itself host-anywhere.
- One-click Cloudflare deploy remains optional and is not part of the baseline shaped solution.

**Rejected options:**

- `A` was excluded because it remained Cloudflare-specific while being less aligned with the platform and more rewrite-heavy than `B`.
- `C` remains a valid backup for portability-first priorities, but it adds paid-plan dependence and container cold-start concerns without being the best-fit Cloudflare runtime shape.

## Final Slices

### Selected Slicing Logic

**Rationale:**

This option minimizes migration rework by creating the shared seam before hosted integration, then proving the hosted path before completing parity and publication.

**Sequence:**

`V1` separates shared core logic from runtime-specific adapters so the Cloudflare path has a clean attachment point. `V2` uses that seam to add the first real Cloudflare path for session ownership, transcript flow, and stop finalization. `V3` extends that already-working hosted path to the remaining app behavior: shared todo/extraction parity. `V4` documents the now-stable local and hosted paths for publication and deployment.

**Demo scenario:**

The same short voice-todo flow is reused across slices, but what it proves changes: `V1` proves the local path now goes through the shared seam, `V2` proves that flow works through a real Cloudflare transcript path, `V3` proves hosted todo parity on top of that runtime, and `V4` proves the finished system can be run locally and deployed to Cloudflare from the docs.

**Notes for `meanpowers:write-spec`:**

- Treat these as technical slices with clear intermediate system states, not feature slices with large UI deltas.
- Do not add temporary scaffolding that the completed spikes already made unnecessary.
- `B8` remains optional and out of baseline scope.

**Map:**

| Component | V1 | V2 | V3 | V4 |
|---|---:|---:|---:|---:|
| B1a Shared session / transcript / finalization core | X |  |  |  |
| B1b Shared todo / extraction core |  |  | X |  |
| B2 Local FastAPI adapter | X |  |  |  |
| B3 Cloudflare Worker front door |  | X |  |  |
| B4 Session-owned Durable Object runtime |  | X |  |  |
| B5 Provider transport adapter |  | X |  |  |
| B6 Session policy and teardown |  | X |  |  |
| B7 Packaging and deployment boundary |  |  |  | X |
| B8 Optional Deploy to Cloudflare packaging |  |  |  | optional |

### V1: Shared Session Core In The Local Path

**State after this slice:**

- The local FastAPI app still supports the current end-to-end voice flow.
- Session, transcript, and finalization logic are no longer centered in `backend/app/ws.py`.
- The local route becomes an adapter around the shared session core.
- Todo/extraction behavior may still be local to the FastAPI path at this point.

**Included components:**

- B1a
- B2

**Notes for write-spec:**

- Acceptance should prove local behavioral parity for session start, live transcript flow, and stop finalization.
- This slice is about creating the shared seam; no hosted path exists yet.

### V2: Real Hosted Transcript Path

**State after this slice:**

- A real Cloudflare Worker + Durable Object path exists.
- The hosted path can accept a session, stream audio to Soniox, emit transcript updates, enforce the session cap, and return a finalized transcript on stop.
- The selected hosted runtime shape is now product code rather than only spike code.
- Hosted todo behavior is not yet at parity.

**Included components:**

- B3
- B4
- B5
- B6

**Notes for write-spec:**

- Acceptance should target real Soniox transcript behavior and the real stop contract: finalize, EOS, and finalized transcript.
- This is the first real Cloudflare endpoint, but hosted todo behavior remains intentionally incomplete.

### V3: Hosted Todo Parity

**State after this slice:**

- Todo extraction behavior is shared rather than trapped in the local path.
- The hosted path now reaches parity for the app's todo behavior, including the final todo snapshot on stop and the intended session-time todo updates.
- Local and hosted runtimes now depend on the same extraction/todo core.

**Included components:**

- B1b

**Notes for write-spec:**

- Acceptance should prove the change from `V2`: hosted todo behavior, not transcript/runtime mechanics.
- The spec should be explicit about what hosted parity means for live todo updates versus final-stop todo generation.

### V4: Publishable Repo And Deploy Path

**State after this slice:**

- The repo has a documented local run path.
- The repo has a documented Cloudflare deploy path for the hosted demo.
- The architecture is publishable as one repo with local and hosted adapters around shared cores.
- `B8` remains optional unless a one-click Deploy to Cloudflare button is explicitly chosen later.

**Included components:**

- B7

**Notes for write-spec:**

- Acceptance should prove the operational delta from `V3`: someone can now run locally and deploy to Cloudflare from a clean checkout.
- Do not pull `B8` into scope unless a one-click deploy experience is explicitly required.

## Spikes

| Spike | Question | Outcome | Shape impact |
|---|---|---|---|
| [010_spike_python-worker-live-path.md](010_spike_python-worker-live-path.md) | Can Shape `A` run the current live path on Cloudflare Python Workers without falling back to Durable Objects or Containers? | The current backend shape is not a near-direct Python Worker port; the main issue is runtime compatibility, not WebSocket support in principle. | Narrowed `A`, strengthened `B`, kept `C` as low-risk backup. |
| [010_spike_fastapi-websocket-boundary.md](010_spike_fastapi-websocket-boundary.md) | Can the browser-facing FastAPI WebSocket boundary plausibly stay intact inside Python Workers? | Current evidence does not support assuming the FastAPI WebSocket route ports cleanly. | Reinforced `B` and further narrowed `A`. |
| [010_spike_shape-b-durable-object-session.md](010_spike_shape-b-durable-object-session.md) | What does `B` mean concretely for the current live session? | One Durable Object per live session maps cleanly to the app boundary and fits the capped demo use case. | Made `B` a real session-runtime shape. |
| [010_spike_shape-b-refactor-impact.md](010_spike_shape-b-refactor-impact.md) | What is the concrete refactor impact of choosing `B`? | The refactor is concentrated around `backend/app/ws.py` and the Soniox transport, not whole-app-wide. | Clarified the shared-core + adapter architecture. |
| [010_spike_publishability-and-deployability.md](010_spike_publishability-and-deployability.md) | How can the repo stay locally usable while also supporting a friendly Cloudflare deployment path? | One repo with shared cores plus local and Cloudflare adapters is practical; one-click deploy is packaging-dependent. | Strengthened `R8`, `R9`, and `B7`. |
| [010_spike_x6_local-cloudflare-session-skeleton.md](010_spike_x6_local-cloudflare-session-skeleton.md) | Can the selected `B` runtime shape run locally as a minimal Worker + Durable Object session skeleton? | Local Worker + Durable Object session ownership and browser protocol shape are practical. | Confirmed `B3`, `B4`, and the basic `B6` runtime shape. |
| [010_spike_x7_soniox-provider-transport.md](010_spike_x7_soniox-provider-transport.md) | Can the selected `B` runtime shape carry the real Soniox outbound transport inside a Python Durable Object? | The Durable Object proof reproduced the repo's finalize behavior and recovered the full transcript with `finalize=1`. | Confirmed `B5` as implementation work rather than open feasibility risk. |

## Decision Record

| Decision | Rationale | Rejected Options |
|---|---|---|
| Select Shape `B` | Best Cloudflare-native fit for one-browser-session / one-provider-session ownership, with the strongest spike evidence. | `A`, `C` |
| Keep one repo with shared cores plus local and hosted adapters | Satisfies `R8` without splitting the project into separate products or repos. | Two repos; Cloudflare-only code path |
| Exclude hosted local-file recording | Demo hosting does not require local filesystem artifacts. | Carry the current recording path into the hosted runtime |
| Treat one-click Cloudflare deploy as optional | Packaging-dependent convenience should not distort the core shape. | Making one-click deploy a baseline requirement |
| Use four technical slices | The work crosses four real transition steps: shared session core, hosted transcript/runtime path, hosted todo parity, and publishability/deployability. | Artificially balancing three slices; thin docs-only early slices |

## External Reference Notes

- Cloudflare Workers WebSockets and Durable Objects support the selected session-owned runtime model.
- Cloudflare Python Workers local tooling (`pywrangler dev`) is sufficient for local spike validation of Worker + Durable Object mechanics.
- Cloudflare Containers remain a valid backup but introduce paid-plan dependence and cold-start concerns.
- Soniox real-time finalization behavior is a key part of the app's stop contract; `<fin>` is the important boundary, not necessarily provider `finished`.

## Handoff To Write-Spec

- Final shape confirmed by user: yes
- Final slices confirmed by user: yes
- Slices ready for spec: `V1`, `V2`, `V3`, `V4`
- Open questions for spec:
  - Define the exact acceptance surface for hosted todo parity in `V3`, especially the expected behavior of live todo updates versus final-stop todo generation.
  - Decide whether `B8` remains out of scope for the initial implementation.

REQUIRED NEXT SKILL: `meanpowers:write-spec`
