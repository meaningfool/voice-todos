# Item 12 Design: Test Surface Cleanup And Ownership Alignment

Scope: refactor the automated test surface so permanent tests are named by
behavior, placed by ownership and harness, and kept minimal without changing
product behavior.

## Why this exists

The current test surface still carries rollout history in places where it
should instead describe the current behavioral contract.

The main problems are:

- benchmark and eval tests still use temporary item-number and phase-number
  naming such as `backend/tests/test_item7_*.py`
- some benchmark live validations sit in `backend/tests/` even though they
  prove shared CLI plus Logfire behavior rather than backend-only behavior
- `scripts/test_audio_pipeline.sh` behaves like a test asset but lives under
  `scripts/`, and the Item 2 notes now say the hypothesis it protected is
  obsolete
- some non-benchmark suites duplicate proof or freeze temporary design
  references rather than proving durable product behavior

Item 12 exists to make the repo's permanent test surface readable and durable:

- names should describe current behavior
- test placement should reveal ownership
- duplicated proof should be collapsed
- stale transition tests should be removed or replaced deliberately

## Refactor Classification

Item 12 is a structural refactor, not a product-behavior item.

Important exception to the phased-spec default:

- this item has no intended product behavioral delta
- its cleanup workstreams may proceed in parallel
- completion is judged at the item level through one shared acceptance
  contract, not phase gates

This exception is intentional. Forcing fake phases onto a naming and placement
cleanup would make the spec less clear.

## Goals

- keep the same intended backend and frontend behavior proved after the refactor
- rename permanent tests away from item numbers, phase numbers, and rollout
  labels
- place tests in the subsystem or shared harness that naturally owns the
  behavior they prove
- remove or replace stale transition tests that only prove migration,
  equivalence, or temporary rollout scaffolding
- reduce obvious duplicated proof while keeping the strongest natural-harness
  coverage

## Non-goals

- changing the product behavior of `/ws`, extraction, replay, benchmarking, or
  the frontend UI
- redesigning benchmark orchestration, prompt handling, or frontend visuals
- creating a brand-new repo-wide testing framework
- moving tests just because they are called "acceptance" tests
- deleting tests as an end in itself

The target is a cleaner permanent proof surface, not a smaller test count at
any cost.

## Current State Summary

### Benchmark And Eval Naming Debt

The benchmark area still contains transitional item-named files such as:

- `backend/tests/test_item7_benchmark_cli.py`
- `backend/tests/test_item7_benchmark_definitions.py`
- `backend/tests/test_item7_benchmark_report.py`
- `backend/tests/test_item7_dataset_migration.py`
- `backend/tests/test_item7_extraction_runner.py`
- `backend/tests/test_item7_replay_runner.py`
- `backend/tests/test_item7_logfire_query.py`
- `backend/tests/test_item7_benchmark_smoke_integration.py`
- `backend/tests/test_item7_logfire_report_integration.py`

Some of those files are not just misnamed. They still prove temporary
transition states such as:

- legacy dataset parity
- legacy registry equivalence
- shim or deprecation behavior

Those are not durable behavior areas by default.

### Benchmark Live Validation Placement Debt

The repo already has a shared live-validation tree:

- `tests/live/benchmarks/`

It already contains benchmark-focused live validators for:

- hosted dataset locking
- stale benchmark detection
- stale benchmark actions

That makes the remaining backend live smoke and live report tests inconsistent.
Tests that prove shared benchmark CLI plus Logfire behavior should live in the
shared live harness unless they are genuinely backend-only.

### Script-Owned Test Asset Debt

`scripts/test_audio_pipeline.sh` is described and used like a test-suite asset,
but the repo policy says non-`pytest` automated validations should live in a
test-owned tree such as `tests/live/`, not in `scripts/`.

The Item 2 notes also now say the flush-delay hypothesis behind that asset was
not the real bug and that the dedicated audio-pipeline test was not needed as a
permanent proof.

### Non-Benchmark Duplication And Brittle Proof

The non-benchmark surface has smaller but still real hygiene issues:

- `frontend/src/App.test.tsx` and `frontend/src/components/TodoSkeleton.test.tsx`
  both assert skeleton-count behavior
- `backend/tests/test_extract.py` and `backend/tests/test_prompt_registry.py`
  both assert the same unknown prompt-version error path
- `frontend/src/index.css.test.ts` freezes literal design-reference values
  rather than a clearly stated long-term product contract

These are not all equally severe, but they should be reviewed under one
cleanup item so the repo has a consistent standard.

## Design Decisions

### 1. Permanent Tests Must Be Organized By Stable Behavior Area

Permanent test names must describe:

- the behavior
- the component
- the subsystem

They must not describe:

- item numbers
- phase numbers
- rollout labels
- migration-step identities

Examples of good final naming directions:

- `test_benchmark_cli.py`
- `test_benchmark_definitions.py`
- `test_benchmark_report.py`
- `test_run_creates_benchmark_lock_on_first_use`
- `test_run_stops_when_locked_dataset_has_drifted`
- `test_rebase_rewrites_lock_and_reruns_entries`

