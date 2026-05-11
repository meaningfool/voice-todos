# Plan: Same-Origin Local Cloudflare App Boundary

> **For agentic workers:** REQUIRED HANDOFF: use `superpowers:executing-plans` to implement this plan task-by-task. `superpowers:subagent-driven-development` is also acceptable if the environment supports it well. Steps use checkbox syntax for tracking.

**Spec:** [031_spec_same-origin-local-cloudflare-app-boundary.md](031_spec_same-origin-local-cloudflare-app-boundary.md)

**Goal:** Make `cloudflare/` the real local same-origin app boundary by serving the built frontend UI and the existing Worker + Durable Object `/ws` runtime from one Cloudflare origin, with a deterministic browser smoke that runs against the Cloudflare-served app rather than the Vite dev server.

**Architecture:** Keep `frontend/` as the UI source of truth, build it with Vite, and sync the build output into `cloudflare/public/`. Configure `cloudflare/wrangler.jsonc` to serve `./public` as SPA assets with an `ASSETS` binding and selective Worker-first routing for `/ws`, so the existing websocket runtime in `cloudflare/src/entry.py` keeps session ownership while frontend routes are served from the same Cloudflare origin. Reuse the existing real-UI fixture mode from `frontend/src/hooks/useTranscript.ts`, but make it build-compatible and drive it through an upgraded `scripts/browser_ui_smoke.sh` smoke script.

**Tech Stack:** React 19, Vite 8, Cloudflare Workers static assets, workers-py, pywrangler, bash, rsync, Vitest, pytest, ruff, ty, `agent-browser`

---

## Scope

This plan covers exactly four deliverables:

1. Define the local Cloudflare app boundary in Wrangler so static frontend routes and `/ws` live on the same origin without the SPA shell swallowing websocket traffic.
2. Add an explicit, repeatable handoff from `frontend/dist/` into `cloudflare/public/`.
3. Make the real app UI’s deterministic fixture path work from the built app, not only from the Vite dev server.
4. Upgrade the existing browser smoke script so it proves the Cloudflare-served real UI, expected transcript/todo flow, and clean stop behavior without relying on the Vite dev server as the browser-facing boundary.

Out of scope for this plan:

- public deployment, DNS, or subdomain work
- a one-command deploy flow
- Cloudflare secrets-contract cleanup beyond what local Cloudflare smoke already needs
- transcript/todo/finalization behavior redesign
- repo restructuring that moves frontend source into `cloudflare/`

---

## File Map

### Cloudflare app boundary and asset handoff

| File | Responsibility |
|------|----------------|
| `cloudflare/wrangler.jsonc` | Define the local same-origin boundary with `assets.directory`, SPA fallback, `ASSETS` binding, and selective Worker-first routing for `/ws` |
| `cloudflare/src/entry.py` | Retain websocket session bootstrap at `/ws`; this should remain the runtime entrypoint above the Durable Object session owner |
| `cloudflare/scripts/sync_frontend_dist.sh` | Refresh `cloudflare/public/` from `frontend/dist/` in one explicit local command |
| `cloudflare/tests/test_assets_config.py` | Pin the Wrangler assets contract so future config edits do not silently break same-origin local serving |
| `cloudflare/tests/test_entry.py` | Prove the retained `/ws` entrypoint still accepts plain websocket sessions and preserves explicit `session=` support |

### Frontend built-app smoke surface

| File | Responsibility |
|------|----------------|
| `frontend/src/hooks/useTranscript.ts` | Keep `new WebSocket(${protocol}//${window.location.host}/ws)` unchanged while making fixture-audio mode available from the built Cloudflare-served app |
| `frontend/src/hooks/useTranscript.test.tsx` | Pin smoke-fixture behavior, fixture-audio asset path, and unchanged `/ws` URL shape |
| `frontend/public/smoke-fixtures/while-speaking-two-todos/audio.pcm` | Built-app deterministic smoke audio shipped with the frontend build |

### Browser validation surface

