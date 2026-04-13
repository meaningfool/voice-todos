# Extraction Quality Evals

This harness evaluates transcript-to-todo extraction against a fixed labeled
dataset using Pydantic Evals, with Logfire as the canonical tracked-results
store.

## Scope

This suite measures:

- transcript-only extraction from finalized transcript text
- final todo-count agreement for each case
- differences across experiment configs such as model, provider, and prompt

This suite does not measure:

- live STT behavior or end-to-end audio quality
- incremental replay behavior
- field-level todo correctness beyond what the evaluator captures

## Core Terms

- `case`: one labeled eval example
- `dataset`: the static suite of cases plus evaluators
- `experiment`: one call to `dataset.evaluate(...)` for one concrete config
- `batch execution`: one CLI invocation that may run one or more experiments

One batch execution prints a single `batch_id`. Each experiment inside that
batch has its own `experiment_id`.

## Results Model

Tracked runs live in Logfire. Local JSON artifacts are no longer the source of
truth and are no longer written by the runner.

Use Logfire to:

- find all experiments from one batch via `batch_id`
- compare experiments via `experiment_id`
- inspect per-case durations, traces, and eval metadata

## Files

- `../../evals/datasets/extraction/todo_extraction_v1.json`: canonical transcript-only dataset
- `dataset_loader.py`: dataset loader
- `evaluators.py`: evaluator definitions
- `experiment_configs.py`: named experiment registry
- `run.py`: CLI runner

For live smoke validation, use:

- `backend/tests/fixtures/evals/todo_extraction_smoke.json`

## Setup

Provider credentials still come from the shared `backend/.env` when they are
not already in the environment.

Tracked runs require Logfire write credentials. The runner checks the standard
Logfire credential locations described in `backend/app/logfire_setup.py`.

Hosted dataset bootstrap and later hosted dataset updates require a
dataset-scoped `LOGFIRE_DATASETS_TOKEN` in the shared `backend/.env`.

The credential storage model for Conductor worktrees is documented in:

- `docs/references/2026-04-13-credential-storage-and-logfire-access.md`

## Running

List experiments:

```bash
cd backend && uv run python evals/extraction_quality/run.py --list-experiments
```

Run one tracked experiment:

```bash
cd backend && uv run python evals/extraction_quality/run.py \
  --experiment gemini3_flash_default
```

Run a smoke dataset through the tracked path:

```bash
cd backend && uv run python evals/extraction_quality/run.py \
  --experiment gemini3_flash_default \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json
```

Run a local-only smoke check without Logfire write credentials:

```bash
cd backend && uv run python evals/extraction_quality/run.py \
  --experiment gemini3_flash_default \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json \
  --allow-untracked
```

`--allow-untracked` is an explicit escape hatch for local smoke runs only. Do
not use it for tracked comparisons or benchmark data collection.

Useful flags:

- `--repeat N`
- `--task-retries N`
- `--max-concurrency N`
- `--dataset-path PATH`
- `--allow-untracked`

## Operator Workflow

After a tracked run finishes:

1. note the printed `batch_id`
2. open Logfire
3. find the batch via `batch_id`
4. compare individual experiments via `experiment_id`

That is now the normal inspection path for timings, traces, and per-case
results.

## Benchmark Workflow

For curated comparisons, use the repo-root benchmark definitions under
`evals/benchmarks/`.

Key files:

- `../evals/benchmarks/extraction_llm_matrix_v1.yaml`
- `../evals/datasets/extraction/todo_extraction_v1.json`

Primary commands:

```bash
cd backend && uv run python ../evals/cli.py benchmark list
cd backend && uv run python ../evals/cli.py benchmark show extraction_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark run extraction_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark report extraction_llm_matrix_v1
```

The benchmark definition owns comparison intent. Tracked experiment metadata
stays benchmark-agnostic, and benchmark state is reconstructed from execution
history rather than attached benchmark membership.

## Network Note

Provider-backed evals still need normal outbound DNS and HTTPS access. If a run
fails with a DNS-style transport error, treat that as an execution-environment
problem before treating it as a model regression.
