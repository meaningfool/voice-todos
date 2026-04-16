# Item 11 Extraction And Replay Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-15-item11-todo-extraction-dataset-design.md`

**Goal:** Remove the outdated local dataset/bootstrap workflow, keep hosted datasets plus benchmark locks as the only benchmark data contract, then curate stronger extraction and replay datasets and run the existing benchmark definitions against them.

**Architecture:** Keep the current extraction evaluator, replay evaluator, benchmark definitions, and model matrix unchanged. First remove the repo-local dataset curation path so hosted datasets are the only source of truth and local locks are the only benchmark-owned dataset artifacts. Then curate the hosted extraction and replay datasets and run the existing benchmark definitions against them. On a benchmark's first run, the runner creates the lock automatically. On later runs after hosted dataset changes, `--rebase` refreshes that lock. Keep fixture-based dataset files only where they are needed for smoke and parser verification.

**Tech Stack:** JSON dataset assets, Pydantic Evals dataset loader, Logfire hosted datasets, benchmark CLI, pytest

**Reference:** `docs/references/2026-04-16-logfire-query-api-notes.md`

---

## File map

- Delete: `evals/datasets/extraction/todo_extraction_v1.json`
- Delete: `backend/evals/extraction_quality/todo_extraction_v1.json`
- Delete: `evals/datasets/replay/todo_extraction_replay_v1.json`
- Delete: `backend/evals/incremental_extraction_quality/todo_extraction_replay_v1.json`
- Delete: `scripts/bootstrap_logfire_hosted_datasets.py`
- Rename: `evals/benchmarks/extraction_llm_matrix_v1.yaml` -> `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Rename: `evals/benchmarks/replay_llm_matrix_v1.yaml` -> `evals/benchmarks/todo_replay_bench_v1.yaml`
- Modify or replace: `backend/tests/test_extraction_dataset_loader.py`
- Modify or replace: `backend/tests/test_incremental_dataset_loader.py`
- Delete or replace: `backend/tests/test_item7_dataset_migration.py`
- Delete or replace: `backend/tests/test_hosted_dataset_bootstrap.py`
- Modify if needed: `backend/tests/test_extraction_runner.py`
- Modify if needed: `backend/tests/test_incremental_extraction_runner.py`
- Reference: `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Reference: `evals/benchmarks/todo_replay_bench_v1.yaml`

## Phase 1: Hosted dataset refactor

### Task 1: Remove the repo-local dataset curation path

**Files:**
- Delete: `evals/datasets/extraction/todo_extraction_v1.json`
- Delete: `backend/evals/extraction_quality/todo_extraction_v1.json`
- Delete: `evals/datasets/replay/todo_extraction_replay_v1.json`
- Delete: `backend/evals/incremental_extraction_quality/todo_extraction_replay_v1.json`
- Delete: `scripts/bootstrap_logfire_hosted_datasets.py`
- Rename: `evals/benchmarks/extraction_llm_matrix_v1.yaml` -> `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Rename: `evals/benchmarks/replay_llm_matrix_v1.yaml` -> `evals/benchmarks/todo_replay_bench_v1.yaml`

- [ ] Remove the committed extraction and replay dataset JSONs that were only
  used as repo-local curation artifacts.
- [ ] Remove the bootstrap script that synced those local datasets into Logfire.
- [ ] Rename the existing benchmark definition files and benchmark IDs to:
  - `todo_extraction_bench_v1`
  - `todo_replay_bench_v1`
- [ ] Remove any runtime default-path dependency on the deleted dataset files.

### Task 2: Replace local-dataset tests with fixture-based verification

**Files:**
- Modify or replace: `backend/tests/test_extraction_dataset_loader.py`
- Modify or replace: `backend/tests/test_incremental_dataset_loader.py`
- Delete or replace: `backend/tests/test_item7_dataset_migration.py`
- Delete or replace: `backend/tests/test_hosted_dataset_bootstrap.py`
- Modify if needed: `backend/tests/test_extraction_runner.py`
- Modify if needed: `backend/tests/test_incremental_extraction_runner.py`

- [ ] Replace tests that assume committed local dataset files with tests that
  use explicit fixture datasets or lock-shaped fixture payloads.
- [ ] Remove migration/bootstrap assertions that only existed to keep repo-local
  dataset copies in sync.
- [ ] Keep parser and runner coverage that proves extraction and replay suites
  still accept explicit dataset fixtures.
- [ ] Run:
  `cd backend && uv run pytest tests/test_extraction_dataset_loader.py tests/test_incremental_dataset_loader.py tests/test_extraction_runner.py tests/test_incremental_extraction_runner.py tests/test_item7_benchmark_cli.py tests/test_item7_benchmark_smoke_integration.py -v`

### Task 3: Reprove the hosted dataset plus lock benchmark flow

**Files:**
- Reference: `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Reference: `evals/benchmarks/todo_replay_bench_v1.yaml`

- [ ] Confirm benchmark runs still resolve their dataset from `hosted_dataset`
  and the local benchmark lock, not from removed repo-local dataset files.
