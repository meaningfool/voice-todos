# Item 12 Test Surface Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-16-item12-test-surface-cleanup-design.md`

**Goal:** Refactor the permanent automated test surface so it preserves the current product behavior proof while using behavior-based naming, ownership-correct placement, and explicit replacement or removal of stale transition coverage.

**Architecture:** Treat Item 12 as one non-phased refactor item with parallel workstreams, not a rollout sequence. Keep backend-owned proof in `backend/tests/`, move shared benchmark live validations into `tests/live/`, remove obsolete test assets instead of ceremonial moves, and finish by adding one repo-owned hygiene validator that locks the new naming and placement contract.

**Tech Stack:** Python 3.11+ backend test suite, pytest, Vitest, shell-based live validation scripts under `tests/live/`, ripgrep-based repo hygiene checks, markdown docs updates

---

## Process Rule

This plan follows:

- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
- `docs/superpowers/specs/2026-04-16-item12-test-surface-cleanup-design.md`

## Non-Phased Refactor Rule

Item 12 is an intentional exception to the phased default:

- there is no intended product behavioral delta
- workstreams may proceed in parallel once the baseline acceptance commands are
  green
- completion is judged only by the item-level acceptance contract from the spec

Do not invent phase gates for this item.

## Hard Guardrails

- Do not intentionally change `/ws`, extraction, replay, benchmark execution,
  or frontend UI behavior.
- Do not delete a test until its behavior is either:
  - proved elsewhere by equal-or-better coverage, or
  - explicitly obsolete under the Item 12 spec
- Keep the repo hygiene check scoped to the maintained automated test surface:
  - `backend/tests/`
  - frontend test files
  - `tests/live/`
- Do not churn historical specs and plans just to erase old item-number text.
  The hygiene validator should ignore historical docs by design.

## Preparation

Run the current acceptance baseline before touching files:

```bash
(cd backend && uv run pytest -q)
(cd frontend && pnpm test:run)
```

Expected:

- backend suite is green before the refactor starts
- frontend suite is green before the refactor starts

Record the baseline output in the implementation notes or PR description so the
cleanup can prove behavior preservation at the end.

## File Map

| File | Responsibility |
|------|----------------|
| `backend/app/live_eval_env.py` | Shared skip-reason helpers and live benchmark opt-in flag handling |
| `backend/tests/test_live_eval_env.py` | Coverage for live benchmark opt-in and credential skip logic |
| `docs/references/2026-04-13-credential-storage-and-logfire-access.md` | Operator-facing reference for benchmark live-validation flags |
| `tests/live/benchmarks/benchmark_live_validation_lib.py` | Shared helper utilities for benchmark live validation scripts |
| `tests/live/benchmarks/validate_benchmark_run_report_smoke.py` | Shared live smoke validation for benchmark run plus report behavior |
| `tests/live/benchmarks/validate_hosted_dataset_locking.py` | Live validator for first-run benchmark locking |
| `tests/live/benchmarks/validate_stale_benchmark_detection.py` | Live validator for stale benchmark stop behavior |
| `tests/live/benchmarks/validate_stale_benchmark_actions.py` | Live validator for `--allow-stale` and `--rebase` behavior |
| `backend/tests/test_benchmark_cli.py` | Behavior-named benchmark CLI proof |
| `backend/tests/test_benchmark_definitions.py` | Behavior-named benchmark definition proof |
| `backend/tests/test_benchmark_report.py` | Behavior-named benchmark report proof |
| `backend/tests/test_benchmark_logfire_query.py` | Behavior-named Logfire benchmark-query proof |
| `backend/tests/test_benchmark_extraction_runner.py` | Behavior-named extraction benchmark runner proof |
| `backend/tests/test_benchmark_replay_runner.py` | Behavior-named replay benchmark runner proof |
| `backend/tests/test_extraction_dataset_loader.py` | Durable extraction dataset contract proof |
| `backend/tests/test_incremental_dataset_loader.py` | Durable replay dataset contract proof |
| `backend/tests/test_hosted_dataset_locking.py` | Backend-owned first-run locking proof with behavior-named temp benchmark IDs |
| `backend/tests/test_stale_benchmark_detection.py` | Backend-owned stale-stop proof with behavior-named temp benchmark IDs |
| `backend/tests/test_stale_benchmark_actions.py` | Backend-owned `--allow-stale` and `--rebase` proof with behavior-named temp benchmark IDs |
| `frontend/src/App.test.tsx` | App-level state-to-skeleton mapping proof |
| `frontend/src/components/TodoSkeleton.test.tsx` | Component-level skeleton rendering and compact-mode proof |
| `backend/tests/test_extract.py` | Extraction-layer proof; should not duplicate prompt-registry negative-path coverage without a distinct boundary |
| `backend/tests/test_prompt_registry.py` | Natural boundary for unsupported prompt-version behavior |
| `tests/live/hygiene/validate_test_surface_layout.py` | Repo-owned hygiene validator for naming and placement acceptance |
| `scripts/test_audio_pipeline.sh` | Obsolete script-owned test asset to remove unless a stronger current contract appears |
| `docs/handoff-interim-text-and-testing.md` | Active operator-facing note that currently refers to the obsolete audio-pipeline script |
| `learnings.md` | Active repo note that should reflect the retired script asset if the file path is removed |

