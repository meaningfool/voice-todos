# Incremental Extraction Quality

This eval harness measures how well the extractor handles a replayed transcript
that arrives in steps, where each new step can refine or extend the todo list
built by previous steps.

## What This Measures

- Item 6.5 replay quality for incremental transcript extraction
- Whether the extractor carries prior todos forward correctly across steps
- Whether the final todo count matches the replay case's expected final count
- Differences between experiment configs such as model, provider, and thinking
  mode

## What This Does Not Measure

- The quality of intermediate step-by-step wording
- Field-level correctness for the todo text or optional metadata
- Live speech-to-text quality
- Audio timing, diarization, or other end-to-end voice pipeline behavior
- Any score based on partial or intermediate step outputs

Item 6.5 is intentionally narrower than item 6. It replays incremental
extraction state, but the evaluator only checks the final todo count.

## How This Differs From Item 6

Item 6 measures transcript-to-todo extraction from a finalized transcript with
`previous_todos = null`.

Item 6.5 measures replayed incremental extraction:

- the transcript arrives as ordered snapshots instead of one final transcript
- `previous_todos` is threaded from one replay step into the next
- each model lives with its own earlier extraction decisions
- only the final replay output is scored

Use item 6 when you want a from-scratch extraction comparison. Use item 6.5
when you want to measure carried-state behavior across one recorded session.

## Dataset Shape

The replay dataset lives at
`backend/evals/incremental_extraction_quality/todo_extraction_replay_v1.json`.

Each case in the dataset uses this contract:

- `name`: stable case id
- `source_fixture`: original fixture name for traceability
- `reference_dt`: ISO datetime used when resolving relative dates
- `replay_steps`: ordered list of transcript snapshots
- `replay_steps[].step_index`: 1-based step number
- `replay_steps[].transcript`: transcript text for that snapshot
- `expected_final_todos`: the final todo list after the last replay step

The loader turns each case into a `pydantic_evals` case with:

- `reference_dt`
- `replay_steps`
- expected output equal to `expected_final_todos`
- metadata that records the dataset name, case type, and source fixture

Example shape:

```json
{
  "name": "refine-todo",
  "source_fixture": "refine-todo",
  "reference_dt": "2026-03-24T09:30:00+00:00",
  "replay_steps": [
    {
      "step_index": 1,
      "transcript": "I need to buy milk."
    },
    {
      "step_index": 2,
      "transcript": "I need to buy milk. Actually, buy oat milk instead."
    }
  ],
  "expected_final_todos": [
    {
      "text": "Buy oat milk from the organic store",
      "category": "Shopping"
    }
  ]
}
```

Keep the dataset human-reviewable. Update the JSON directly instead of teaching
the runner to regenerate it implicitly.

## How Replay Works

For each case, the runner:

1. Starts with `previous_todos = null`
2. Replays each transcript snapshot in order
3. Calls `extract_todos(...)` for every step, passing the current transcript,
   the shared `reference_dt`, and the todos from the previous step
4. Stores the todos returned by each step in the replay result
5. Uses the last step's todos as the final output for scoring

The replay state is threaded through `previous_todos`, so the harness tests
incremental behavior rather than isolated transcript-only extraction.

## Final-Count-Only Scoring

The evaluator checks only whether the final predicted todo count matches the
expected final todo count.

- pass when `len(final_todos) == len(expected_final_todos)`
- fail when the counts differ
- ignore the wording of the todos
- ignore optional fields and field-level exactness
- ignore intermediate step counts except as supporting debug data

This makes item 6.5 a replay fidelity check, not a full semantic accuracy
benchmark.

## Running Experiments

List available experiments:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py --list-experiments
```

Run one experiment:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py --experiment gemini3_flash_default
```

Run the whole matrix:

```bash
cd backend && uv run python evals/incremental_extraction_quality/run.py --all --repeat 3 --max-concurrency 1
```

Useful flags:

- `--repeat N`: rerun each case `N` times
- `--max-concurrency N`: control concurrent case execution inside one experiment
- `--output-dir PATH`: write artifacts somewhere other than the default results
  directory

## Inspecting Per-Step Outputs

Per-step outputs are preserved in the JSON artifacts written by the replay
runner. By default, they live under
`backend/evals/extraction_quality/results/<timestamp>/<experiment>.json`.

Each artifact includes:

- `cases[].step_results[]` with the transcript and todos for every replay step
- `cases[].trace_id` and `cases[].span_id` for cross-referencing traces
- aggregate metrics and final count metrics for the run

When Logfire credentials are configured, the runner also attaches per-step
attributes named `replay_step_<n>_todos`, which makes manual inspection easier
in the trace UI.

## Caveats And Guardrails

- Item 6.5 is a replay harness, not a new scoring framework for todo wording or
  field completeness.
- The dataset contract depends on ordered replay steps. Do not renumber or
  reshuffle them without updating the expected final output.
- Cross-provider experiments still need the relevant API keys and provider
  packages available.
- Eval scores are decision support, not automatic rollout criteria.
- If you are comparing runs, keep the dataset version and prompt version fixed
  so the final-count signal stays meaningful.
