# Spec: Hosted Todo Parity

## Source

- Shaping document: [010_shaping_shape-cloudflare-hosting-path.md](./010_shaping_shape-cloudflare-hosting-path.md)
- Shaping slice: `V3`
- Scope: move todo extraction behavior into a shared core and make the hosted Cloudflare path reach parity with the app's intended todo behavior on top of the already-working hosted transcript/runtime path

## Baseline

After `V2`, the repo has:

- a shared session/transcript/finalization core in:
  - [backend/app/live_session.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/live_session.py)
  - [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/transcript_accumulator.py)
- a local FastAPI `/ws` adapter in [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py)
- a real hosted Cloudflare Worker + Durable Object path in [cloudflare/src/entry.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/entry.py) and [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)
- a hosted Soniox transport path in [cloudflare/src/stt_soniox_cf.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/stt_soniox_cf.py)

But todo behavior is still not shared. The intended app behavior currently lives only in the local path through [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extraction_loop.py) and the local `/ws` adapter's stop/fallback logic in [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py).

That means `V2` proved hosted transcript/runtime behavior, but not hosted todo parity.

## Target System

After this slice:

- todo extraction behavior is shared rather than local-only
- local and hosted adapters both depend on the same todo/extraction coordination core
- the hosted path reaches parity for the app's intended todo behavior:
  - live todo updates when extraction triggers fire
  - final todo handling on stop using the finalized transcript
  - fallback resend behavior when no new final todo send occurs
  - warning behavior for timeout or final extraction failure
  - `todos` before `stopped` ordering where required

The transcript/runtime path from `V2` remains intact. `V3` changes the app behavior above that runtime layer, not the runtime mechanics themselves.

## Architecture

This slice extends the shared-core architecture by adding a shared todo core beside the existing shared session core.

The shared core now has two layers:

1. **Session/transcript/finalization core**
   - already shared after `V1` and reused by `V2`

2. **Todo/extraction coordination core**
   - promoted from the current local-only `ExtractionLoop` behavior
   - owns extraction trigger policy, in-flight serialization, final-stop behavior, fallback decisions, and structured stop outcomes

The adapters remain thin:

- **Local FastAPI adapter** sends browser `transcript`, `todos`, and `stopped`, but no longer owns todo policy
- **Hosted Durable Object adapter** does the same, using the same shared todo core

The extraction model/provider seam remains below this layer in [backend/app/extract.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extract.py) and the model-provider code. `V3` does not redesign provider choice; it only shares the app behavior that calls into extraction.

## Components

- **Shared session core**
  - [backend/app/live_session.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/live_session.py)
  - [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/transcript_accumulator.py)

- **Shared todo core**
  - evolve [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extraction_loop.py) into the runtime-neutral todo coordinator
  - add any narrowly needed shared result types for final-stop todo outcomes

- **Extraction engine seam**
  - [backend/app/extract.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/extract.py)
  - existing model/provider code remains the extraction implementation seam

- **Local adapter**
  - [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/ws.py)

- **Hosted adapter**
  - [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py)

## Data Flow

1. Adapter creates the shared session controller and the shared todo coordinator against the same transcript state.
2. Transcript updates from the shared session core are still sent to the browser as `transcript`.
3. The adapter forwards transcript-change and endpoint signals into the shared todo coordinator.
4. The shared todo coordinator decides when to run background extraction:
   - transcript-threshold trigger
   - endpoint trigger
   - serialized background execution
5. On successful extraction, the shared todo coordinator emits the todo snapshot and the adapter sends browser `todos`.
6. On `stop`, the adapter first stops the shared session core and gets the finalized transcript result.
7. The adapter then asks the shared todo coordinator to complete stop handling against that finalized transcript.
8. The shared todo coordinator returns a structured stop outcome describing whether:
   - final extraction ran
   - final extraction was skipped because transcript was unchanged
   - final extraction was skipped because transcript finalization timed out
   - final extraction failed
   and whether the latest snapshot must be resent
9. The adapter sends the required terminal browser messages, preserving todo/stopped ordering and warning behavior.

## Behavioral Delta

Before this slice:

- hosted transcript behavior works
- hosted todo parity does not exist
- todo extraction policy is still trapped in the local path

After this slice:

- local and hosted adapters use the same todo/extraction behavior
- hosted todo updates and final-stop todo behavior match the app's intended parity surface
- adapter-specific todo policy branches are removed or reduced to browser-message mapping only

## Decisions

- Reuse and evolve `ExtractionLoop` rather than introduce a parallel todo-policy abstraction
- Keep extraction provider/model choice below the shared todo core
- Make final-stop todo behavior a structured shared outcome instead of adapter-local branching
- Keep adapters thin and browser-protocol focused

## Non-Goals

- Rework the hosted transcript/runtime mechanics from `V2`
- Redesign the browser websocket protocol
- Add hosted provider parity beyond what already exists
- Change publishability/deploy/developer-doc scope
- Introduce a new storage or persistence layer for todos

## Design And Implementation Constraints

- Preserve the browser `/ws` contract already consumed by [frontend/src/hooks/useTranscript.ts](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/frontend/src/hooks/useTranscript.ts)
- Preserve local behavior while moving todo policy behind a shared boundary
- Preserve `todos` before `stopped` ordering where the current app behavior requires it
- Preserve final-stop fallback behavior when no new final todo send occurs
- Preserve warning behavior for transcript timeout and final extraction failure
- Keep background extraction non-terminal on failure
- Keep cancellation/generation safety so stale extraction results are not sent after teardown or restart

## Acceptance Gate: Local And Hosted Todo Behavior Are Identical

**Why this gate matters:**
This is the actual delta from `V2`. If local and hosted todo behavior are still materially different, then `V3` has not delivered its slice.

**Criteria:**

- Given the same transcript/extraction conditions, the local `/ws` path and the hosted `/ws` path produce the same todo behavior.
- "Same todo behavior" means:
  - the same live `todos` updates are emitted when extraction triggers fire
  - on `stop`, both use the finalized transcript for final todo handling
  - if no new final todo send occurs but the latest snapshot must be preserved, both resend the latest `todos` snapshot before `stopped`
  - both attach the same warning behavior for transcript timeout and final extraction failure
  - both preserve `todos` before `stopped` ordering when a todo send is required

**Proof:**

- **Local proof:** focused FastAPI `/ws` acceptance tests
- **Hosted proof:** focused Cloudflare acceptance tests or smoke/harness proof
- **Assertions:** verify live todo updates, final-stop extraction behavior, fallback resend behavior, warning behavior, and terminal message ordering are the same in both runtimes for the covered conditions
- **Structural proof:** inspect the code to show both adapters delegate todo behavior to the shared todo core instead of carrying separate todo-policy branches
- **Expected evidence:** local acceptance output, hosted acceptance or smoke output, and code references to the shared todo-core boundary

## Supporting Verification

- Focused shared todo-core unit tests for:
  - threshold-triggered extraction
  - endpoint-triggered extraction
  - unchanged-final-transcript skip behavior
  - timeout skip behavior
  - final extraction failure behavior
  - resend-latest-snapshot behavior
  - cancellation / generation safety
- Focused hosted/runtime tests only where needed to prove adapter integration points
- Narrow backend regression checks for the shared session core only if touched incidentally
