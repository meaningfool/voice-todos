# Item 6 Design: Extraction Model Evals

Scope: define the local LLM experiment set, dataset boundary, and scoring approach for transcript-to-todo extraction evals.

## Why this exists

The extraction path is now important enough that we need a stable way to compare models without editing production code between runs. The eval design needs to answer a simple question first:

- given the same finalized transcript, which LLM setup most reliably extracts the right number of todos at acceptable latency and cost?

This design intentionally keeps the first pass narrow so we can get a repeatable harness working before we expand into richer field-quality scoring.

## Goals

- Compare multiple LLM extraction candidates on the same local dataset
- Keep experiments local and repeatable
- Avoid code edits when switching models or thinking settings
- Start with a simple, explainable score: `todo_count_match`
- Keep the dataset rich enough to support stricter evaluators later

## Non-goals

- Evaluating live STT behavior
- Measuring end-to-end audio pipeline quality
- Scoring wording quality or field accuracy in v1
- Automatically promoting a winning model to production

## Approved Eval Decisions

- Input: finalized transcript text plus deterministic `reference_dt`
- Incremental context: `previous_todos` stays in the case schema for future expansion but is `null` in v1
- Output: structured `Todo` list
- Dataset: `backend/evals/extraction_quality/todo_extraction_v1.json`
- Initial metric: `todo_count_match`
- Empty / noisy transcript success: expected and predicted todo counts must both be zero

## First LLM Experiment Matrix

| Experiment ID | Model | Thinking config | Purpose |
|---|---|---|---|
| `gemini3_flash_default` | `google-gla:gemini-3-flash-preview` | provider default | Gemini3 Flash default |
| `gemini3_flash_minimal_thinking` | `google-gla:gemini-3-flash-preview` | `thinking_level="minimal"` | Gemini3 Flash minimal thinking |
| `gemini31_flash_lite_default` | `google-gla:gemini-3.1-flash-lite-preview` | provider default | New lightweight Google candidate |
| `gemini31_flash_lite_minimal_thinking` | `google-gla:gemini-3.1-flash-lite-preview` | `thinking_level="minimal"` | Faster low-cost Google comparison |
| `mistral_small_4_default` | `mistral-small-2603` | provider default | First Mistral extraction candidate |

The first run should include exactly these experiments when the corresponding provider keys are available.

## Dataset Boundary

The extraction eval is transcript-only, not full-pipeline:

- source seed: `backend/tests/fixtures/*/result.json`
- canonical eval asset: `backend/evals/extraction_quality/todo_extraction_v1.json`
- case shape includes `transcript`, `reference_dt`, `previous_todos`, and full `expected_todos`
- the first evaluator only reads expected todo count, but the dataset keeps full expected todo objects for future expansion

## Scoring

The first version uses one deterministic metric:

- `todo_count_match`

Why this is enough for v1:

- it is easy to explain
- it avoids pretending that wording and optional fields are more tightly specified than they are today
- it still gives a useful first pass across latency, cost, and extraction presence

What we are explicitly deferring:

- todo text matching
- `due_date`, `assign_to`, `category`, `priority`, and `notification` scoring
- LLM-judge evaluation

## Reporting Expectations

Each experiment run should make it easy to compare:

- experiment name
- model name
- provider
- prompt version
- thinking mode
- expected todo count
- predicted todo count
- pass/fail for `todo_count_match`
- latency and token usage where available from provider instrumentation

## Relationship To Other Eval Work

- STT model evals are a separate track and should not be mixed into this harness
- the stack comparison document in `docs/references/eval-models-and-stacks.md` is the broad candidate inventory
- this design is the narrower source of truth for the extraction LLM experiment set

## Open Questions After The First Run

- Is `gemini-3.1-flash-lite-preview` strong enough to become the default lightweight Google extraction candidate?
- Is `mistral-small-2603` strong enough to justify deeper Mistral-side eval investment?
- When are the extraction prompt and optional fields specified tightly enough to justify richer evaluators?