| File | Responsibility |
|------|----------------|
| `scripts/browser_ui_smoke.sh` | Repo-owned `agent-browser` smoke that opens the real app UI, starts a session, waits for todo/transcript evidence, stops, and asserts the final state |
| `backend/tests/fixtures/while-speaking-two-todos/result.json` | Existing expected transcript/todo contract that the browser smoke should assert instead of hard-coding ad hoc text |

### Existing tooling that remains supporting, not the acceptance surface

| File | Why it matters |
|------|----------------|
| `frontend/vite.config.ts` | The Vite proxy remains useful for local dev, but it must no longer be the proof surface for this slice |
| `cloudflare/scripts/ws_smoke.py` | Focused direct websocket smoke still protects `/ws` behavior while the browser-facing boundary moves to Cloudflare |
| `cloudflare/tests/test_ws_smoke.py` | Preserves the direct websocket smoke contract during the same-origin boundary work |
| `cloudflare/dev/todo_parity_browser_check.html` | May remain as a focused debug harness, but it is not the acceptance proof surface for this slice |

---

## Acceptance Gates From Spec

## Acceptance Gate: Local Cloudflare Same-Origin App Works Through The Real UI

**Why this gate matters:**
This slice exists to prove the app boundary, not just the websocket runtime. If
the real UI still cannot be opened directly from the local Cloudflare app
boundary and complete the accepted session flow, then the target shape has not
been established.

**Criteria**

- The local Cloudflare app serves the real frontend UI directly from the same
  origin that serves `/ws`.
- A browser session started from that Cloudflare-served UI reaches the accepted
  voice-todo flow through the existing Worker + Durable Object runtime.
- The local smoke flow is deterministic and does not require a live microphone.

**Proof**

- **Setup**
  - build the frontend for Cloudflare consumption
  - start the local Cloudflare app boundary from `cloudflare/`
- **Action**
  - open the local Cloudflare URL in a browser
  - invoke the real app UI’s local deterministic smoke path using the accepted
    `while-speaking-two-todos` fixture scenario or equivalent deterministic
    smoke mechanism that can later be reused by `V2`
  - start the session and stop it through normal UI interaction
- **Assertions**
  - the app loads from the Cloudflare-served origin rather than the Vite dev
    server
  - the browser websocket connects to same-origin `/ws`
  - during the run, the UI shows transcript activity and todo updates
  - after stop, the UI shows the finalized transcript, the expected final todo
    list for the fixture, and returns to the normal idle/start state

**Expected evidence**

- exact frontend build and local Cloudflare startup commands
- exact `agent-browser` commands used against the Cloudflare-served app
- observed browser-visible outcomes proving transcript flow, todo flow, and
  clean stop on the same origin

## Acceptance Gate: Local Cloudflare App Boundary And Asset Handoff Are Explicit

**Why this gate matters:**
One successful browser run is not enough if the local Cloudflare app boundary
still depends on hidden manual steps or a muddled source-of-truth boundary. The
slice must leave behind a clear and repeatable local app shape.

**Criteria**

- `frontend/` remains the source of truth for UI code.
- `cloudflare/` consumes built frontend assets rather than duplicating UI source
  files.
- The local Cloudflare boundary explicitly serves frontend routes in addition to
  `/ws`.
- The local same-origin smoke path no longer depends on the Vite websocket proxy
  as its app boundary.

**Proof**

- **Code-boundary proof**
  - inspect the files that define:
    - the frontend build output handoff
    - the Cloudflare static asset serving boundary
    - the retained `/ws` entrypoint
- **Process proof**
  - show the explicit command or documented procedure used to refresh the
    frontend assets consumed by `cloudflare/`
  - verify that the local Cloudflare smoke run can be executed without running
    the Vite dev server as the browser-facing app boundary

**Expected evidence**

- code references showing asset handoff and same-origin Cloudflare serving
- exact command or documented procedure for refreshing the frontend assets used
  by `cloudflare/`
- brief note confirming whether the Vite dev server remained available only as
  supporting tooling

## Supporting Verification

- run a focused frontend build verification for the asset handoff path

---

## Gate Execution

### Behavioral proof for `Local Cloudflare Same-Origin App Works Through The Real UI`

Build and hand off the frontend assets first:

