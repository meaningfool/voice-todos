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

## Recommended Amendments After V1

This section preserves the approved v1 design above and records follow-up
recommendations for the next iteration of Item 6. These amendments do not
invalidate the original scope decisions; they clarify how to keep prompt
experiments, run metadata, and result comparisons clean as the harness grows.

### Prompt Source Of Truth And Version Identity

- keep extraction prompts version-controlled in the repo rather than leaving the
  canonical text inline inside `backend/app/extract.py`
- move extraction prompts into a dedicated prompt registry under a focused path
  such as `backend/app/prompts/todo_extraction/`
- load prompts through a small registry module instead of a loose inline dict in
  the extractor
- replace the bare `prompt_version` string in runtime config with a structured
  prompt reference that exposes:
  - `family`: stable prompt family name such as `todo_extraction`
  - `version`: human-facing milestone label such as `v1` or `v3`
  - `path`: canonical repo path to the prompt file
  - `content`: loaded prompt text passed to the agent
  - `sha256`: exact content fingerprint derived from `content`
- treat `version` as the human label and `sha256` as the exact prompt identity;
  a small wording tweak may keep the same milestone version during exploration,
  but it must still produce a new hash in eval metadata
- use new milestone versions for materially different prompt directions, for
  example `v1` to `v3`, instead of silently editing older prompt versions in
  place

### Agent Prompt API Choice

- prefer Pydantic AI `instructions` over `system_prompt` for static extraction
  guidance unless we specifically need prior system prompts to persist across
  message history boundaries
- if runtime context needs to affect prompt text later, add dynamic instructions
  deliberately rather than mixing prompt composition into the eval runner

### Configuration As Single Source Of Truth

- treat the experiment configuration object as the authoritative source for both
  task behavior and experiment metadata
- derive eval metadata from the same config object used to construct the agent,
  model settings, and prompt reference
- avoid duplicated hand-written metadata that can drift away from the actual
  task configuration
- minimum metadata for every experiment run should include:
  - experiment name
  - dataset name
  - model name
  - provider
  - thinking mode
  - prompt family
  - prompt version
  - prompt sha
  - git branch
  - git commit sha

### Provider And Module Boundaries

- split provider-specific model construction out of `backend/app/extract.py`
  into focused helper functions or provider modules
- retain lazy imports for optional or environment-sensitive providers such as
  Mistral so unsupported dependencies do not break Gemini-only development
- use top-of-file imports only for providers that are mandatory for the common
  path or guaranteed to be installed in the supported development environment
- keep the extraction module responsible for orchestration and input formatting,
  not provider bootstrapping details

### Result Persistence And Comparison Hygiene

- keep Logfire as the primary UI for browsing and comparing experiments
- add local result artifacts under `backend/evals/extraction_quality/results/`
  for durable reproducibility outside the Logfire UI
- each run artifact should record:
  - timestamp
  - dataset name and dataset version
  - experiment id
  - model and provider settings summary
  - prompt family, version, and sha
  - git branch and commit sha
  - repeat count and max concurrency
  - aggregate metrics
  - per-case pass/fail and count outputs
  - trace id and span id when available
- local result artifacts should be append-only and timestamped rather than
  overwritten, so later comparisons do not depend solely on terminal output or
  on Logfire retention windows

### Worktree And Credential Ergonomics

- document that `backend/.env` is intentionally gitignored and therefore
  per-worktree, not branch-tracked
- add `backend/.env.example` listing the variables relevant to this harness, at
  minimum `GEMINI_API_KEY`, optional `LOGFIRE_TOKEN`, and future provider keys
  as they are added
- recommend either copying or symlinking `.env` when creating new worktrees so
  eval availability is predictable and easy to debug

### Recommended Iteration Workflow

- when changing prompt text, run one experiment first to validate the new prompt
  direction against the target model before rerunning the full matrix
- rerun the full matrix only after the targeted comparison looks promising
- use the exact same dataset when comparing prompt variants so prompt changes
  are isolated from dataset drift
- use `prompt_sha` for exact comparison and the milestone version label for the
  broader prompt family history

### External Guidance Informing These Amendments

- Pydantic AI recommends `instructions` over `system_prompt` for most use cases
- Pydantic Evals recommends a configuration object as the single source of truth
  for both task configuration and experiment metadata
- Pydantic Evals recommends recording experiment metadata such as prompt version
  and commit context to support cross-run comparisons and reproducibility
- Logfire's eval UI is intended as the comparison layer for multiple experiment
  runs, while managed variables are useful for runtime overrides but should not
  replace repo-controlled prompt history for this harness
