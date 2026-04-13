# Legacy Benchmark Docs

The old manifest-based benchmark contract under `backend/evals/benchmarks/` is
deprecated.

Use the repo-root benchmark definitions and benchmark-first CLI instead:

```bash
cd backend && uv run python ../evals/cli.py benchmark list
cd backend && uv run python ../evals/cli.py benchmark show extraction_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark run extraction_llm_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark report extraction_llm_matrix_v1
```

Canonical files now live under:

- `../evals/benchmarks/`
- `../evals/datasets/`
