# Spec: Hosted STT Provider Parity

## Source

- Follow-on work identified after `V3`
- Extends the hosted runtime beyond Soniox-only support
- Includes a preparatory refactor slice so both Soniox and Mistral follow the same provider boundary

## Scope

This spec contains two sequential slices:

1. `V4b.1`: shared provider normalization boundary
2. `V4b.2`: hosted STT provider parity

The first slice is structural with semantic non-regression requirements. The second slice is the actual hosted behavior expansion.

## Baseline

After `V3`, the hosted Cloudflare runtime supports only Soniox at the hosted STT factory edge:

- [cloudflare/src/stt_factory_cf.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/stt_factory_cf.py) rejects any hosted `stt_provider` other than `soniox`
- [cloudflare/src/stt_soniox_cf.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/stt_soniox_cf.py) owns both:
  - Cloudflare-specific connection mechanics
  - Soniox normalization/config/capability logic

Meanwhile the local app already supports both Soniox and Mistral:

- [backend/app/stt_factory.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt_factory.py)
- [backend/app/stt_soniox.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt_soniox.py)
- [backend/app/stt_mistral.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/app/stt_mistral.py)

That leaves two gaps:

- hosted provider choice is not at parity with local
- provider architecture is asymmetric, because normalization logic is not consistently shared across providers/runtimes

## Target System

After both slices:

- Soniox and Mistral both follow the same architecture:
  - shared provider normalization/capability logic
  - local transport adapter
  - hosted transport adapter
- the shared session core and hosted session runtime remain provider-agnostic
- the hosted Cloudflare runtime supports `stt_provider="soniox"` and `stt_provider="mistral"`
- hosted Mistral behavior matches the accepted browser-visible session behavior already established for local Mistral

## Architecture

Provider handling should be symmetric across providers and across runtimes.

Target shape:

```text
shared/
  stt.py
  stt_soniox_shared.py
  stt_mistral_shared.py

backend/app/
  stt_factory.py
  stt_soniox.py
  stt_mistral.py

cloudflare/src/
  stt_factory_cf.py
  stt_soniox_cf.py
  stt_mistral_cf.py
```

The boundary is:

- **shared** owns provider semantics:
  - capabilities
  - config payload builders if runtime-neutral
  - raw-event normalization into `SttEvent`
  - final transcript semantics where applicable
- **local/hosted adapters** own only runtime-specific connection mechanics
- **factories** own provider selection only
- **session runtime and shared session core** remain provider-agnostic

This means Soniox is also cleaned up to match the same shape as Mistral rather than leaving one provider with shared semantics and the other with embedded adapter semantics.

## Components

- **Shared STT contract**
  - existing `SttSession`, `SttEvent`, `SttCapabilities` contract remains the seam
- **Shared Soniox normalization layer**
  - extract Soniox config/capabilities/event translation into shared code
- **Shared Mistral normalization layer**
  - extract or preserve Mistral capabilities/event translation in shared code
- **Local STT adapters**
  - keep local websocket/client connection mechanics in local adapter files
- **Hosted STT adapters**
  - keep Cloudflare outbound connection mechanics in hosted adapter files
  - add [cloudflare/src/stt_mistral_cf.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/stt_mistral_cf.py) in the second slice
- **Factory seams**
  - local and hosted factories dispatch on provider name but do not own provider semantics

## Data Flow

**Slice `V4b.1`: shared provider normalization boundary**
1. local and hosted transport adapters open provider-specific outbound connections as they do today.
2. raw provider messages are read inside those transport adapters.
3. raw provider messages are passed into shared provider normalization logic.
4. shared provider normalization returns the `SttEvent` semantics used by the shared session controller.
5. browser-visible session behavior remains unchanged.

**Slice `V4b.2`: hosted STT provider parity**
1. hosted settings choose `stt_provider`.
2. [cloudflare/src/stt_factory_cf.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/stt_factory_cf.py) dispatches:
   - `soniox` to hosted Soniox transport
   - `mistral` to hosted Mistral transport
3. the chosen hosted transport opens the runtime-specific outbound provider connection.
4. shared provider normalization translates provider messages into `SttEvent`s.
5. the shared session core and hosted session runtime continue transcript, todo, stop, and teardown behavior without provider-specific branching.

## Structural And Behavioral Delta

Before this spec:

- hosted supports only Soniox
- provider semantics are not consistently shared across providers and runtimes

After `V4b.1`:

- provider normalization semantics are shared for both Soniox and Mistral
- no browser-visible change is intended

After `V4b.2`:

- hosted supports both Soniox and Mistral
- hosted Mistral follows the same accepted session behavior above the provider seam

