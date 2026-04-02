# Extraction Quality Evals

This eval harness compares transcript-to-todo extraction experiments against the
same labeled dataset without editing production code between runs.

## What This Measures

- Transcript-only extraction quality for finalized transcript text
- Whether a model extracts the expected number of todos
- Per-experiment differences in model, provider, prompt version, and thinking mode
- Latency and provider metadata when those are available through the eval stack

## What This Does Not Measure

- Live STT behavior or end-to-end audio quality
- Incremental extraction with non-null `previous_todos`
- Todo wording quality
- Field correctness for `due_date`, `assign_to`, `category`, `priority`, or
  `notification`
- Automatic rollout decisions

The v1 evaluator is intentionally narrow. It measures count accuracy only.

## Files

- `todo_extraction_v1.json`: canonical extraction dataset asset
- `dataset_loader.py`: loads the dataset into `pydantic_evals.Dataset`
- `evaluators.py`: deterministic count-based evaluator set
- `experiment_configs.py`: named experiment registry and availability checks
- `run.py`: CLI runner for listing and executing experiments

## Local Setup

The harness reads provider credentials from `backend/.env` when the variables are
not already present in the shell. That file is gitignored, so it does not show up
automatically in a new worktree. Create it by copying the checked-in template:

```bash
cp backend/.env.example backend/.env
```

If you prefer to share one file across worktrees, symlink `backend/.env` to the
copy you keep elsewhere instead of duplicating it.

Logfire credentials are separate from `backend/.env`. The Logfire CLI stores
them under `backend/.logfire/logfire_credentials.json` by default, and that
directory is also local to each worktree unless you copy or symlink it:

```bash
ln -s /absolute/path/to/shared/backend/.logfire backend/.logfire
```

The standalone `evals/extraction_quality/run.py` CLI now configures Logfire on
startup. If `backend/.logfire` is present, `LOGFIRE_CREDENTIALS_DIR` points to a
shared location, or `LOGFIRE_TOKEN` is set, the runner can ship traces
remotely. Without credentials it still creates local trace/span IDs, but you
will not see the run in the hosted Logfire UI.

## Dataset Asset

The dataset is a stable repo asset at
`backend/evals/extraction_quality/todo_extraction_v1.json`.

It is seeded from `backend/tests/fixtures/*/result.json`, but after the initial
seed this file is the source of truth for eval runs.

Each case stores:

- `name`: stable case id
- `source_fixture`: original fixture name
- `reference_dt`: deterministic datetime for date resolution
- `previous_todos`: currently always `null` in v1
- `transcript`: finalized transcript text
- `expected_todos`: full expected todo objects

Example shape:

```json
{
  "name": "stop-the-button",
  "source_fixture": "stop-the-button",
  "reference_dt": "2026-03-24T09:30:00+00:00",
  "previous_todos": null,
  "transcript": "Stop",
  "expected_todos": []
}
```

Keep this asset human-reviewable. Add or edit cases directly in the dataset file
instead of teaching the runner to regenerate it implicitly.

## Evaluator Strategy

The first-pass evaluator returns:

- `todo_count_match`
- `expected_todo_count`
- `predicted_todo_count`

A case passes only when expected and predicted counts are equal. Empty or noisy
transcripts pass only when both counts are zero.

This is decision support for extraction presence, not evidence that the todo
text or optional fields are correct.

## Listing Experiments

```bash
cd backend && .venv/bin/python evals/extraction_quality/run.py --list-experiments
```

The output lists every configured experiment and whether it is runnable in the
current environment.

Current experiment ids:

- `gemini3_flash_default`
- `gemini3_flash_minimal_thinking`
- `gemini31_flash_lite_default`
- `gemini31_flash_lite_minimal_thinking`
- `mistral_small_4_default`

If an experiment is unavailable, the runner prints the reason instead of
failing the whole command.

## Running One Experiment

```bash
cd backend && .venv/bin/python evals/extraction_quality/run.py --experiment gemini3_flash_default
```

Useful flags:

- `--repeat N`: rerun each case N times
- `--max-concurrency N`: control concurrent case execution inside an experiment

## Running The Whole Matrix

```bash
cd backend && .venv/bin/python evals/extraction_quality/run.py --all --repeat 3 --max-concurrency 2
```

The runner:

- loads the dedicated dataset asset
- attaches the count-based evaluator set
- skips experiments whose provider credentials or provider support are missing
- prints one `pydantic_evals` report per runnable experiment
- writes JSON artifacts under `backend/evals/extraction_quality/results/` by
  default, with one timestamped directory per run

## Comparing Experiments In Logfire

The runner configures Logfire itself and still attaches experiment metadata with
`set_eval_attribute`, so the main remaining requirement is having credentials
available to the process through `backend/.logfire`,
`LOGFIRE_CREDENTIALS_DIR`, or `LOGFIRE_TOKEN`.

When Logfire credentials are available, runs can be separated by:

- `experiment`
- `model_name`
- `provider`
- `prompt_version`
- `thinking_mode`

Per-case eval results also include the count metrics from `evaluators.py`, which
lets you compare where models over-extract, under-extract, or match exactly.

When reviewing Logfire for a run that was actually instrumented:

- compare experiments with the same dataset and prompt version
- use `todo_count_match` first for pass/fail trend
- inspect `expected_todo_count` and `predicted_todo_count` for why a case passed
  or failed
- treat latency and token/cost data as supporting evidence, not the only signal

## Adding A New Model Config Safely

1. Add a new entry in `experiment_configs.py`.
2. Keep `prompt_version` explicit in the `ExtractionConfig`.
3. Set `provider` and `thinking_mode` metadata so reports stay comparable.
4. Make sure the provider credentials and provider package support are available.
5. Run `--list-experiments` first to confirm the new config is discoverable.
6. Run the new experiment alone before adding it to larger comparison runs.

For prompt tweaks, start with one experiment and only move to the full matrix if
the targeted run looks promising. That keeps the feedback loop short and avoids
spending time or provider quota on a broad rerun too early.

Prefer small, named configs over ad-hoc code edits. The point of this harness is
to make model switching a data change, not a production-path change.

## Caveats And Guardrails

- The production extractor previously used a singleton agent. This harness exists
  partly to avoid first-call-wins model reuse during eval runs.
- The dataset scope is intentionally extraction-specific. Do not silently expand
  it into an STT or end-to-end harness.
- The initial evaluator measures todo count only. It does not validate wording
  or optional fields.
- Cross-provider experiments need the corresponding API keys and provider
  support installed.
- Eval scores are decision support, not automatic rollout criteria.