- [ ] Confirm benchmark list/show/run/report use the renamed benchmark IDs.
- [ ] Run the existing benchmark CLI and smoke coverage needed to prove nothing
  behaviorally broke.
- [ ] If live hosted dataset credentials are available, run at least one normal
  benchmark rebase/report flow end to end; otherwise call out that live proof is
  blocked by external credentials.

### Phase 1 acceptance gates

- [ ] `cd backend && uv run pytest tests/test_extraction_dataset_loader.py tests/test_incremental_dataset_loader.py tests/test_extraction_runner.py tests/test_incremental_extraction_runner.py tests/test_item7_benchmark_cli.py tests/test_item7_benchmark_smoke_integration.py -v`
- [ ] If credentials are available: `cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --rebase`
- [ ] If credentials are available: `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json`

Do not begin Phase 2 until these gates pass or are blocked only by missing
external credentials that have been explicitly called out.

## Phase 2: Extraction dataset

### Task 4: Curate the extraction dataset

**Files:**
- Hosted dataset only

- [ ] Replace the current hosted extraction dataset rows with the approved
  curated count-only case set.
- [ ] Keep the dataset size between 20 and 30 cases.
- [ ] Cover the agreed dimensions: actionability boundary, todo boundarying,
  ASR noise, dense structure, duplicates, corrections, cancellations, and mixed
  signal.
- [ ] Add metadata tags to each hosted row so the case mix is reviewable.
- [ ] Remove the `stop` case from the curated set.

### Task 5: Run the extraction benchmark definition against the curated dataset

