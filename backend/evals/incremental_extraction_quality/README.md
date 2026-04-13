# Incremental Extraction Quality

This harness evaluates replayed incremental extraction, where transcript text
arrives in ordered steps and the extractor carries prior todos forward between
steps.

## Scope

This suite measures:

- replayed incremental extraction behavior
- whether final replay output matches the expected final todo count
- differences across experiment configs such as model, provider, and prompt

This suite does not measure:

- live STT quality
- intermediate-step wording quality
- field-level semantic correctness beyond the evaluator contract

## Core Terms

- `case`: one replay example
- `dataset`: the static suite of replay cases plus evaluators
- `experiment`: one concrete replay run of `dataset.evaluate(...)`
- `batch execution`: one CLI invocation that may run one or more experiments

One batch execution prints a single `batch_id`. Each experiment in that batch
keeps its own `experiment_id`.

## Results Model

Tracked replay results live in Logfire. The runner no longer writes local JSON
artifacts and no longer performs a post-run enrichment pass.

Use Logfire to:

- find runs by `batch_id`
- compare replay experiments by `experiment_id`
- inspect per-case durations and traces
- inspect replay-step trace attributes such as `replay_step_<n>_todos`

## Files

- `../../evals/datasets/replay/todo_extraction_replay_v1.json`: canonical replay dataset
- `dataset_loader.py`: replay dataset loader
- `evaluators.py`: replay evaluator definitions
- `experiment_configs.py`: shared experiment registry
- `run.py`: CLI runner

For live smoke validation, use:

- `backend/tests/fixtures/evals/todo_extraction_replay_smoke.json`

## Replay Behavior

For each case, the runner:

1. starts with `previous_todos = null`
2. replays transcript snapshots in order
3. passes the previous step’s todos into the next step
4. scores only the final replay output

Replay-step todo payloads remain visible in traces through
`replay_step_<n>_todos` attributes.

## Running

List experiments:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py --list-experiments
```

Run one tracked replay experiment:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py \
  --experiment gemini3_flash_default
```

Run the replay smoke dataset through the tracked path:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py \
  --experiment gemini3_flash_default \
  --dataset-path tests/fixtures/evals/todo_extraction_replay_smoke.json
```

Run a local-only smoke replay without Logfire write credentials:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py \
  --experiment gemini3_flash_default \
  --dataset-path tests/fixtures/evals/todo_extraction_replay_smoke.json \
  --allow-untracked
```

`--allow-untracked` is only for explicit local smoke runs. It is not the normal
comparison path.

Useful flags:

- `--repeat N`
- `--task-retries N`
- `--max-concurrency N`
- `--dataset-path PATH`
- `--allow-untracked`

## Operator Workflow

After a tracked replay run finishes:

1. capture the printed `batch_id`
2. open Logfire
3. filter or search by `batch_id`
4. inspect each replay experiment via `experiment_id`
5. drill into replay traces to inspect `replay_step_<n>_todos`

That is now the standard path for timings, traces, and replay inspection.

## Benchmark Workflow

Replay benchmarks use the repo-root benchmark definitions and the same
benchmark-first CLI as transcript extraction.

Key files:

- `../evals/benchmarks/replay_llm_matrix_v1.yaml`
- `../evals/datasets/replay/todo_extraction_replay_v1.json`

Primary commands:

```bash
cd backend && uv run python ../evals/cli.py benchmark list
cd backend && uv run python ../evals/cli.py benchmark show replay_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark run replay_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark report replay_llm_matrix_v1
```

Tracked replay runs stay benchmark-agnostic. Benchmark state is reconstructed by
matching replay benchmark entries against experiment-scoped metadata in tracked
history.

## Network Note

Replay evals still require normal outbound DNS and HTTPS access for provider
calls and Logfire trace shipping. Treat DNS-style transport errors as
execution-environment issues first.
