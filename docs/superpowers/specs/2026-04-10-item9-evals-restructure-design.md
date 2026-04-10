# Item 9 Design: Restructure Evals Around Stable Benchmarks

Scope: move eval-owned data and orchestration out of `backend/evals`, define a
small benchmark-first contract for datasets and benchmark definitions, and
migrate both transcript-only extraction and incremental replay evals to the new
structure through explicit gated phases.

## Why this exists

The current eval system works, but it mixes three concerns too tightly:

- production backend code
- eval datasets and benchmark definitions
- eval execution and reporting code

Today the repo keeps eval data, eval runner code, and some historical result
artifacts under `backend/evals/`. That makes the boundary between "the app" and
"the tool that evaluates the app" harder to reason about than it needs to be.

There is also a benchmark-modeling problem:

- the current experiment registry is code-first
- the benchmark concept is still emerging
- the current registry is not the most readable source of truth for a human who
  wants to compare a deliberate set of model and prompt candidates

Item 9 exists to make the eval system easier to understand and easier to evolve
without pretending that evals are part of the backend app itself.

## Goals

- make benchmark definitions the stable git-tracked source of truth for eval
  comparisons
- move eval-owned data and orchestration to a top-level `evals/` area
- keep production extraction logic in `backend/app/`
- support additive benchmark population, where a benchmark can be rerun later to
  fill only missing entries
- keep Logfire as the canonical tracked-results store
- cover both existing eval families:
  - transcript-only extraction quality
  - incremental replay extraction quality
- phase the migration so each step has automated acceptance criteria and an
  explicit gate before the next phase begins

## Non-goals

- changing the meaning of the current evaluators
- redesigning the extraction or replay task semantics
- building a separate repo for evals
- building a new eval UI
- introducing multi-axis benchmark matrices in this item
- redesigning production prompt or model-provider abstractions as part of this
  structural refactor

## Current State Summary

The current extraction evals live under:

- `backend/evals/extraction_quality/`
- `backend/evals/incremental_extraction_quality/`

The current concrete extraction experiment matrix is defined in
`backend/evals/extraction_quality/experiment_configs.py` and currently includes:

- `gemini3_flash_default`
- `gemini3_flash_minimal_thinking`
- `gemini31_flash_lite_default`
- `gemini31_flash_lite_minimal_thinking`
- `mistral_small_4_default`
- `deepinfra_qwen35_9b_default`
- `deepinfra_qwen35_4b_structured_tuned`

Replay currently reuses that same registry.

The production extraction path used by those runners lives in
`backend/app/extract.py`.

## Canonical Terms

- `dataset`: one git-tracked labeled collection of eval rows
- `benchmark`: one stable git-tracked comparison definition
- `benchmark entry`: one explicit candidate inside a benchmark
- `benchmark state`: the current assembled result state of a benchmark, using
  the latest compatible result for each entry
- `execution history`: the historical tracked runs that contributed to a
  benchmark over time

Important rule:

- a benchmark is the stable named object
- a benchmark is not redefined every time it is executed
- adding new entries to an existing benchmark is additive benchmark population,
  not a new benchmark version

## Design Decisions

### 1. Keep production extraction in the backend

Production extraction code stays in `backend/app/`.

For Item 9, `backend/app/extract.py` remains the production implementation that
evals call into. Renaming that file can be done later if desired, but it is not
required to achieve the architecture split.

This keeps a clean dependency shape:

- `evals` may depend on `backend/app`
- `backend/app` must not depend on `evals`

### 2. Move eval-owned data and orchestration to top-level `evals/`

The target structure is:

```text
backend/
  app/
    extract.py
  tests/
    fixtures/

evals/
  cli.py
  run.py
  report.py
  datasets/
    extraction/
      todo_extraction_v1.json
    replay/
      todo_extraction_replay_v1.json
  benchmarks/
    extraction_llm_matrix_v1.yaml
    replay_llm_matrix_v1.yaml
```

Meaning of each top-level eval file:

- `evals/cli.py`: user-facing eval commands
- `evals/run.py`: benchmark execution logic
- `evals/report.py`: benchmark reporting logic
- `evals/datasets/`: canonical reviewed dataset files
- `evals/benchmarks/`: canonical benchmark definitions

### 3. Treat `backend/tests/fixtures/` as raw evidence, not canonical benchmark data