## Acceptance Coverage Decisions

- `update` the live benchmark opt-in flag to a behavior-named identifier: `BENCHMARK_ENABLE_LIVE_SMOKE`.
- `replace` backend-owned live smoke and live report pytest files with one shared benchmark live validator under `tests/live/benchmarks/`.
- `replace` item-numbered benchmark pytest files with behavior-named backend-owned suites.
- `remove` `backend/tests/test_item7_dataset_migration.py` after any still-relevant dataset contract assertions live in the dataset loader tests.
- `update` hosted-dataset locking and stale-action suites to use behavior-named temp benchmark IDs instead of `phase1_lock`, `phase2_stale`, and `phase3_rebase`.
- `remove` `scripts/test_audio_pipeline.sh` unless a current durable contract forces a replacement. The spec already points toward removal.
- `update` frontend skeleton tests so app-level and component-level suites prove distinct boundaries.
- `remove` `frontend/src/index.css.test.ts` unless implementation discovers a real long-term visual contract worth replacing it with.
- `remove` the duplicate unsupported-prompt negative-path assertion from `backend/tests/test_extract.py` unless implementation can justify it as a distinct propagation contract.
- `add` one repo-owned hygiene validator under `tests/live/hygiene/` and use it as the final naming and placement acceptance proof.

## Parallelization Notes

After Task 1 lands, these workstreams can run in parallel:

- `Workstream A`: Tasks 2 and 5
  - shared benchmark live validators and live-validator naming cleanup
- `Workstream B`: Tasks 3 and 4
  - backend benchmark pytest surface renames and transition-test replacement
- `Workstream C`: Tasks 6 and 7
  - obsolete asset removal plus non-benchmark duplicate cleanup

Task 8 is the final convergence task and must run last.

## Task 1: Replace Rollout-Specific Live Benchmark Opt-In Naming

**Files:**
- Modify: `backend/app/live_eval_env.py`
- Modify: `backend/tests/test_live_eval_env.py`
- Modify: `tests/live/benchmarks/validate_hosted_dataset_locking.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_detection.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_actions.py`
- Modify: `docs/references/2026-04-13-credential-storage-and-logfire-access.md`

- [ ] **Step 1: Add the failing coverage for a generic benchmark live-smoke flag**

Update `backend/tests/test_live_eval_env.py` so the durable contract is:

- `BENCHMARK_ENABLE_LIVE_SMOKE=1` enables tracked live benchmark runs
- skip reasons mention `BENCHMARK_ENABLE_LIVE_SMOKE=1`
- no new test name or expectation depends on `ITEM7_ENABLE_LIVE_SMOKE`

- [ ] **Step 2: Run the targeted test to verify the old flag name is still wired**

Run:

```bash
(cd backend && uv run pytest tests/test_live_eval_env.py -q)
```

Expected:

- FAIL because `backend/app/live_eval_env.py` still reads `ITEM7_ENABLE_LIVE_SMOKE`

- [ ] **Step 3: Update the shared helper, live validators, and operator reference**

Implement the minimal code change:

- `backend/app/live_eval_env.py` reads `BENCHMARK_ENABLE_LIVE_SMOKE`
- all benchmark live validators use the new flag
- the operator-facing credential reference documents the new flag name

Do not update historical Item 7 specs or plans just to remove the old flag
string.

