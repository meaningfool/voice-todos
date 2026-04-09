# Eval Benchmark Architecture Contrast

This note captures the conceptual difference between the eval architecture we are building in Items 6.8 and 6.9 and the architecture used in `kwindla/aiewf-eval`.

It is a reference document, not a source-of-truth spec. The source-of-truth design documents remain:

- `docs/superpowers/specs/2026-04-07-item6.8-eval-result-structure-and-process-design.md`
- `docs/superpowers/specs/2026-04-08-item6.9-benchmark-abstraction-design.md`

## Why this document exists

The two systems use the word `benchmark` differently.

That can make the 6.8/6.9 design feel more abstract than it is, especially when comparing it to a repo like `aiewf-eval` where the benchmark concept is tied directly to the local directory structure.

This document explains:

- what each system is grouping
- how runs are associated to a benchmark
- how repeated runs are aggregated
- why `benchmark_id` and `batch_id` are both needed in the 6.9 model

## The 6.8 and 6.9 taxonomy

This repo is aligning to Pydantic Evals and Logfire terminology first, then adding a small number of repo-specific concepts on top.

| Concept | Meaning in this repo |
|---|---|
| `Dataset` | The static eval suite and evaluator contract |
| `Experiment` | One execution of `dataset.evaluate(...)` |
| `EvaluationReport` | The result of one experiment |
| `Batch execution` | One CLI invocation that may launch one or many experiments |
| `batch_id` | Metadata that groups sibling experiments created by the same launch |
| `Benchmark` | A repo-level comparison contract above experiments |
| `benchmark_id` | Metadata that says which long-lived comparison set an experiment belongs to |
| `benchmark report` | Derived comparison output across many experiments |

The important split is:

- `benchmark_id` answers: "which comparison set is this experiment part of?"
- `batch_id` answers: "which local launch event produced this experiment?"

## How `aiewf-eval` uses the word `benchmark`

In `aiewf-eval`, a benchmark is a repo-defined scenario package under `benchmarks/<name>/`.

Examples in the public repo:

- `aiwf_long_context`
- `aiwf_medium_context`

Each benchmark package contains the scenario definition:

- `config.py`
- `prompts/system.py`
- `data/knowledge_base.txt`

In practice, that benchmark package is doing several jobs at once:

- naming the evaluation scenario
- defining the shared turns, tools, and prompt context
- providing the top-level namespace under `runs/<benchmark>/...`

That means the benchmark concept there is closer to "scenario definition plus output namespace" than to the 6.9 meaning of "comparison contract above experiments."

Useful upstream references:

- Repository: `https://github.com/kwindla/aiewf-eval`
- Benchmark discovery and run-dir creation: `https://github.com/kwindla/aiewf-eval/blob/main/src/multi_turn_eval/cli.py`
- Example benchmark config: `https://github.com/kwindla/aiewf-eval/blob/main/benchmarks/aiwf_medium_context/config.py`
- Aggregation script: `https://github.com/kwindla/aiewf-eval/blob/main/aggregate_results.py`

## How a run is associated to a benchmark in `aiewf-eval`

Association is primarily filesystem-based.

The flow is:

1. the operator runs `multi-turn-eval run <benchmark_name> --model <model> ...`
2. the CLI imports `benchmarks.<benchmark_name>.config`
3. the run output directory is created at `runs/<benchmark_name>/<timestamp>_<model>_<suffix>`
4. later commands infer the benchmark again from the run path

The final suffix is not a semantic identifier. It is a short random fragment used to avoid directory-name collisions when runs happen close together.

The important consequence is:

- benchmark membership is inferred from directory location, not from explicit per-run benchmark metadata stored in a canonical remote system

## How aggregation works in `aiewf-eval`

There are multiple scripts, but the common pattern is:

- select runs from the filesystem
- bucket them by benchmark folder and model name
- skip obviously unusable runs
- aggregate scores across the remaining turns

### `aggregate_results.py`

This is the strictest built-in aggregator in the public repo.

Its behavior is:

- it scans one benchmark folder, currently hard-coded as `runs/aiwf_medium_context`
- it parses the model name from each run directory name
- it strips the trailing random suffix so repeated runs of the same model fall into one bucket
- it only includes runs that have `claude_summary.json`
- it takes the `N` most recent judged runs per model, with `N=5` by default
- it aggregates by summing counts across all included turns