`backend/tests/fixtures/` stays where it is.

Its role is:

- test fixtures
- replay evidence
- raw captured material

It is not the long-term canonical home for benchmark definitions.

### 4. Dataset files stay intentionally small

Dataset files should contain:

- `name`
- `version`
- `rows`

Each row should contain:

- `id`
- `input`
- `expected_output`
- optional `metadata`

Example extraction dataset:

```json
{
  "name": "todo_extraction",
  "version": "v1",
  "rows": [
    {
      "id": "call-mom-memo-supplier",
      "input": {
        "transcript": "I need to call Mom tonight...",
        "reference_dt": "2026-03-24T09:30:00+00:00",
        "previous_todos": null
      },
      "expected_output": [
        {
          "text": "Call Mom",
          "category": "Personal"
        }
      ],
      "metadata": {
        "source_fixture": "call-mom-memo-supplier"
      }
    }
  ]
}
```

Example replay dataset:

```json
{
  "name": "todo_extraction_replay",
  "version": "v1",
  "rows": [
    {
      "id": "refine-todo",
      "input": {
        "reference_dt": "2026-03-24T09:30:00+00:00",
        "replay_steps": [
          {
            "step_index": 1,
            "transcript": "I need to buy milk."
          },
          {
            "step_index": 2,
            "transcript": "I need to buy oat milk instead."
          }
        ]
      },
      "expected_output": [
        {
          "text": "Buy oat milk",
          "category": "Shopping"
        }
      ],
      "metadata": {
        "source_fixture": "refine-todo"
      }
    }
  ]
}
```

There is deliberately no `suite` field in the dataset file.

The loader should determine extraction versus replay from dataset location and
row shape, not from an extra explicit field.

### 5. Benchmark files use explicit entries, not one fixed block plus one variable field

The benchmark file should be the human-readable source of truth for what is
being compared.

The earlier "one variable field" design is too narrow for the real experiment
matrix, where one benchmark may compare:

- Gemini default
- Gemini minimal thinking
- Mistral default
- Qwen default
- Qwen tuned
- prompt variants across one or more models

The benchmark file should therefore list explicit entries.

Required benchmark fields:

- `benchmark_id`
- `dataset`
- `repeat`
- `task_retries`
- `max_concurrency`
- `entries`

Each entry should contain:

- `id`
- `provider`
- `model`
- `prompt_version`
- `model_settings`

Example:

```yaml
benchmark_id: extraction_llm_matrix_v1
dataset: evals/datasets/extraction/todo_extraction_v1.json

repeat: 3
task_retries: 1
max_concurrency: 1

entries:
  - id: gemini3_flash_default
    provider: google-gla
    model: gemini-3-flash-preview
    prompt_version: v1
    model_settings: {}

  - id: gemini3_flash_minimal_thinking
    provider: google-gla
    model: gemini-3-flash-preview
    prompt_version: v1
    model_settings:
      google_thinking_config:
        thinking_level: minimal

  - id: mistral_small_4_default
    provider: mistral
    model: mistral-small-2603
    prompt_version: v1
    model_settings: {}

  - id: deepinfra_qwen35_4b_structured_tuned
    provider: deepinfra
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    model_settings:
      temperature: 0
      max_tokens: 1024
```

### 6. Benchmark identity versus execution history

The benchmark itself is the stable named object.

Benchmark identity is defined by:

- benchmark file path and `benchmark_id`
- dataset reference
- benchmark entries
- `repeat`
- `task_retries`

`max_concurrency` should be recorded and queryable, but it should not be treated
as the primary reason to mint a new benchmark version. It is an execution-shape
parameter that may affect provider behavior, but it is not the core comparison
contract in the same way that dataset, entries, repeat, and retries are.

Additive benchmark change that stays within the same benchmark version:

- append new entries to the benchmark

Material benchmark change that should create a new benchmark version:

- change the dataset reference
- change `repeat`
- change `task_retries`
- materially change an existing entry config
- change the evaluator contract in a way that makes old and new results
  semantically non-comparable

### 7. Benchmark report semantics

`benchmark report <benchmark_id>` should show the current benchmark state.

That means:

- the latest compatible result for each entry is shown by default
- entries with no compatible result are shown as missing
- older compatible results remain available as history
- execution history exists, but it is not the primary user concept