- [ ] **Step 4: Run the targeted verification**

Run:

```bash
(cd backend && uv run pytest tests/test_live_eval_env.py -q)
if rg -n "ITEM7_ENABLE_LIVE_SMOKE" backend/app backend/tests tests/live docs/references; then
  echo "old item-numbered live-smoke flag still present" >&2
  exit 1
fi
```

Expected:

- `tests/test_live_eval_env.py` passes
- `rg` prints no matches in the maintained code and active operator docs

- [ ] **Step 5: Commit**

```bash
git add backend/app/live_eval_env.py \
  backend/tests/test_live_eval_env.py \
  tests/live/benchmarks/validate_hosted_dataset_locking.py \
  tests/live/benchmarks/validate_stale_benchmark_detection.py \
  tests/live/benchmarks/validate_stale_benchmark_actions.py \
  docs/references/2026-04-13-credential-storage-and-logfire-access.md
git commit -m "test: rename benchmark live smoke flag"
```

## Task 2: Replace Backend Live Smoke And Report Tests With Shared Live Validators

**Files:**
- Create: `tests/live/benchmarks/benchmark_live_validation_lib.py`
- Create: `tests/live/benchmarks/validate_benchmark_run_report_smoke.py`
- Modify: `tests/live/benchmarks/validate_hosted_dataset_locking.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_detection.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_actions.py`
- Delete: `tests/live/benchmarks/benchmark_locking_live_validation_lib.py`
- Delete: `backend/tests/test_item7_benchmark_smoke_integration.py`
- Delete: `backend/tests/test_item7_logfire_report_integration.py`

- [ ] **Step 1: Generalize the shared benchmark live-validation helper**

Create `tests/live/benchmarks/benchmark_live_validation_lib.py` from the
existing locking helper so it can support:

- temp benchmark creation
- benchmark run command execution
- benchmark report command execution
- lock payload loading
- available benchmark entry selection

Then update the three existing live validators to import from the generic
helper name.

- [ ] **Step 2: Add the shared run-plus-report smoke validator**

Create `tests/live/benchmarks/validate_benchmark_run_report_smoke.py` with the
same `PASS` / `WARN` / `FAIL` contract as the existing benchmark live
validators. It should:

- reuse the generic helper library
- run `benchmark run`
- run `benchmark report --json`
- fail if run/report do not complete or if report output lacks the benchmark ID
  and entry state payload

- [ ] **Step 3: Remove the backend-owned live smoke/report pytest files**

Delete:

- `backend/tests/test_item7_benchmark_smoke_integration.py`
- `backend/tests/test_item7_logfire_report_integration.py`

The live behavior now belongs to the shared live harness, not `backend/tests/`.

- [ ] **Step 4: Run the shared live-validation scripts**

Run:

```bash
(cd backend && uv run python ../tests/live/benchmarks/validate_hosted_dataset_locking.py)
(cd backend && uv run python ../tests/live/benchmarks/validate_stale_benchmark_detection.py)
(cd backend && uv run python ../tests/live/benchmarks/validate_stale_benchmark_actions.py)
(cd backend && uv run python ../tests/live/benchmarks/validate_benchmark_run_report_smoke.py)
```

Expected:

- each script exits `0`
- each script prints `PASS:` when prereqs are present or `WARN:` when prereqs
  are intentionally missing
- none of the scripts crash with import or command errors

- [ ] **Step 5: Verify the deleted backend live tests are no longer part of collection**

Run:

```bash
test ! -e backend/tests/test_item7_benchmark_smoke_integration.py
test ! -e backend/tests/test_item7_logfire_report_integration.py
if (cd backend && uv run pytest --collect-only -q | rg "item7_benchmark_smoke_integration|item7_logfire_report_integration"); then
  echo "deleted backend live smoke/report tests are still collected" >&2
  exit 1
fi
```

Expected:

- both `test ! -e` checks pass
- the `rg` command returns no matches from collected tests

- [ ] **Step 6: Commit**

```bash
git add tests/live/benchmarks
git rm backend/tests/test_item7_benchmark_smoke_integration.py \
  backend/tests/test_item7_logfire_report_integration.py \
  tests/live/benchmarks/benchmark_locking_live_validation_lib.py
git commit -m "test: move benchmark live smoke validation to tests live"
```

