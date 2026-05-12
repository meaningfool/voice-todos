# Evals

This repo uses a benchmark-first eval layout.

## Canonical Files

- `benchmarks/`: benchmark definitions
- `locks/`: locked dataset snapshots
- `reports/`: committed benchmark reports and report UI artifacts
- `cli.py`: main benchmark CLI entrypoint

The backend eval harnesses live under `backend/evals/`, but the benchmark contract surface is rooted here.

## Common Commands

From `backend/`:

```bash
uv run python ../evals/cli.py benchmark list
uv run python ../evals/cli.py benchmark show todo_extraction_bench_v1
uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1
uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1
uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --html
```

## Why Reports Are Committed

`evals/reports/` stays in the repo on purpose:

- it gives the benchmark report UI a stable example artifact
- it preserves reference outputs for doc and review workflows
- it makes benchmark/report structure inspectable without rerunning hosted evals

These committed artifacts should stay sanitized and path-portable.
