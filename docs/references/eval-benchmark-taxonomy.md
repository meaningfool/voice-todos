# Eval Benchmark Taxonomy

This document explains the durable benchmark vocabulary and lifecycle used by
the repo's eval tooling.

It is about the current benchmark contract, not about the older item-numbered
design history.

## Purpose

The repo uses a benchmark-first eval surface rooted under [evals/](../../evals).

That surface exists to answer a stable question:

- for a named comparison set, which configured entries are current, stale,
  missing, or failing, and what is the latest comparable result for each one?

## Core Files

- [evals/benchmarks/](../../evals/benchmarks): benchmark definitions
- [evals/locks/](../../evals/locks): locked hosted-dataset snapshots
- [evals/reports/](../../evals/reports): persisted JSON and HTML reports
- [evals/cli.py](../../evals/cli.py): benchmark CLI entrypoint
- [evals/run.py](../../evals/run.py): benchmark execution orchestration
- [evals/report.py](../../evals/report.py): benchmark report assembly
- [evals/resolution.py](../../evals/resolution.py): entry resolution and
  comparability selectors

## Core Terms

| Term | Meaning in this repo |
|---|---|
| `benchmark` | One long-lived comparison contract |
| `benchmark_id` | Stable ID for that comparison contract |
| `entry` | One labeled config inside a benchmark |
| `dataset_family` | Which suite shape the benchmark uses, such as transcript extraction or replay |
| `lock` | The repo-controlled snapshot of the hosted dataset used for reproducible comparisons |
| `batch_id` | Metadata that groups sibling experiments launched by one CLI run |
| `benchmark report` | Derived comparison output across the latest comparable run for each entry |

The important split is:

- `benchmark_id` answers: which comparison set is this result part of?
- `batch_id` answers: which launch event produced this result?

## Benchmark Definition

A benchmark definition names:

- the hosted dataset to compare against
- the dataset family
- the headline metric
- execution defaults such as repeat count, retries, and concurrency
- the list of entries to compare

Each entry adds a concrete model/provider/config combination.

## Locking Model

Hosted datasets are not trusted implicitly at runtime. The repo keeps a lock
file under [evals/locks/](../../evals/locks) for each benchmark.

That lock is the reproducible dataset contract used for:

- local execution
- comparability selectors
- stale-dataset detection

If the hosted dataset changes, the benchmark becomes stale until the operator
either:

- keeps using the locked snapshot explicitly, or
- rebases the benchmark onto the new hosted dataset and refreshes the lock

## Run Lifecycle

`benchmark run` in [evals/cli.py](../../evals/cli.py) does the following:

1. load the benchmark definition
2. ensure a usable lock exists
3. detect whether the benchmark is stale
4. resolve entry configs into concrete suite/provider/model settings
5. decide which entries need execution
6. launch suite-specific runners
7. collect `batch_id`s for the entries that actually ran

The execution layer is metadata-driven. It does not rely on directory naming to
infer benchmark membership.

## Comparability Model

[evals/resolution.py](../../evals/resolution.py) builds a selector for each
entry using:

- dataset hash
- evaluator-contract hash
- prompt hash
- config fingerprint
- model name
- retry/repeat settings

That selector is what lets reporting choose the latest comparable run for an
entry without guessing from filenames alone.

## Report Lifecycle

`benchmark report` in [evals/report.py](../../evals/report.py) does the
following:

1. load the benchmark and current lock state
2. build selectors for every entry
3. query Logfire for candidate runs
4. select the latest matching run per entry
5. assemble entry states such as `current`, `missing`, or `stale`
6. persist a sanitized JSON report under [evals/reports/](../../evals/reports)
7. optionally render or open the HTML report UI

The committed report artifacts are examples and reviewable outputs, not the
canonical experiment store. Logfire remains the canonical tracked-results
system.

## Why Reports Are Committed

The repo keeps benchmark reports committed on purpose:

- the HTML report UI needs a stable example artifact
- reviewers can inspect the report structure without rerunning hosted evals
- the benchmark surface stays legible from a clean checkout

These committed artifacts should stay sanitized and path-portable.

## Operational Rules

- Treat the lock file as the reproducibility contract.
- Treat stale benchmarks explicitly; do not silently compare against a changed
  hosted dataset.
- Treat the benchmark report as derived output from tracked experiment metadata.
- Keep benchmark membership metadata-driven rather than filesystem-driven.