## Task 3: Rename Benchmark CLI, Definition, Report, And Query Suites To Behavior Names

**Files:**
- Create: `backend/tests/test_benchmark_cli.py`
- Create: `backend/tests/test_benchmark_definitions.py`
- Create: `backend/tests/test_benchmark_report.py`
- Create: `backend/tests/test_benchmark_logfire_query.py`
- Delete: `backend/tests/test_item7_benchmark_cli.py`
- Delete: `backend/tests/test_item7_benchmark_definitions.py`
- Delete: `backend/tests/test_item7_benchmark_report.py`
- Delete: `backend/tests/test_item7_logfire_query.py`

- [ ] **Step 1: Move the item-numbered suites to behavior-named paths**

Carry forward only assertions that still prove the current benchmark contract:

- benchmark CLI behavior
- benchmark definition parsing
- benchmark report rendering and missing-entry behavior
- Logfire benchmark-row normalization

Rewrite file headers and test names so no permanent test name contains
`item7`, `phase`, or rollout-language residue.

- [ ] **Step 2: Run the targeted backend tests**

Run:

```bash
(cd backend && uv run pytest \
  tests/test_benchmark_cli.py \
  tests/test_benchmark_definitions.py \
  tests/test_benchmark_report.py \
  tests/test_benchmark_logfire_query.py -q)
```

Expected: PASS

- [ ] **Step 3: Verify the old item-numbered files are gone**

Run:

```bash
test ! -e backend/tests/test_item7_benchmark_cli.py
test ! -e backend/tests/test_item7_benchmark_definitions.py
test ! -e backend/tests/test_item7_benchmark_report.py
test ! -e backend/tests/test_item7_logfire_query.py
```

Expected: all four checks pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_benchmark_cli.py \
  backend/tests/test_benchmark_definitions.py \
  backend/tests/test_benchmark_report.py \
  backend/tests/test_benchmark_logfire_query.py
git rm backend/tests/test_item7_benchmark_cli.py \
  backend/tests/test_item7_benchmark_definitions.py \
  backend/tests/test_item7_benchmark_report.py \
  backend/tests/test_item7_logfire_query.py
git commit -m "test: rename benchmark contract suites by behavior"
```

## Task 4: Replace Transition-Only Dataset And Runner Suites With Durable Benchmark Proof

**Files:**
- Create: `backend/tests/test_benchmark_extraction_runner.py`
- Create: `backend/tests/test_benchmark_replay_runner.py`
- Modify: `backend/tests/test_extraction_dataset_loader.py`
- Modify: `backend/tests/test_incremental_dataset_loader.py`
- Delete: `backend/tests/test_item7_extraction_runner.py`
- Delete: `backend/tests/test_item7_replay_runner.py`
- Delete: `backend/tests/test_item7_dataset_migration.py`

- [ ] **Step 1: Move any still-relevant dataset contract checks into the loader suites**

Keep only durable dataset assertions such as:

- stable row IDs
- normalized case structure
- replay dataset loader shape

Do not preserve raw "legacy parity" assertions whose only purpose is to prove a
migration step that no longer exists.

- [ ] **Step 2: Move the extraction benchmark runner proof into a behavior-named suite**

Carry forward only assertions that still prove the current contract, such as:

- entry resolution
- runner context isolation
- benchmark-owned invocation behavior

- [ ] **Step 3: Move the replay benchmark runner proof into a behavior-named suite**

Keep only assertions that still prove:

- replay entry suite selection
- skipping already-populated entries by default
- full rerun behavior for `--all`

- [ ] **Step 4: Delete the transition-only migration suite**

Delete `backend/tests/test_item7_dataset_migration.py` only after the durable
dataset contract is clearly covered by `test_extraction_dataset_loader.py` and
`test_incremental_dataset_loader.py`.

- [ ] **Step 5: Run the targeted backend tests**

Run:

```bash
(cd backend && uv run pytest \
  tests/test_benchmark_extraction_runner.py \
  tests/test_benchmark_replay_runner.py \
  tests/test_extraction_dataset_loader.py \
  tests/test_incremental_dataset_loader.py -q)