This keeps the benchmark stable and readable while still preserving tracked run
history in Logfire.

### 8. Benchmark report output contract

Item 9 should define what `benchmark report <benchmark_id>` returns.

The default terminal report should contain:

- benchmark header:
  - `benchmark_id`
  - dataset `name`
  - dataset `version`
  - `repeat`
  - `task_retries`
  - `max_concurrency`
- benchmark population summary:
  - total benchmark entry count
  - populated entry count
  - missing entry count
- one row per benchmark entry showing:
  - `entry_id`
  - `provider`
  - `model`
  - `prompt_version`
  - compact `model_settings` summary
  - status:
    - `current`
    - `missing`
  - latest compatible result timestamp when present
  - completed case count
  - failure count
  - primary evaluator result summary for that suite

For extraction benchmarks, the initial primary evaluator result summary should
include:

- `todo_count_match` aggregate or pass-rate summary

For replay benchmarks, the initial primary evaluator result summary should
include:

- `final_todo_count_match` aggregate or pass-rate summary

`benchmark report <benchmark_id>` should also support a machine-readable output
mode such as `--json`.

The JSON report should include:

- benchmark metadata
- current compatibility contract
- a list of current entry states
- missing entry IDs
- history references sufficient to trace the selected current result back to
  Logfire

Item 9 does not need to define markdown, CSV, or rich history views. Those can
be added later.

### 9. CLI should be benchmark-first, not path-first and not execution-first

The public CLI should operate on benchmark IDs, not file paths.

Target commands:

- `benchmark list`
- `benchmark show <benchmark_id>`
- `benchmark run <benchmark_id>`
- `benchmark run <benchmark_id> --all`
- `benchmark report <benchmark_id>`

Behavior:

- `benchmark list`: list known benchmark IDs
- `benchmark show <id>`: print the benchmark definition
- `benchmark run <id>`: run only missing entries by default
- `benchmark run <id> --all`: force recomputation of all entries
- `benchmark report <id>`: show the current assembled benchmark state
- default report output is human-readable terminal output
- `benchmark report <id> --json` returns the machine-readable report contract
  described above

There may still be an internal per-invocation identifier in Logfire, but that is
an implementation detail, not a primary user-facing concept in Item 9.

### 10. Packaging note for this repo

This repo's current Python project root is `backend/`, not the repo root.

Item 9's target layout still moves eval-owned code to top-level `evals/`, but
the transition should not require solving repo-wide Python packaging in the same
step as the eval architecture split.

Therefore:

- benchmark-first CLI semantics are part of the design contract
- the temporary bootstrap path for invoking that CLI during migration is an
  implementation detail
- if a compatibility launcher or path bridge is needed during migration, that is
  acceptable as long as the public benchmark-first command model is preserved

## Phased Delivery

### Phase 1: Introduce top-level canonical data and benchmark definitions

Goal:

- create the new `evals/datasets/` and `evals/benchmarks/` structure
- copy current canonical dataset content into the new structure
- define the benchmark-entry contract in files

Expected work:

- create `evals/datasets/extraction/todo_extraction_v1.json`
- create `evals/datasets/replay/todo_extraction_replay_v1.json`
- create initial benchmark definition files under `evals/benchmarks/`
- add loaders or parser helpers that can read the new file formats

Automated acceptance criteria:

- extraction dataset loader reads the new dataset file and produces the same row
  count and row identities as the current extraction dataset loader
- replay dataset loader reads the new dataset file and produces the same row
  count and row identities as the current replay dataset loader
- benchmark loader parses the new explicit-entry benchmark files without
  ambiguity
- benchmark entries resolve to the same concrete configs as the current
  extraction experiment registry for equivalent candidates

Required automated tests:

- `tests/test_item9_dataset_migration.py`
  - verifies the new extraction dataset has the same row IDs as the current
    canonical extraction dataset
  - verifies the new replay dataset has the same row IDs as the current
    canonical replay dataset
  - verifies row counts match old and new sources exactly
  - verifies representative row payloads still contain the expected input and
    expected-output structure
