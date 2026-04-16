# Legacy Benchmark Docs

The old manifest-based benchmark contract under `backend/evals/benchmarks/` is
deprecated.

Use the repo-root benchmark definitions and benchmark-first CLI instead:

```bash
cd backend && uv run python ../evals/cli.py benchmark list
cd backend && uv run python ../evals/cli.py benchmark show todo_extraction_bench_v1
cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --html
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --open
```

Canonical files now live under:

- `../evals/benchmarks/`
- `../evals/locks/`
- `../evals/reports/`