```

Expected: PASS

- [ ] **Step 6: Verify the item-numbered runner and migration files are gone**

Run:

```bash
test ! -e backend/tests/test_item7_extraction_runner.py
test ! -e backend/tests/test_item7_replay_runner.py
test ! -e backend/tests/test_item7_dataset_migration.py
```

Expected: all three checks pass

- [ ] **Step 7: Commit**

```bash
git add backend/tests/test_benchmark_extraction_runner.py \
  backend/tests/test_benchmark_replay_runner.py \
  backend/tests/test_extraction_dataset_loader.py \
  backend/tests/test_incremental_dataset_loader.py
git rm backend/tests/test_item7_extraction_runner.py \
  backend/tests/test_item7_replay_runner.py \
  backend/tests/test_item7_dataset_migration.py
git commit -m "test: replace transition-only benchmark runner suites"
```

## Task 5: Rename Locking And Staleness Fixture Identities Away From Phase Labels

**Files:**
- Modify: `backend/tests/test_hosted_dataset_locking.py`
- Modify: `backend/tests/test_stale_benchmark_detection.py`
- Modify: `backend/tests/test_stale_benchmark_actions.py`
- Modify: `tests/live/benchmarks/validate_hosted_dataset_locking.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_detection.py`
- Modify: `tests/live/benchmarks/validate_stale_benchmark_actions.py`
- Modify: `tests/live/benchmarks/benchmark_live_validation_lib.py`

- [ ] **Step 1: Replace phase-labeled temp benchmark IDs and filenames with behavior names**

Rename temporary IDs and fixture filenames to behavior-oriented names such as:

- `first_run_locking`
- `stale_detection`
- `stale_actions`

Do not leave `phase1_lock`, `phase2_stale`, or `phase3_rebase` anywhere in the
maintained automated test surface.

- [ ] **Step 2: Remove phase wording from live-validator output**

Update live validator output strings so they talk about:

- first-run locking
- stale detection
- stale actions

not "phase 1", "phase 2", or "phase 3".

- [ ] **Step 3: Run the targeted backend tests**

Run:

```bash
(cd backend && uv run pytest \
  tests/test_hosted_dataset_locking.py \
  tests/test_stale_benchmark_detection.py \
  tests/test_stale_benchmark_actions.py \
  tests/test_benchmark_staleness_report.py -q)
```

Expected: PASS

- [ ] **Step 4: Run the shared live validators again**

Run:

```bash
(cd backend && uv run python ../tests/live/benchmarks/validate_hosted_dataset_locking.py)
(cd backend && uv run python ../tests/live/benchmarks/validate_stale_benchmark_detection.py)
(cd backend && uv run python ../tests/live/benchmarks/validate_stale_benchmark_actions.py)
```

Expected: each script exits `0` with either `PASS:` or `WARN:`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_hosted_dataset_locking.py \
  backend/tests/test_stale_benchmark_detection.py \
  backend/tests/test_stale_benchmark_actions.py \
  tests/live/benchmarks/validate_hosted_dataset_locking.py \
  tests/live/benchmarks/validate_stale_benchmark_detection.py \
  tests/live/benchmarks/validate_stale_benchmark_actions.py \
  tests/live/benchmarks/benchmark_live_validation_lib.py
git commit -m "test: remove phase labels from benchmark locking fixtures"
```

## Task 6: Remove The Obsolete Audio-Pipeline Test Asset

**Files:**
- Delete: `scripts/test_audio_pipeline.sh`
- Modify: `docs/handoff-interim-text-and-testing.md`
- Modify: `learnings.md`

- [ ] **Step 1: Remove the obsolete script-owned test asset**

Delete `scripts/test_audio_pipeline.sh`.

Do not move it into `tests/live/` unless implementation discovers a real
present-day contract that still needs durable automated proof. The Item 12 spec
already points toward removal.

- [ ] **Step 2: Update the active notes that still point at the removed file**

Update:

- `docs/handoff-interim-text-and-testing.md`
- `learnings.md`

so they describe the script as a retired historical asset rather than an active
test command.

Do not churn historical Item 2 specs or plans.

- [ ] **Step 3: Verify the script is gone and active notes no longer present it as runnable**

Run:

```bash
test ! -e scripts/test_audio_pipeline.sh
if rg -n "test_audio_pipeline\\.sh" docs/handoff-interim-text-and-testing.md learnings.md scripts; then
  echo "active documentation still points at the removed audio pipeline script" >&2
  exit 1
fi
```

Expected:

- the script path does not exist
- `rg` returns no active-runnable references in the checked files