- `tests/test_item9_benchmark_definitions.py`
  - verifies benchmark files parse successfully
  - verifies every benchmark entry has a unique `id`
  - verifies benchmark entries resolve to the same concrete provider, model,
    prompt, and model-settings values as the current legacy experiment registry
    for equivalent entries
  - verifies benchmark-level settings such as `repeat` and `task_retries` are
    parsed as required contract fields

Automated gate:

- a dedicated automated test target for new dataset and benchmark parsing must
  pass before Phase 2 begins
- expected gate command:
  - `cd backend && uv run pytest tests/test_item9_dataset_migration.py tests/test_item9_benchmark_definitions.py`
- the gate must run without live provider credentials
- the gate must run without live Logfire access

Phase gate rule:

- do not start Phase 2 until all Phase 1 automated acceptance criteria pass

### Phase 2: Add the new benchmark runner for transcript-only extraction

Goal:

- introduce the new benchmark-first execution path for extraction benchmarks
- keep the current backend runner path working during this phase

Expected work:

- add `evals/run.py`
- add `evals/cli.py`
- make `benchmark run <id>` resolve benchmark IDs to benchmark files
- make benchmark entries resolve to concrete extraction configs
- make the new runner call the existing production extraction path in
  `backend/app/extract.py`

Automated acceptance criteria:

- `benchmark list` surfaces the expected benchmark IDs
- `benchmark show <id>` prints the expected benchmark entry set
- benchmark entry resolution produces the same concrete extraction configs as
  the current code-first experiment registry for equivalent entries
- the new extraction benchmark runner can execute through a local automated path
  without live vendor calls, using stubbed or smoke-path execution where needed
- benchmark metadata written for tracked runs includes benchmark ID, dataset
  identity, entry ID, repeat, and task-retry settings

Required automated tests:

- `tests/test_item9_benchmark_cli.py`
  - verifies `benchmark list` returns the expected benchmark IDs
  - verifies `benchmark show <id>` returns the expected benchmark structure
  - verifies `benchmark run <id>` plans only missing entries by default
  - verifies `benchmark run <id> --all` plans all entries
- `tests/test_item9_extraction_runner.py`
  - verifies each extraction benchmark entry resolves to the expected concrete
    extraction config
  - verifies the runner calls the production extraction path with the expected
    config for each entry
  - verifies benchmark metadata includes benchmark ID, dataset identity, entry
    ID, repeat, and task-retry settings
  - verifies deterministic local execution works without live provider access

Automated gate:

- a dedicated automated test target for benchmark CLI resolution and extraction
  benchmark execution must pass before Phase 3 begins
- expected gate command:
  - `cd backend && uv run pytest tests/test_item9_benchmark_cli.py tests/test_item9_extraction_runner.py`
- the gate must not depend on live providers or live Logfire

Phase gate rule:

- do not start Phase 3 until all Phase 2 automated acceptance criteria pass

### Phase 3: Extend the new benchmark runner to replay and benchmark-state reporting

Goal:

- support replay benchmarks in the new structure
- support benchmark reporting as current assembled benchmark state

Expected work:

- teach `evals/run.py` to execute replay datasets through the same benchmark
  contract
- add `evals/report.py`
- implement benchmark report assembly using the latest compatible result for each
  benchmark entry
- support additive population:
  - default run only missing entries
  - `--all` reruns every entry

Automated acceptance criteria:

- replay benchmark entry resolution produces the expected concrete replay
  executions
- replay benchmark execution works through an automated local path without live
  provider calls
- benchmark report assembly correctly marks:
  - populated entries
  - missing entries
  - latest compatible result selection
- `benchmark run <id>` skips already populated entries
- `benchmark run <id> --all` forces rerun planning for all entries

Required automated tests:

- `tests/test_item9_replay_runner.py`
  - verifies replay benchmark entries resolve correctly
  - verifies replay execution threads prior todos across steps correctly
  - verifies replay benchmark metadata includes benchmark ID, dataset identity,
    entry ID, repeat, and task-retry settings
  - verifies default benchmark population skips already populated entries
  - verifies `--all` forces full replay rerun planning
- `tests/test_item9_benchmark_report.py`
  - verifies benchmark report assembly returns the expected terminal summary
    sections
  - verifies machine-readable report output contains benchmark metadata, current
    entry states, and missing entry IDs
  - verifies latest compatible result selection logic when multiple historical
    compatible results exist for one entry
  - verifies missing entries are reported as missing rather than silently
    omitted
