# Spike: Publishability And Deployability

## Context

Shape `B` is selected for the hosted Cloudflare demo, with `C` kept as backup. A new concern now matters to shaping: what source code should be published, and how should the repo balance Cloudflare-native hosting with local usability and approachable deployment for others.

This spike focuses on two candidate requirements:

- `R8`: keep the published source usable outside the hosted Cloudflare runtime
- `R9`: provide a friendly documented or one-click deployment path for the Cloudflare demo

## Goal

Clarify how `R8` and `R9` could work in practice in a single repo, and identify the main options and tradeoffs before changing the requirement set.

## Questions

| ID | Question |
|---|---|
| X5-Q1 | Can a single repo support both the selected Cloudflare demo runtime and a local non-Cloudflare run path in a practical way? |
| X5-Q2 | What does satisfying `R8` mean concretely in code structure? |
| X5-Q3 | What are the realistic friendly options for `R9`? |
| X5-Q4 | Does the current repo layout help or hurt one-click Cloudflare deployment? |

## Findings

### Finding 1

The strongest practical interpretation of `R8` is local-run portability, not host-anywhere parity.

Reasoning:

- "Deployable anywhere" is a much larger requirement than "usable locally without Cloudflare".
- The current selected shape `B` is intentionally Cloudflare-native at the hosted runtime boundary.
- The portable value in the published source is therefore best preserved by keeping the live-session core reusable and keeping a non-Cloudflare local adapter available.

Impact:

- The most realistic `R8` is:
  - the public repo supports the hosted Cloudflare demo runtime
  - the same repo also supports local execution without Cloudflare
  - Cloudflare-specific code is isolated so the core logic remains reusable

### Finding 2

The current repo already points toward a single-repo, dual-adapter structure.

Repo evidence:

- The repo already separates `frontend/` and `backend/`.
- The current backend is a FastAPI/WebSocket adapter around a live-session flow.
- The shared live-session logic is already partially separable from the transport layer.

Relevant code:

- [backend/app/ws.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/ws.py:92)
- [backend/app/transcript_accumulator.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/transcript_accumulator.py:18)
- [backend/app/extraction_loop.py](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/app/extraction_loop.py:15)

Impact:

- A practical single-repo structure is:
  - shared Python live-session core
  - local FastAPI adapter for local running and non-Cloudflare reuse
  - Cloudflare Worker + Durable Object adapter for the hosted demo
- This does not require two repos.

### Finding 3

Cloudflare's own Python tooling supports local development for Python Workers, including Durable Objects.

Cloudflare evidence:

- The official Python Workers examples say to use `pywrangler dev` to run a local development server powered by `workerd`.
- The examples include both Durable Objects and WebSocket examples.
- Workers local development supports local simulation of Durable Objects.

Relevant sources:

- https://raw.githubusercontent.com/cloudflare/python-workers-examples/main/README.md
- https://developers.cloudflare.com/workers/development-testing/bindings-per-env/

Impact:

- There are two distinct local paths available in one repo:
  - the current FastAPI local path
  - a Cloudflare-local path through `pywrangler dev` / `wrangler dev`
- This strengthens the case for a single repo rather than a repo split.

### Finding 4

The current repo layout is not immediately ideal for a one-click Deploy to Cloudflare button.

Repo evidence:

- The repo currently has separate `frontend/package.json` and `backend/pyproject.toml`.
- There is no root `wrangler` config or self-contained Worker app directory today.

Relevant code:

- [frontend/package.json](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/frontend/package.json)
- [backend/pyproject.toml](/Users/josselinperrus/conductor/workspaces/voice-todos/doha/backend/pyproject.toml)

Cloudflare evidence:

- Deploy to Cloudflare buttons support Workers applications.
- Monorepos are not fully supported.
- If you use a subdirectory URL, the application must be fully isolated inside that subdirectory, including dependencies.

Relevant source:

- https://developers.cloudflare.com/workers/platform/deploy-buttons/

Impact:

- A one-click button is feasible only if the Cloudflare demo app becomes a self-contained Workers application at the repo root or in a fully isolated subdirectory.
- The current repo shape does not satisfy that out of the box.

### Finding 5

There are three realistic `R9` options, and they differ mainly in friendliness versus structural pressure on the repo.

#### Option R9-A: documented manual Cloudflare deploy

- Provide a clear README path such as:
  - install dependencies
  - configure secrets
  - run `wrangler deploy`
- Lowest structural pressure
- Works well with a shared-code repo
- Least magical, but fully practical

#### Option R9-B: Deploy to Cloudflare button

- Add a button in the README using Cloudflare's official deploy-button flow
- Friendliest onboarding for visitors who want their own hosted copy
- Requires the Cloudflare app to be a self-contained Workers application
- Conflicts with a loose monorepo layout unless the Worker app is isolated properly

Relevant source:

- https://developers.cloudflare.com/workers/platform/deploy-buttons/

#### Option R9-C: both manual deploy and deploy button

- Keep a documented manual path as the baseline
- Add a deploy button only if the Cloudflare app packaging becomes isolated enough
- Best user-facing outcome, but only after the repo structure supports it

Impact:

- `R9-C` is the most attractive end state.
- `R9-A` is the safest near-term requirement.
- `R9-B` should not be promised unless the repo structure is intentionally shaped for it.

### Finding 6

Satisfying `R8` and a friendly `R9` at the same time is possible in one repo, but it pushes the repo toward a more explicit packaging boundary.

Practical shape:

1. Extract a shared Python live-session core.
2. Keep `backend/` as a local FastAPI adapter around that core.
3. Add a dedicated Cloudflare app boundary around the same core.
4. Decide whether the Cloudflare app lives:
   - at repo root, making a deploy button easier, or
   - in an isolated subdirectory, which is also button-compatible if fully self-contained.

Tradeoff:

- The cleaner the deploy-button experience, the more deliberate the Cloudflare app packaging must become.
- The cleaner the shared-code story, the less likely the current repo can stay an informal two-app layout.

## Practical Read

If `R8` is adopted, the strongest practical version is:

- anyone can clone the repo and run the app locally without Cloudflare
- the hosted demo still uses the selected Cloudflare-native runtime
- the shared live-session logic is reused between local and Cloudflare adapters

If `R9` is adopted, the most realistic staging is:

- first: documented manual Cloudflare deploy
- later, if the Cloudflare app packaging is isolated enough: add a Deploy to Cloudflare button

## Suggested Requirement Refinements

These are suggested changes only, not yet applied:

- `R8`: The published repo supports local execution without Cloudflare and isolates Cloudflare-specific runtime code so the live-session core remains reusable.
- `R9a`: The published repo includes one clear documented deployment path for the hosted Cloudflare demo.
- `R9b`: If the Cloudflare demo app is packaged as a self-contained Workers application, the published repo may also provide a Deploy to Cloudflare button.

## Conclusion

You do not need two repos to satisfy the underlying concern.

A single repo is still the best shape if:

- the shared live-session core is extracted cleanly
- local FastAPI remains as the local and portable adapter
- the Cloudflare demo app becomes an explicit adapter boundary

The main open choice is not one repo versus two repos. It is whether `R9` should promise:

- only a documented deploy path now
- or a future one-click Deploy to Cloudflare experience that will require stronger app packaging discipline
