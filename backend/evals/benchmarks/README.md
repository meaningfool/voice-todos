# Eval Benchmarks

Benchmarks are git-tracked comparison manifests above individual eval runs.

The manifest owns benchmark membership through explicit
`attached_experiment_runs`. Experiments stay benchmark-agnostic in Logfire.

## Manifest Location

Store benchmark manifests in `backend/evals/benchmarks/`.

This directory should contain:

- one JSON manifest per benchmark
- optional notes or examples that help operators understand the benchmark

## Identity Terms

- `experiment_id`: stable identity for one evaluated config
- `experiment_run_id`: unique identity for one concrete run
- `batch_id`: one CLI launch that may produce several experiment runs

Benchmark membership uses `experiment_run_id`.

That means:

- rerunning the same config produces a new `experiment_run_id`
- a benchmark can attach one exact run without changing the experiment record
- multiple runs with the same `experiment_id` can coexist in one benchmark if
  you attach them explicitly

## Manifest Shape

Each manifest records:

- `benchmark_id`
- `title`
- `suite`
- `dataset_name`
- `dataset_sha`
- `evaluator_contract_sha`
- `fixed_config`
- `axes`
- `attached_experiment_runs`

Example: [`todo_extraction_model_smoke_v1.json`](./todo_extraction_model_smoke_v1.json)

## Current Matching Constraint

Launch resolution uses experiment identity metadata from the suite registry.
Coverage and report commands use the metadata fetched back from Logfire.

For the current implementation, the safest benchmark shape is:

- axis on `model_name`
- fixed config on `prompt_sha`
- choose coordinates that resolve to one experiment config each

If two experiment configs share the same `model_name` and `prompt_sha`, the
benchmark is ambiguous and `launch` will fail until you narrow the benchmark.

The example smoke manifest deliberately uses model names that are unique in the
current registry.

## Attach Existing Runs

Attach an already recorded experiment run:

```bash
cd backend && uv run python evals/benchmarking/run.py attach \
  evals/benchmarks/todo_extraction_model_smoke_v1.json \
  --experiment-run-id 2026-04-09T12-00-00Z-deadbeef--mistral_small_4_default
```

This only edits the benchmark manifest. It does not mutate the Logfire record.

## Launch From A Benchmark

Launch every coordinate in a benchmark:

```bash
cd backend && uv run python evals/benchmarking/run.py launch \
  evals/benchmarks/todo_extraction_model_smoke_v1.json \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json
```

Launch only missing coordinates:

```bash
cd backend && uv run python evals/benchmarking/run.py launch \
  evals/benchmarks/todo_extraction_model_smoke_v1.json \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json \
  --missing-only
```

Launch a subset of coordinates:

```bash
cd backend && uv run python evals/benchmarking/run.py launch \
  evals/benchmarks/todo_extraction_model_smoke_v1.json \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json \
  --coordinate model_name=mistral-small-2603
```

Local smoke launches without Logfire write credentials must be explicit:

```bash
cd backend && uv run python evals/benchmarking/run.py launch \
  evals/benchmarks/todo_extraction_model_smoke_v1.json \
  --dataset-path tests/fixtures/evals/todo_extraction_smoke.json \
  --allow-untracked
```

## Inspect Coverage

Coverage shows:

- attached compatible runs
- incompatible attachments
- missing attached runs
- unmappable runs
- missing coordinates

Command:

```bash
cd backend && uv run python evals/benchmarking/run.py coverage \
  evals/benchmarks/todo_extraction_model_smoke_v1.json
```

## Generate A Report

Reports are stable views over attached runs only.

Command:

```bash
cd backend && uv run python evals/benchmarking/run.py report \
  evals/benchmarks/todo_extraction_model_smoke_v1.json
```

## Operator Workflow

Typical flow:

1. define a benchmark manifest in git
2. launch from the benchmark or attach existing `experiment_run_id`s
3. inspect `coverage` to see what is still missing
4. rerun `launch --missing-only` as new runs become available
5. use `report` to generate the stable comparison set from attached runs

The benchmark boundary lives in the manifest, not in local run folders and not
in experiment-side metadata.