```bash
cd frontend && pnpm build
cd ../cloudflare && ./scripts/sync_frontend_dist.sh
```

Expected:

- `frontend/dist/index.html` exists
- `cloudflare/public/index.html` exists after the sync command

Start the local Cloudflare app boundary:

```bash
cd cloudflare && set -a && source ../backend/.env && set +a && uv run pywrangler dev --port 8788
```

Expected:

- local Cloudflare serves the app at `http://127.0.0.1:8788/`
- local Cloudflare serves the websocket boundary at `ws://127.0.0.1:8788/ws`

Quick same-host proof before running the browser smoke:

```bash
curl -I http://127.0.0.1:8788/
curl -i http://127.0.0.1:8788/ws
```

Expected:

- `/` returns `200 OK` for the Cloudflare-served app shell
- `/ws` returns the retained websocket-path response for a non-upgrade request, such as `426`, proving the UI and websocket boundary are on the same host even before the browser run

Preferred smoke path using the repo-owned script:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Expected:

- the script opens `http://127.0.0.1:8788/?fixture=while-speaking-two-todos`
- it clicks `Start Session`, waits for `Listening now...`, observes todo text from the fixture result, clicks `Finish Session`, expands `Session details`, and verifies the final transcript and expected final todo list
- it exits `0` and prints a success marker such as `browser-ui-smoke: ok`

Manual `agent-browser` equivalent for debugging or when script output needs raw evidence:

```bash
agent-browser --session 031-cloudflare open "http://127.0.0.1:8788/?fixture=while-speaking-two-todos"
agent-browser --session 031-cloudflare wait --load networkidle
agent-browser --session 031-cloudflare snapshot -i
agent-browser --session 031-cloudflare click <start-session-button-id>
agent-browser --session 031-cloudflare wait --text "Listening now..."
agent-browser --session 031-cloudflare wait --text "Buy oat milk"
agent-browser --session 031-cloudflare wait --text "Email Sarah the revised budget"
agent-browser --session 031-cloudflare snapshot -i
agent-browser --session 031-cloudflare click <finish-session-button-id>
agent-browser --session 031-cloudflare wait --text "Session details"
agent-browser --session 031-cloudflare click <session-details-summary-id>
agent-browser --session 031-cloudflare wait --text "By oat milk tonight. Zen email Sarah the revised budget."
agent-browser --session 031-cloudflare snapshot -i
agent-browser --session 031-cloudflare close
```

Expected:

- the browser-visible app shell comes from port `8788`, not the Vite dev server
- the same real UI flow produces todo cards and the final transcript from `backend/tests/fixtures/while-speaking-two-todos/result.json`
- no Vite dev server is required for the browser-facing app boundary

Evidence to collect:

- exact `pnpm build`, sync-script, and `pywrangler dev` commands used
- either the `scripts/browser_ui_smoke.sh` command or the explicit `agent-browser` command sequence above
- one snapshot during the active session with todo text visible
- one snapshot after stop with `Session details` expanded and the final transcript visible

### Code-boundary and process proof for `Local Cloudflare App Boundary And Asset Handoff Are Explicit`

Code-boundary proof for the Cloudflare serving boundary and retained websocket entry:

```bash
rg -n '"assets"|directory|binding|not_found_handling|run_worker_first' cloudflare/wrangler.jsonc
rg -n 'new WebSocket|window.location.host|fixture|smoke-fixtures' frontend/src/hooks/useTranscript.ts
rg -n 'session|uuid|parse_qs|urlparse' cloudflare/src/entry.py
```

Expected:

- `cloudflare/wrangler.jsonc` shows `./public` as the assets directory, SPA fallback, `ASSETS` binding, and selective Worker-first routing for `/ws`
- `frontend/src/hooks/useTranscript.ts` still constructs websocket URLs from `window.location.host`
- `cloudflare/src/entry.py` still owns `/ws` session bootstrap and does not duplicate frontend asset logic

Process proof for the frontend asset handoff:

```bash
cd frontend && pnpm build
cd ../cloudflare && ./scripts/sync_frontend_dist.sh
test -f public/index.html
find public -maxdepth 2 -type f | sort | sed -n '1,40p'
```