## Decisions

- Include the provider-boundary cleanup in the same spec, but as an earlier slice
- Use the same architecture for Soniox and Mistral
- Keep session/controller/runtime layers provider-agnostic
- Treat hosted Mistral enablement as a separate behavioral delta after the refactor slice
- Prefer shared provider normalization over duplicating event-translation semantics across runtimes

## Non-Goals

- No browser protocol change
- No changes to todo extraction behavior
- No redesign of the shared session controller contract
- No requirement in this spec to add hosted LLM-provider parity
- No deploy/documentation scope

## Design And Implementation Constraints

- Shared provider normalization modules must remain runtime-neutral
- `session_runtime.py` must not branch on provider-specific transcript semantics
- `stt_factory_cf.py` may branch on provider name, but not own provider translation logic
- Hosted Mistral must preserve the accepted stop/final transcript behavior already established locally
- Existing Soniox browser-visible behavior must not regress while extracting shared Soniox semantics

## Acceptance Gate: Provider Normalization Semantics Are Shared Without Regression

**Why this gate matters:**
This is the refactor slice that makes the provider architecture coherent. If provider semantics remain duplicated or drift during the extraction, hosted parity work will be built on an inconsistent seam.

**Criteria**

- Soniox and Mistral normalization/capability logic lives in shared runtime-neutral modules.
- Local and hosted adapters for the same provider depend on the same shared normalization logic.
- Extracting shared provider normalization does not change the accepted provider transcript/finalization semantics.

**Proof**

- **Structural proof**
  - inspect the provider modules and show:
    - shared Soniox normalization exists
    - shared Mistral normalization exists
    - local and hosted Soniox adapters import shared Soniox logic
    - local and hosted Mistral adapters import shared Mistral logic
- **Semantic non-regression proof**
  - run existing local Mistral tests that define accepted translation/session semantics:
    ```bash
    cd backend && uv run pytest \
      tests/test_stt_mistral.py \
      tests/test_stt_factory.py::test_create_stt_session_routes_mistral_provider_to_mistral_connector \
      tests/test_stt_factory.py::test_create_stt_session_routes_mistral_events_to_provider_recorder \
      tests/test_stt_factory.py::test_create_stt_session_rejects_mistral_without_api_key -v
    ```
  - run focused local Soniox/provider regression tests or add them if missing, to prove Soniox shared extraction did not change accepted semantics
  - run focused hosted Soniox adapter tests to prove the hosted path now depends on shared Soniox normalization without changing behavior

**Expected evidence**

- code references showing both runtimes import shared normalization modules for each provider
- pytest output for the named provider semantic/regression tests
- explicit note if a small new Soniox semantic-regression test had to be added because the current suite did not pin a required behavior

## Acceptance Gate: Hosted Runtime Supports Both STT Providers

**Why this gate matters:**
This is the actual hosted parity outcome. If the Cloudflare runtime still only supports Soniox, the slice has not delivered the requested capability.

**Criteria**

- Hosted provider selection accepts both `soniox` and `mistral`.
- When hosted `stt_provider="mistral"`, the hosted `/ws` path preserves the accepted browser-visible session behavior above the provider seam.
- Hosted Mistral startup rejects missing `MISTRAL_API_KEY` with the expected hosted failure behavior.
- Hosted session/controller/runtime layers remain provider-agnostic; provider choice stays behind the hosted factory and adapter seam.

**Proof**

- **Hosted factory proof**
  - run hosted factory tests proving:
    - `mistral` dispatches to the hosted Mistral connector
    - missing `MISTRAL_API_KEY` is rejected
- **Hosted Mistral session proof**
  - run focused hosted acceptance tests for Mistral that cover:
    - transcript streaming
    - finalized-transcript stop handling
    - terminal ordering
  - these should mirror the accepted local Mistral session behavior already covered in:
    - [backend/tests/test_ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/backend/tests/test_ws.py)
- **Structural seam proof**
  - inspect [cloudflare/src/session_runtime.py](/Users/josselinperrus/conductor/workspaces/voice-todos/florence/cloudflare/src/session_runtime.py) to show it does not branch on provider-specific transcript semantics

**Expected evidence**

- named hosted factory test output
- named hosted Mistral acceptance test output
- code references showing factory dispatch and provider-agnostic hosted session runtime

## Supporting Verification

- focused lint/type checks for shared provider modules and hosted adapter modules
- optional hosted runtime smoke for Soniox and Mistral after parity lands
- focused local `/ws` Mistral regression checks if the shared normalization refactor touches local provider behavior above the adapter seam