**Files:**
- Reference: `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Reference: `evals/locks/todo_extraction_bench_v1.json`

- [ ] Treat `todo_extraction_bench_v1` as the existing benchmark definition ID,
  not as a lock file name.
- [ ] If this benchmark has not been run before and no local lock exists yet,
  create the first lock by running:
  `cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1`
- [ ] If the benchmark already has a local lock and the hosted dataset has
  changed, refresh that lock by running:
  `cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --rebase`
- [ ] Generate a report for the updated benchmark state.
- [ ] Run:
  `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json`
- [ ] Record the resulting batch ID and confirm the report reflects the updated
  benchmark run.

### Phase 2 acceptance gates

- [ ] If no extraction lock exists yet: `cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1`
- [ ] If an extraction lock already exists and the hosted dataset changed: `cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --rebase`
- [ ] `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json`

Do not begin Phase 3 until these gates pass or are blocked only by missing
external credentials that have been explicitly called out.

## Phase 3: Replay dataset

### Task 6: Curate the replay dataset

**Files:**
- Hosted dataset only

- [ ] Replace the current hosted replay rows with the approved curated replay
  case set from the spec.
- [ ] Keep the core vs stretch split visible in metadata tags or case comments
  as appropriate.
- [ ] Keep replay cuts realistic: cumulative transcript snapshots, no mid-word
  cuts, more filler, more mixed signal, and longer multi-step sessions.
- [ ] Include the approved case adjustments:
  - `buy-bread-merge` uses the 3-step split with the correction moved into step 3
  - `god-milk-asr-context` removes the unnatural step-2 phrasing and relies on later context
  - `supplier-memo-recap` moves the recap cut so step 5 ends with `let me recap, I need JC`

### Task 7: Run the replay benchmark definition against the curated dataset

**Files:**
- Reference: `evals/benchmarks/todo_replay_bench_v1.yaml`
- Reference: `evals/locks/todo_replay_bench_v1.json`

- [ ] Treat `todo_replay_bench_v1` as the existing benchmark definition ID, not
  as a lock file name.
- [ ] If this benchmark has not been run before and no local lock exists yet,
  create the first lock by running:
  `cd backend && uv run python ../evals/cli.py benchmark run todo_replay_bench_v1`
- [ ] If the benchmark already has a local lock and the hosted dataset has
  changed, refresh that lock by running:
  `cd backend && uv run python ../evals/cli.py benchmark run todo_replay_bench_v1 --rebase`
- [ ] Generate a report for the updated replay benchmark state.
- [ ] Run:
  `cd backend && uv run python ../evals/cli.py benchmark report todo_replay_bench_v1 --json`
- [ ] Record the resulting batch ID and confirm the report reflects the updated
  replay benchmark run.

### Phase 3 acceptance gates

- [ ] If no replay lock exists yet: `cd backend && uv run python ../evals/cli.py benchmark run todo_replay_bench_v1`
- [ ] If a replay lock already exists and the hosted dataset changed: `cd backend && uv run python ../evals/cli.py benchmark run todo_replay_bench_v1 --rebase`
- [ ] `cd backend && uv run python ../evals/cli.py benchmark report todo_replay_bench_v1 --json`

Do not begin Phase 4 until these gates pass or are blocked only by missing
external credentials that have been explicitly called out.

## Phase 4: Benchmark report case enrichment

### Task 8: Switch benchmark report case enrichment to one all-traces query

**Files:**
- Modify: `evals/logfire_query.py`
- Modify: `evals/report.py`
- Modify if needed: `backend/tests/test_item7_logfire_query.py`
- Modify if needed: `backend/tests/test_item7_benchmark_report.py`

- [ ] Replace per-trace case-span requests with a single case-span query over
  all selected `trace_id`s.
- [ ] Pass an explicit API `limit` for the case-span query request.
- [ ] Keep this change narrow:
  - do not introduce `Retry-After` handling yet
  - do not introduce `min_timestamp` / `max_timestamp` filtering yet
  - do not switch the report path to MCP
- [ ] Keep the benchmark selection and headline-metric logic unchanged.
- [ ] Run:
  `cd backend && uv run pytest tests/test_item7_logfire_query.py tests/test_item7_benchmark_report.py -v`
- [ ] If live credentials are available, use this proof procedure against one
  fixed benchmark state:
  - do not rerun the benchmark between baseline capture and after-change report
  - save the baseline report to
    `.context/todo_extraction_bench_report.phase4-baseline.json`
    with:
    `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json > ../.context/todo_extraction_bench_report.phase4-baseline.json`
  - after the code change, save the new report to
    `.context/todo_extraction_bench_report.phase4-after.json`
    with:
    `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json > ../.context/todo_extraction_bench_report.phase4-after.json`
  - compare those two files and prove all of the following:
    - every `entry_id` present in the baseline is present in the after report
    - `selected_run_id` is unchanged for every entry
    - `headline_metric_value` is unchanged for every entry
    - at least one entry that had empty case-level enrichment in the baseline
      now has populated case-level enrichment in the after report
  - populated case-level enrichment means at least one of:
    - `max_case_duration_s` is not `null` and `slowest_cases` is not empty
    - `failure_count > 0` and `failures` is not empty
  - if that proof cannot be established clearly, the phase fails

### Phase 4 acceptance gates

- [ ] `cd backend && uv run pytest tests/test_item7_logfire_query.py tests/test_item7_benchmark_report.py -v`
- [ ] If credentials are available, baseline and after-change
  `todo_extraction_bench_v1` JSON reports prove all of the following on the
  same fixed benchmark state:
  - same `entry_id` set
  - same `selected_run_id` values
  - same `headline_metric_value` values
  - at least one entry that had empty case-level enrichment in the baseline now
    has populated case-level enrichment in the after report
  - any failure to prove those statements counts as gate failure

The next item must not begin until these Phase 4 gates pass or are blocked only
by missing external credentials that have been explicitly called out.

## Phase 5: Persistent benchmark reports

### Task 9: Persist benchmark reports under benchmark-owned paths

**Files:**
- Modify: `evals/report.py`
- Modify: `evals/cli.py`
- Modify or add helper if needed: `evals/storage.py`
- Modify if needed: `backend/tests/test_item7_benchmark_report.py`
- Modify if needed: `backend/tests/test_item7_logfire_report_integration.py`
- Add if needed: `evals/reports/`

- [ ] Persist benchmark JSON reports at `evals/reports/<benchmark_id>.json`.
- [ ] Make `benchmark report <benchmark_id>` ensure that durable file exists.
- [ ] Reuse the stored report when the benchmark state is unchanged.
- [ ] Recompute and overwrite the stored report when the benchmark state has
  changed.
- [ ] Keep the user-visible report schema unchanged.
- [ ] Do not treat `.context` proof files as benchmark-owned outputs.
- [ ] Run:
  `cd backend && uv run pytest tests/test_item7_benchmark_report.py tests/test_item7_logfire_report_integration.py -v`
- [ ] If live credentials are available, use this proof procedure against
  `todo_extraction_bench_v1`:
  - remove or move aside any pre-existing
    `evals/reports/todo_extraction_bench_v1.json`
  - run:
    `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json`
  - prove that `evals/reports/todo_extraction_bench_v1.json` now exists and its
    contents match the CLI JSON output
  - capture the stored file checksum and modification time
  - run the same command again without changing benchmark state
  - prove the stored file checksum and modification time are unchanged
  - for refresh behavior, prove via tests or a controlled benchmark-state
    change that when the benchmark state differs, the next report invocation
    rewrites `evals/reports/todo_extraction_bench_v1.json`
  - if that proof cannot be established clearly, the phase fails

### Phase 5 acceptance gates

- [ ] `cd backend && uv run pytest tests/test_item7_benchmark_report.py tests/test_item7_logfire_report_integration.py -v`
- [ ] If credentials are available:
  - `cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json`
  - the command creates `evals/reports/todo_extraction_bench_v1.json`
  - the durable report file matches CLI output
  - a second invocation on unchanged benchmark state reuses the same file
    rather than rewriting it
- [ ] Refresh on changed benchmark state is proven by tests or by a controlled
  benchmark-state change.
- [ ] Any failure to prove creation, reuse, or refresh counts as gate failure.

The next item must not begin until these Phase 5 gates pass or are blocked only
by missing external credentials that have been explicitly called out.