Expected:

- the sync procedure is one explicit repo-owned command after the frontend build
- `public/index.html` and built asset files exist inside `cloudflare/`
- the built asset tree includes the deterministic smoke asset path used by the browser smoke

Config and websocket regression proof:

```bash
cd cloudflare && uv run pytest \
  tests/test_assets_config.py \
  tests/test_entry.py \
  -v
```

Expected:

- config tests pin the static asset boundary and selective Worker-first `/ws` routing
- existing entry tests continue to pass for plain `/ws` and explicit `session=` websocket behavior

Evidence to collect:

- `rg` output from `cloudflare/wrangler.jsonc`, `frontend/src/hooks/useTranscript.ts`, and `cloudflare/src/entry.py`
- the exact `./scripts/sync_frontend_dist.sh` command and its resulting `public/` files
- pytest output from `tests/test_assets_config.py` and `tests/test_entry.py`
- a short note that the Cloudflare browser smoke ran without a Vite dev server serving the app shell

---

## Supporting Verification

Frontend verification:

```bash
cd frontend && pnpm test:run src/hooks/useTranscript.test.tsx
cd frontend && pnpm build
cd frontend && pnpm lint
```

Expected:

- smoke-fixture hook tests PASS
- built-app asset output PASS
- frontend lint PASS

Cloudflare verification:

```bash
cd cloudflare && uv run pytest \
  tests/test_assets_config.py \
  tests/test_entry.py \
  tests/test_ws_smoke.py \
  -v
cd cloudflare && uv run ruff check src tests scripts
cd cloudflare && uv run ty check src
```

Expected:

- Cloudflare config, entry, and websocket smoke tests PASS
- static checks PASS

Direct websocket non-regression smoke:

```bash
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --fixture-path ../backend/tests/fixtures/while-speaking-two-todos/audio.pcm \
  --mode todo-stop \
  --session-id smoke-todo-stop \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1 \
  --expect-todos-min 1 \
  --expect-terminal-type stopped
```

Expected:

- direct `/ws` smoke still PASS while the browser-facing app boundary moves to Cloudflare

Script verification:

```bash
bash -n cloudflare/scripts/sync_frontend_dist.sh
bash -n scripts/browser_ui_smoke.sh
```

Expected:

- both shell scripts parse cleanly

---

## Checkpoint

Do not start `032` or any public deployment work until both `031` acceptance gates pass:

1. `Local Cloudflare Same-Origin App Works Through The Real UI`
2. `Local Cloudflare App Boundary And Asset Handoff Are Explicit`

Supporting verification does not replace either gate.

---

## Task 1.1: Pin the Cloudflare static asset routing contract

**Purpose:**
Make the same-origin local app boundary explicit in Wrangler config and prevent SPA fallback from swallowing `/ws`.

**Files:**
- Create: `cloudflare/tests/test_assets_config.py`
- Modify: `cloudflare/wrangler.jsonc`
- Test: `cloudflare/tests/test_entry.py`

**Supports:**
- Acceptance Gate: `Local Cloudflare App Boundary And Asset Handoff Are Explicit`
- Supporting Verification: Cloudflare config and websocket regression tests

- [ ] **Step 1: Write the failing config tests**

Add focused tests such as:

```python
from pathlib import Path

WRANGLER = Path(__file__).resolve().parents[1] / "wrangler.jsonc"

def test_wrangler_config_serves_public_assets_with_spa_fallback():
    text = WRANGLER.read_text()
    assert '"directory": "./public"' in text
    assert '"binding": "ASSETS"' in text
    assert '"not_found_handling": "single-page-application"' in text

def test_wrangler_config_runs_worker_first_for_ws():
    text = WRANGLER.read_text()
    assert '"run_worker_first": ["/ws"]' in text
```

- [ ] **Step 2: Run the test to confirm the current config is incomplete**

Run: `cd cloudflare && uv run pytest tests/test_assets_config.py -v`

Expected: FAIL because `cloudflare/wrangler.jsonc` does not yet define the frontend asset boundary.

- [ ] **Step 3: Write the minimal config change**