This means:

- it does not choose one "best" run
- it does not use all historical runs by default
- it usually uses the 5 most recent judged runs per model

### Handling failed or incomplete runs

The skip rules are lightweight:

- if a run has no `claude_summary.json`, it is skipped as failed, incomplete, or not yet judged
- if a run has a summary but only partial judged coverage, it can still be included
- when strict turn-pass totals are missing, the scripts fall back to other available counts

So the system distinguishes more strongly between:

- missing or unjudged runs: excluded
- partial but judged runs: included proportionally

That is convenient for exploratory benchmarking, but it is not a strong compatibility contract.

### What it does not validate strongly

The aggregation scripts do not enforce a rich comparability manifest.

They mostly assume comparability from:

- being under the same benchmark folder
- being parsed as the same model name
- being recent enough or matching the operator's glob pattern

They do not strongly validate, at aggregation time, that all included runs share the same:

- prompt revision
- judge model
- pipeline or transport settings
- repo commit
- benchmark version
- execution settings

Those constraints are mostly handled by operator discipline and repo conventions, not by a first-class benchmark membership contract.

## The main architectural contrast

The key difference is not "local files versus Logfire."

The key difference is where the comparison contract lives.

### In `aiewf-eval`

- the benchmark package and directory layout carry most of the grouping meaning
- repeated runs are gathered later from the filesystem
- aggregation assumes comparability from shared location and naming conventions

### In the 6.8 and 6.9 model

- Logfire is the canonical store for experiment results
- `Dataset` remains the native Logfire and Pydantic eval grouping concept
- `Benchmark` is a repo-level comparison contract above experiments
- benchmark membership should be reconstructed from metadata, not inferred from directory layout

That makes the 6.9 model more explicit:

- compatibility is something we define
- membership is something we record
- reports are something we derive

## Why `benchmark_id` and `batch_id` are both needed

This is the part that tends to be confusing at first.

In `aiewf-eval`, one CLI invocation usually creates one local run directory for one model on one benchmark scenario. Because the unit of execution is narrower, there is less pressure to introduce a separate concept like `batch`.

In our 6.8 and 6.9 model, one batch execution may launch many experiments at once.

Example:

- benchmark goal: compare 7 models on one dataset and evaluator contract
- batch A launches 5 experiments
- batch B later launches 2 more experiments

The right identities are:

- all 7 experiments share one `benchmark_id`
- the first 5 share one `batch_id`
- the later 2 share another `batch_id`

That separation matters because the two questions are different:

- `benchmark_id`: which experiments are meant to be compared together?
- `batch_id`: which experiments were launched together operationally?

Without `benchmark_id`, later additive runs are hard to reconstruct as one coherent comparison set.

Without `batch_id`, it becomes harder to inspect one local launch event in Logfire, especially when many experiments land on the same dataset page over time.

## Rough mapping between the two architectures

The concepts do not map one-to-one, but this is the closest practical translation.

| `aiewf-eval` concept | Closest concept in this repo | Important caveat |
|---|---|---|
| benchmark package under `benchmarks/<name>` | dataset/scenario definition | In `aiewf-eval` this also acts as the output namespace |
| `runs/<benchmark>/...` folder | dataset page plus repo-local grouping convention | Our canonical grouping is not a local folder |
| one run directory | one experiment run or one local export of a run | Their run directory is usually a single-model execution |
| timestamp plus random suffix | run-instance identifier | Not equivalent to `benchmark_id`; only loosely analogous to a unique run instance |
| model-level aggregation over repeated run dirs | benchmark report or comparison output | Our version should be metadata-driven from Logfire |
| implicit grouping by folder and model name | explicit benchmark membership contract | This is the main 6.9 design difference |

## Practical implication for refining Item 6.9

When refining the 6.9 spec, the useful lesson from `aiewf-eval` is not to copy its directory model directly.

The useful lesson is that humans need an easy mental model for:

- what belongs together
- what was launched together
- what gets aggregated together later

The 6.9 design should keep those answers explicit:

- `Benchmark` is the durable comparison contract
- `Batch execution` is the local launch grouping
- `Experiment` is the atomic recorded result
- benchmark summaries are derived views over benchmark-member experiments