The same rule applies inside test data and temporary benchmark fixtures used by
durable tests. Names such as `phase1_lock`, `phase2_stale`, and
`phase3_rebase` should be replaced with behavior-named identifiers.

### 2. Test Placement Must Follow Technical Ownership, Not Historical Accident

Placement rules for Item 12:

- backend-only behavior stays in `backend/tests/`
- frontend-only behavior stays in the frontend test suite
- shared benchmark live validations belong under `tests/live/benchmarks/`
- non-`pytest` automated test assets belong in test-owned locations, not under
  `scripts/`

This means:

- backend benchmark unit and integration tests should remain backend-owned when
  they are proving local Python behavior
- shared tracked-run, report, and Logfire live validations should live under
  `tests/live/benchmarks/`
- `scripts/test_audio_pipeline.sh` should either move into a test-owned live
  location or be removed if it no longer proves a current contract

### 3. Transitional Rollout Tests Are Cleanup Candidates, Not Protected Assets

A transitional test should remain permanent only if it still proves part of the
current intended contract.

Tests that are candidates for removal or replacement include tests whose only
proof is:

- migration parity with a legacy dataset shape
- equivalence with a legacy registry
- existence of a compatibility shim that is no longer part of the intended
  long-term surface

Item 12 should therefore treat files such as:

- `backend/tests/test_item7_dataset_migration.py`
- `backend/tests/test_item7_extraction_runner.py`
- parts of `backend/tests/test_item7_benchmark_definitions.py`
- parts of `backend/tests/test_item7_benchmark_smoke_integration.py`

as replace-or-remove decisions rather than automatic rename targets.

### 4. Duplicate Proof Should Collapse To The Strongest Natural Harness

Item 12 should not create a second acceptance copy of a behavior.

For each duplicated area, the cleanup decision should be:

- keep the strongest natural proof
- remove or trim the mirror proof
- only keep both when they prove genuinely different boundaries

Examples:

- if `App.test.tsx` proves state-to-skeleton mapping, the component suite does
  not need to mirror every count case
- if the component suite proves the primitive count rendering and compact-mode
  class behavior, the app suite only needs the state mapping cases that matter
- if one prompt-version failure test already proves the durable contract, a
  second identical negative-path assertion should be removed unless it proves a
  distinct propagation boundary

### 5. Obsolete Live Assets Should Be Removed, Not Ceremonially Moved

If a test asset no longer proves a current contract, moving it is the wrong
fix.

This rule especially applies to `scripts/test_audio_pipeline.sh`.

Item 12 must decide one of two things explicitly:

- `replace` it with a current live validation in a test-owned location because
  the behavior still needs a durable automated proof
- `remove` it because the repo's current contract no longer depends on that
  hypothesis

The notes already point strongly toward removal unless a current behavior owner
can justify a durable replacement.

### 6. Cleanup Decisions Must Be Explicit By Behavior Area

For each behavior area, the implementation plan must make one of these choices:

- `update`
- `replace`
- `add`
- `remove`

This item must not quietly delete coverage and call it cleanup.

## Parallel Workstreams

The implementation can proceed in parallel across these workstreams:

- `placement cleanup`
  - move or remove misplaced live and cross-system tests
- `benchmark suite cleanup`
  - replace item-number, phase-number, and transition-only benchmark tests
    with behavior-named durable coverage
- `general suite cleanup`
  - remove or trim stale and duplicated non-benchmark tests while keeping the
    strongest proof

These workstreams are intentionally parallelizable because they do not depend
on a product-behavior rollout sequence.

## Target Behavior Areas And Expected Cleanup Direction

### Shared Benchmark Live Validation

Behavior area:

- live proof that benchmark commands and Logfire-backed reporting work in the
  shared benchmark environment

Expected direction:

- `replace` backend-owned live smoke and report tests with shared live assets
  under `tests/live/benchmarks/`, or `remove` them if existing live validators
  already provide the smallest realistic proof

Current cleanup targets:

- `backend/tests/test_item7_benchmark_smoke_integration.py`
- `backend/tests/test_item7_logfire_report_integration.py`

### Benchmark Definition, CLI, Report, And Entry Resolution

Behavior areas:

- benchmark definition parsing
- benchmark CLI behavior
- benchmark reporting
- benchmark entry resolution for extraction and replay

Expected direction:

- `replace` item-numbered backend test files with behavior-named backend-owned
  tests
- `remove` legacy-parity assertions unless they still prove a current contract

Current cleanup targets:

- `backend/tests/test_item7_benchmark_cli.py`
- `backend/tests/test_item7_benchmark_definitions.py`
- `backend/tests/test_item7_benchmark_report.py`
- `backend/tests/test_item7_dataset_migration.py`
- `backend/tests/test_item7_extraction_runner.py`
- `backend/tests/test_item7_replay_runner.py`
- `backend/tests/test_item7_logfire_query.py`