Update `cloudflare/wrangler.jsonc` to add:

```jsonc
"assets": {
  "directory": "./public",
  "binding": "ASSETS",
  "not_found_handling": "single-page-application",
  "run_worker_first": ["/ws"]
}
```

Keep the existing `main`, `durable_objects`, and secret config intact.

- [ ] **Step 4: Run focused verification**

Run: `cd cloudflare && uv run pytest tests/test_assets_config.py tests/test_entry.py -v`

Expected: PASS, proving the config now declares the static asset boundary and `/ws` behavior remains intact.

- [ ] **Step 5: Commit**

```bash
git add cloudflare/wrangler.jsonc cloudflare/tests/test_assets_config.py
git commit -m "Add Cloudflare static asset routing contract"
```

## Task 1.2: Add the explicit frontend build handoff into `cloudflare/public`

**Purpose:**
Leave behind one repeatable command that refreshes the Cloudflare-served app shell from `frontend/dist/`.

**Files:**
- Create: `cloudflare/scripts/sync_frontend_dist.sh`
- Modify: none unless the script needs a narrow helper reference in docs or config
- Verify: `frontend/dist/`, `cloudflare/public/`

**Supports:**
- Acceptance Gate: `Local Cloudflare App Boundary And Asset Handoff Are Explicit`
- Supporting Verification: Focused frontend build verification for the asset handoff path

- [ ] **Step 1: Write the handoff script**

Create `cloudflare/scripts/sync_frontend_dist.sh` with behavior equivalent to:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
src="$repo_root/frontend/dist"
dest="$repo_root/cloudflare/public"

test -f "$src/index.html"
mkdir -p "$dest"
rsync -a --delete "$src"/ "$dest"/
```

The script should fail clearly if `frontend/dist/index.html` does not exist yet.

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && pnpm build`

Expected: PASS and `frontend/dist/index.html` exists.

- [ ] **Step 3: Run the asset handoff**

Run: `cd cloudflare && ./scripts/sync_frontend_dist.sh`

Expected: PASS and `cloudflare/public/index.html` plus hashed asset files exist.

- [ ] **Step 4: Verify the output explicitly**

Run:

```bash
test -f cloudflare/public/index.html
find cloudflare/public -maxdepth 2 -type f | sort | sed -n '1,40p'
```

Expected: PASS and the built frontend asset tree is now present inside `cloudflare/`.

- [ ] **Step 5: Commit**

```bash
git add cloudflare/scripts/sync_frontend_dist.sh
git commit -m "Add frontend asset handoff into cloudflare public"
```

## Task 1.3: Make the real UI’s fixture mode build-compatible

**Purpose:**
Keep the accepted deterministic smoke path inside the real app UI, but make it work from the built Cloudflare-served app instead of only from the Vite dev server.

**Files:**
- Modify: `frontend/src/hooks/useTranscript.ts`
- Modify: `frontend/src/hooks/useTranscript.test.tsx`
- Move/Create: `frontend/public/smoke-fixtures/while-speaking-two-todos/audio.pcm`

**Supports:**
- Acceptance Gate: `Local Cloudflare Same-Origin App Works Through The Real UI`
- Supporting Verification: Frontend smoke-fixture tests and frontend build

- [ ] **Step 1: Write the failing frontend tests**

Add or update focused tests so they pin:

```tsx
it("resolves the smoke fixture path from ?fixture=while-speaking-two-todos", () => {
  expect(resolveSmokeFixtureAudioPath("?fixture=while-speaking-two-todos")).toBe(
    "/smoke-fixtures/while-speaking-two-todos/audio.pcm"
  );
});

it("keeps the /ws websocket shape in fixture mode", async () => {
  // existing hook assertion should stay unchanged
});
```

The test should prove the fixture path is no longer tied to a Vite-only dev gate.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && pnpm test:run src/hooks/useTranscript.test.tsx`

Expected: FAIL because the current hook still treats fixture mode as dev-only and still points at the old dev-only asset path.

- [ ] **Step 3: Write the minimal implementation**

Update `frontend/src/hooks/useTranscript.ts` so that:

- the websocket target stays `ws(s)://<current-host>/ws`
- fixture mode is resolved from the URL query without an `import.meta.env.DEV` guard
- the fixture asset path is renamed to a built-app-safe path such as `/smoke-fixtures/while-speaking-two-todos/audio.pcm`