- [ ] **Step 4: Commit**

```bash
git add docs/handoff-interim-text-and-testing.md learnings.md
git rm scripts/test_audio_pipeline.sh
git commit -m "test: retire obsolete audio pipeline validation asset"
```

## Task 7: Trim Non-Benchmark Duplicate And Brittle Coverage

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/TodoSkeleton.test.tsx`
- Delete: `frontend/src/index.css.test.ts`
- Modify: `backend/tests/test_extract.py`
- Modify: `backend/tests/test_prompt_registry.py` (only if needed to keep the natural boundary explicit)

- [ ] **Step 1: Separate app-level skeleton mapping from component-level rendering proof**

Keep:

- `App.test.tsx` cases that prove state-to-skeleton decisions
- `TodoSkeleton.test.tsx` cases that prove component-local count and compact
  behavior

Remove mirrored count coverage that does not add a distinct boundary.

- [ ] **Step 2: Remove the brittle CSS reference-alignment test**

Delete `frontend/src/index.css.test.ts` unless implementation can justify a
stable visual contract that should survive as behavior-level proof. The default
path for Item 12 is removal.

- [ ] **Step 3: Collapse the duplicate unsupported-prompt negative path**

Keep the natural boundary in `backend/tests/test_prompt_registry.py`.

Remove the duplicate unsupported-version negative-path assertion from
`backend/tests/test_extract.py` unless it is rewritten to prove a distinct
propagation contract.

- [ ] **Step 4: Run the targeted frontend and backend tests**

Run:

```bash
(cd frontend && pnpm exec vitest run \
  src/App.test.tsx \
  src/components/TodoSkeleton.test.tsx)
(cd backend && uv run pytest tests/test_extract.py tests/test_prompt_registry.py -q)
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.test.tsx \
  frontend/src/components/TodoSkeleton.test.tsx \
  backend/tests/test_extract.py \
  backend/tests/test_prompt_registry.py
git rm frontend/src/index.css.test.ts
git commit -m "test: trim duplicate non-benchmark coverage"
```

## Task 8: Add The Repo-Owned Hygiene Validator And Run Final Acceptance

**Files:**
- Create: `tests/live/hygiene/validate_test_surface_layout.py`

- [ ] **Step 1: Add the hygiene validator**

Create `tests/live/hygiene/validate_test_surface_layout.py` so it checks only
the maintained automated test surface:

- file basenames under `backend/tests/`
- file basenames under `tests/live/`
- test file basenames under the frontend suite
- Python test function names in backend and live test files
- `it(...)` / `test(...)` names in frontend test files
- presence of active automated test-suite assets under `scripts/`

The validator should fail on:

- item-number labels
- phase-number labels
- rollout-labeled permanent test names
- active automated test-suite assets that still live in `scripts/`

It should intentionally ignore:

- `docs/`
- historical specs and plans
- other non-test repo content

- [ ] **Step 2: Run the hygiene validator**

Run:

```bash
python3 tests/live/hygiene/validate_test_surface_layout.py
```

Expected:

- exit code `0`
- output clearly says `PASS` and lists the scanned surface

- [ ] **Step 3: Run the full item acceptance commands**

Run:

```bash
(cd backend && uv run pytest -q)
(cd frontend && pnpm test:run)
python3 tests/live/hygiene/validate_test_surface_layout.py
git diff --check
```

Expected:

- backend suite passes
- frontend suite passes
- hygiene validator passes
- `git diff --check` reports no whitespace or merge-marker issues

- [ ] **Step 4: Commit**

```bash
git add tests/live/hygiene/validate_test_surface_layout.py
git commit -m "test: lock test surface naming and placement contract"
```

## Completion Gate

Item 12 is complete only when all of these are true:

- backend acceptance still passes
- frontend acceptance still passes
- the hygiene validator passes against the maintained automated test surface
- no permanent automated test file or final test name in that maintained
  surface uses item-number, phase-number, or rollout labeling
- shared benchmark live validations live under `tests/live/`
- no active automated test-suite asset remains under `scripts/`

## References

- `docs/superpowers/specs/2026-04-16-item12-test-surface-cleanup-design.md`
- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
- `backend/app/live_eval_env.py`
- `backend/tests/`
- `tests/live/benchmarks/`
- `frontend/src/`