### Hosted Dataset Locking And Staleness

Behavior areas:

- first-run locking
- stale detection
- stale actions
- benchmark report stale state

Expected direction:

- `keep` these backend-owned suites in `backend/tests/`
- `update` internal benchmark IDs, temporary filenames, and test naming so they
  are behavior-named rather than phase-named
- keep the existing shared live validators as the live proof for these
  behaviors

Current cleanup targets:

- `backend/tests/test_hosted_dataset_locking.py`
- `backend/tests/test_stale_benchmark_detection.py`
- `backend/tests/test_stale_benchmark_actions.py`
- `backend/tests/test_benchmark_staleness_report.py`

### Audio Pipeline Validation Asset

Behavior area:

- browser-to-backend audio byte-delivery validation

Expected direction:

- `remove` the current script if it no longer proves a current contract
- only `replace` it with a test-owned live asset if a durable present-day
  contract still requires it

Current cleanup target:

- `scripts/test_audio_pipeline.sh`

### Frontend Skeleton And View-State Coverage

Behavior area:

- app state decides when skeletons appear and how many appear
- skeleton component renders its own primitive count and compact-mode behavior

Expected direction:

- `update` app-level and component-level suites so each proves a distinct
  boundary instead of mirroring the same count matrix

Current cleanup targets:

- `frontend/src/App.test.tsx`
- `frontend/src/components/TodoSkeleton.test.tsx`

### Frontend Style And Reference Guards

Behavior area:

- durable visual contract, if any

Expected direction:

- `replace` brittle literal reference-alignment assertions with behavior-level
  proof, or `remove` them if there is no stable contract worth freezing

Current cleanup target:

- `frontend/src/index.css.test.ts`

### Prompt Version Failure Coverage

Behavior area:

- unsupported prompt versions fail at the intended boundary

Expected direction:

- keep one durable proof at the natural boundary, plus a second test only if it
  proves a distinct propagation contract

Current cleanup targets:

- `backend/tests/test_extract.py`
- `backend/tests/test_prompt_registry.py`

## Item-Level Acceptance Contract

Item 12 is complete only when all of the following are true:

1. The same intended backend and frontend behavior remains proved after the
   cleanup.
2. The permanent automated test surface is named by behavior and ownership, not
   by item numbers, phase numbers, or rollout labels.
3. Shared benchmark live validations live in test-owned shared locations such
   as `tests/live/benchmarks/`, not in `scripts/` or misclassified backend test
   files.
4. Tests removed during the cleanup are either replaced by equal-or-better
   proof or explicitly removed as obsolete.
5. A developer reading the repo layout can tell which tests are:
   - backend-owned
   - frontend-owned
   - shared live validations

## Acceptance Tests

Because this item is a structural refactor with no intended product-behavior
delta, acceptance is item-level rather than phased.

### 1. Backend Suite Acceptance

Command:

```bash
cd backend && uv run pytest -q
```

Proves:

- the backend behavior still works after test renames, moves, removals, and
  replacements

### 2. Frontend Suite Acceptance

Command:

```bash
cd frontend && pnpm test:run
```

Proves:

- the frontend behavior still works after the non-benchmark cleanup

### 3. Test Surface Naming Acceptance

Expected proof:

- a repo-level hygiene check confirms that no permanent test files or final
  test names under the maintained automated test surface are tied to item
  numbers, phase numbers, or rollout labels

Expected scope of the check:

- `backend/tests/`
- frontend automated test files
- `tests/live/`

This check should intentionally ignore specs, plans, and historical docs.

### 4. Test Surface Placement Acceptance

Expected proof:

- a repo-level hygiene check confirms that shared benchmark live validations
  live under `tests/live/benchmarks/`
- no active automated test-suite asset remains in `scripts/`

If a former script-owned validation is intentionally retained, it must be moved
into a test-owned tree and validated there.

## Supporting Verification

Useful supporting verification for the implementation plan:

- targeted backend suite runs for touched benchmark files during the rename and
  replacement work
- targeted frontend runs for touched component and app suites
- manual review of every `remove` decision to confirm the behavior is either
  obsolete or proved elsewhere
- running the shared live benchmark validators when environment prerequisites
  are available:
  - `tests/live/benchmarks/validate_hosted_dataset_locking.py`
  - `tests/live/benchmarks/validate_stale_benchmark_detection.py`
  - `tests/live/benchmarks/validate_stale_benchmark_actions.py`

These are valuable confidence checks, but the item's core acceptance contract
is the preserved behavior proof plus the cleaned-up permanent test surface.

## References

- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
- `docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md`
- `backend/tests/`
- `tests/live/benchmarks/`
- `scripts/test_audio_pipeline.sh`
- `frontend/src/App.test.tsx`
- `frontend/src/components/TodoSkeleton.test.tsx`
- `frontend/src/index.css.test.ts`
- `backend/tests/test_extract.py`
- `backend/tests/test_prompt_registry.py`