Move the existing fixture file from:

- `frontend/public/dev-fixtures/while-speaking-two-todos/audio.pcm`

to:

- `frontend/public/smoke-fixtures/while-speaking-two-todos/audio.pcm`

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd frontend && pnpm test:run src/hooks/useTranscript.test.tsx
cd frontend && pnpm build
find dist/smoke-fixtures -maxdepth 2 -type f | sort
```

Expected:

- hook tests PASS
- frontend build PASS
- the built asset tree contains `dist/smoke-fixtures/while-speaking-two-todos/audio.pcm`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useTranscript.ts frontend/src/hooks/useTranscript.test.tsx frontend/public/smoke-fixtures/while-speaking-two-todos/audio.pcm
git commit -m "Make browser smoke fixtures available from built app"
```

## Task 1.4: Upgrade the existing browser smoke script for the Cloudflare-served app

**Purpose:**
Reuse the existing repo smoke entrypoint instead of inventing a second browser smoke flow, and make it prove the real app UI on the Cloudflare-served origin.

**Files:**
- Modify: `scripts/browser_ui_smoke.sh`
- Read for assertions: `backend/tests/fixtures/while-speaking-two-todos/result.json`
- Verify against: `cloudflare/public/`, local `pywrangler dev`

**Supports:**
- Acceptance Gate: `Local Cloudflare Same-Origin App Works Through The Real UI`
- Acceptance Gate: `Local Cloudflare App Boundary And Asset Handoff Are Explicit`
- Supporting Verification: Repo-owned browser smoke script

- [ ] **Step 1: Expand the smoke script behavior**

Update `scripts/browser_ui_smoke.sh` so it:

- accepts `<base-url>` and `<fixture-name>` arguments
- opens `"$base_url/?fixture=$fixture_name"`
- uses `agent-browser` to click `Start Session` and `Finish Session`
- waits for todo text and final transcript from `backend/tests/fixtures/while-speaking-two-todos/result.json`
- exits non-zero on any missing state transition or assertion

Prefer reading expectations from the fixture `result.json` instead of hard-coding transcript/todo text in the script.

- [ ] **Step 2: Static-check the script**

Run: `bash -n scripts/browser_ui_smoke.sh`

Expected: PASS.

- [ ] **Step 3: Run the upgraded smoke against the Cloudflare-served app**

In terminal A:

```bash
cd frontend && pnpm build
cd ../cloudflare && ./scripts/sync_frontend_dist.sh
cd cloudflare && set -a && source ../backend/.env && set +a && uv run pywrangler dev --port 8788
```

In terminal B:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

Expected:

- the script exits `0`
- it prints a success marker after observing the real UI state transitions on the Cloudflare-served origin
- no Vite dev server is needed for the app shell

- [ ] **Step 4: Run websocket non-regression checks after the browser smoke**

Run:

```bash
cd cloudflare && uv run pytest tests/test_ws_smoke.py tests/test_entry.py -v
cd cloudflare && uv run python scripts/ws_smoke.py \
  --base-url ws://127.0.0.1:8788/ws \
  --fixture-path ../backend/tests/fixtures/while-speaking-two-todos/audio.pcm \
  --mode todo-stop \
  --session-id smoke-todo-stop \
  --chunk-bytes 3200 \
  --chunk-delay-ms 100 \
  --expect-started \
  --expect-transcript-min 1 \
  --expect-todos-min 1 \
  --expect-terminal-type stopped
```

Expected: PASS, proving the same-origin browser boundary did not regress the direct `/ws` path.

- [ ] **Step 5: Commit**

```bash
git add scripts/browser_ui_smoke.sh
git commit -m "Upgrade browser smoke for cloudflare served app"
```

REQUIRED HANDOFF: `superpowers:executing-plans`

OPTIONAL HANDOFF: `superpowers:subagent-driven-development`