- `tests/test_item9_logfire_report_integration.py`
  - verifies report queries work against a dedicated Logfire dev project
  - verifies the report can fetch and assemble benchmark state from real tracked
    data
  - verifies the selected current result for each entry matches the latest
    compatible tracked result in Logfire

Automated gate:

- a dedicated automated test target for replay benchmark execution, additive
  benchmark population, and report assembly must pass before Phase 4 begins
- expected gate command:
  - `cd backend && uv run pytest tests/test_item9_replay_runner.py tests/test_item9_benchmark_report.py`
- required live Logfire integration gate:
  - `cd backend && uv run pytest tests/test_item9_logfire_report_integration.py`
- the local gate must not depend on live providers or live Logfire
- the live Logfire gate must run against a dedicated Logfire dev project
- the live Logfire gate must not depend on live provider calls; it may use a
  deterministic tracked test path

Phase gate rule:

- do not start Phase 4 until both the local gate and the live Logfire gate pass

### Phase 4: Cut over to the new structure and reduce the old backend eval layout

Goal:

- make the new `evals/` structure the primary eval system
- retire or shrink the old backend eval organization

Expected work:

- switch documentation to the new benchmark-first CLI
- stop treating `backend/evals/.../experiment_configs.py` as the primary source
  of comparison definitions
- stop treating dataset copies under `backend/evals/` as canonical
- keep only the backend-owned pieces that should remain:
  - production extraction code
  - backend tests
  - raw fixtures

Automated acceptance criteria:

- docs and test commands reference the new benchmark-first flow
- canonical dataset loading paths point to `evals/datasets/`
- canonical benchmark loading paths point to `evals/benchmarks/`
- old backend eval entrypoints are either removed or clearly demoted to
  compatibility shims
- the new benchmark-first path remains green for both extraction and replay

Required automated tests:

- the Phase 1 dataset and benchmark-definition tests remain green
- the Phase 2 CLI and extraction-runner tests remain green
- the Phase 3 replay-runner, benchmark-report, and Logfire-report integration
  tests remain green
- one full benchmark smoke test verifies end-to-end benchmark execution and
  benchmark reporting through the new paths
- one compatibility test verifies any retained legacy backend eval entrypoint
  either delegates correctly or fails with an intentional deprecation path

Automated gate:

- the full automated Item 9 test target covering dataset loading, benchmark
  parsing, extraction execution, replay execution, and benchmark reporting must
  pass before old backend eval paths are removed or demoted
- expected gate command:
  - `cd backend && uv run pytest tests/test_item9_dataset_migration.py tests/test_item9_benchmark_definitions.py tests/test_item9_benchmark_cli.py tests/test_item9_extraction_runner.py tests/test_item9_replay_runner.py tests/test_item9_benchmark_report.py`
- expected live Logfire gate command:
  - `cd backend && uv run pytest tests/test_item9_logfire_report_integration.py tests/test_item9_benchmark_smoke_integration.py`
- the final phase requires both the full local gate and the live Logfire gate
  to pass

Phase gate rule:

- do not complete Phase 4 until all automated acceptance criteria pass

## Verification Principles

Item 9 must be verification-led.

That means:

- each phase must define automated acceptance criteria before implementation is
  considered complete
- no phase may claim completion without passing its automated gate
- every phase must have a local deterministic automated gate
- no phase gate should require live provider access
- phases that touch benchmark-state reporting against tracked data must also have
  a dedicated live Logfire integration gate
- live Logfire gates must target a dedicated dev project rather than production
- local deterministic tests and live Logfire integration tests serve different
  purposes and both are required once reporting is in scope

This is deliberate. Item 9 is primarily an architecture and ownership refactor.
Its local gates should prove structural correctness and behavioral equivalence,
while its live Logfire gates should prove that benchmark reporting works against
the real tracked-results system boundary.

## Open Questions To Keep Out Of Scope For Item 9

- whether `backend/app/extract.py` should later be renamed
- whether the repo should later move Python packaging from `backend/` to the
  repo root
- whether benchmark reporting should later expose richer history-selection modes
- whether benchmark definitions should later support multi-axis grids
- whether benchmark files should later gain optional labels or descriptions for
  presentation

Those may become follow-up items, but Item 9 should stay focused on the minimal
restructure described above.
