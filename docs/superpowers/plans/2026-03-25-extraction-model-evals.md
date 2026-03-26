# Extraction Model Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable, config-driven eval harness for todo extraction so we can compare multiple LLM models and Gemini thinking settings against the same labeled dataset without editing production code between runs.

**Architecture:** The production extractor currently hardcodes a singleton `Agent("google-gla:gemini-3-flash-preview", ...)` in `backend/app/extract.py`. We will refactor that path so model choice and model settings are injectable, then build a code-first eval runner using Pydantic Evals. The plan now assumes a dedicated `extraction_quality` eval suite under `backend/evals/`, with one stable dataset file (`todo_extraction_v1.json`), one dataset loader module, one count-based evaluator module, one experiment-config module, and one runner module.

**Tech Stack:** FastAPI backend code, PydanticAI, Pydantic Evals, Logfire, pytest, Gemini via Google GLA, optional OpenAI / Anthropic providers later

**References:** `backend/app/extract.py`, `backend/app/models.py`, `backend/tests/test_extract.py`, `backend/tests/fixtures/`, `docs/references/logfire-trace-analysis.md`

---

## Scope

This plan covers exactly five deliverables:

1. Refactor extraction so model and model settings are runtime configuration instead of hardcoded singleton state.
2. Create and maintain a dedicated extraction dataset asset for this eval suite.
3. Implement an initial count-based evaluator strategy for this task.
4. Add a Pydantic Evals runner that can execute the same dataset against multiple model configs and annotate results in Logfire.
5. Document how to run and compare experiments without editing or committing code changes between runs.

Out of scope for this plan:

- retuning `TOKEN_THRESHOLD`
- stop-path / `<fin>` latency work
- prompt redesign beyond simple version labeling
- end-to-end audio + Soniox evals
- automatic dataset generation from production traces
- shipping a new model to production by default

---

## Eval Strategy

We will treat this as an extraction-task eval, not a full pipeline eval.

- Input: finalized transcript text plus deterministic `reference_dt`; `previous_todos` remains in the case schema for later expansion but is `null` in v1
- Output: structured `Todo` list
- Ground truth: a stable dedicated extraction dataset asset in the repo
- Initial seed material: existing `result.json` fixtures under `backend/tests/fixtures/`
- Initial scoring metric: `todo_count_match` only
- First experiment matrix:
  - `google-gla:gemini-3-flash-preview` with provider defaults
  - `google-gla:gemini-3-flash-preview` with minimal thinking
  - `google-gla:gemini-2.5-flash` with thinking disabled
  - `google-gla:gemini-2.5-flash-lite` with thinking disabled
- Later experiment matrix:
  - OpenAI / Anthropic variants once keys are available

The initial goal is not to find a perfect scoring system. It is to create a stable harness that lets us compare quality, latency, token use, and cost on the same cases.

---

## Design Gates

These two design gates are now resolved for the first implementation pass:

### Design Gate 1 - Dedicated dataset asset

Decision:

- create one dedicated extraction-only dataset file: `backend/evals/extraction_quality/todo_extraction_v1.json`
- make that file the canonical source for eval runs
- treat `backend/tests/fixtures/*/result.json` as seed material, not the long-term source of truth
- keep the dataset format as JSON so it stays easy to inspect and stable in git
- keep the scope narrow: finalized transcript to todo extraction only for v1
- include `reference_dt` in every case so date-sensitive outputs are deterministic
- keep `expected_todos` in the dataset even though the v1 evaluator only uses todo count

### Design Gate 2 - Evaluator strategy

Decision:

- use a single deterministic evaluator: `todo_count_match`
- define success as predicted todo count exactly matching expected todo count
- treat empty / noisy transcript cases as passing only when both expected and predicted counts are zero
- do not score todo text, `due_date`, `assign_to`, `category`, `priority`, or `notification` in v1
- keep richer expected todo data in the dataset so stricter evaluators can be added later without redesigning the asset

This keeps the first eval harness intentionally narrow: it answers "did the model extract the right number of todos?" and leaves wording and field-quality analysis for a later pass after the prompt and schema are tightened.

---

## File Map

### Backend - New files

| File | Responsibility |
|------|----------------|
| `backend/evals/extraction_quality/todo_extraction_v1.json` | Dedicated stable dataset file for extraction-quality experiments; canonical source for eval runs |
| `backend/evals/extraction_quality/dataset_loader.py` | Load `todo_extraction_v1.json` into a Pydantic Evals dataset with deterministic case metadata |
| `backend/evals/extraction_quality/evaluators.py` | Count-based evaluator implementation for extraction quality in the first pass |
| `backend/evals/extraction_quality/experiment_configs.py` | Named experiment-config registry for model and provider settings under this eval suite |
| `backend/evals/extraction_quality/run.py` | CLI runner for extraction-quality experiment configs and Logfire-backed evaluation runs |
| `backend/evals/extraction_quality/README.md` | Short usage guide for running this eval suite and reading results |

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/extract.py` | Replace hardcoded singleton assumptions with configurable extraction settings and a reusable agent factory |
| `backend/tests/test_extract.py` | Add tests for runtime model overrides and provider-specific settings passthrough |

### Backend - Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/app/models.py` | Defines `Todo` and `ExtractionResult`, which the eval task and evaluators will use directly |
| `backend/tests/fixtures/*/result.json` | Existing golden transcripts and expected todo lists |
| `backend/app/main.py` | Existing Logfire configuration for instrumentation patterns |

---

## Task 1: Refactor extraction to support runtime model config

**Files:**
- Modify: `backend/app/extract.py`
- Modify: `backend/tests/test_extract.py`

Today `extract_todos()` always uses a cached singleton agent with model `google-gla:gemini-3-flash-preview`. That makes multi-model experiments awkward and risks leaking the first-created model into later runs. We need a one-time refactor so model choice becomes data instead of code.

- [ ] **Step 1: Add failing tests for runtime extraction config**

Extend `backend/tests/test_extract.py` with focused tests that prove:

1. `extract_todos()` can accept an override model name without mutating global production defaults
2. provider-specific settings are passed through to agent creation
3. two different model configs in one process do not reuse the wrong cached agent

Suggested cases:

```python
async def test_extract_todos_uses_override_model():
    ...

async def test_extract_todos_passes_model_settings():
    ...

async def test_get_agent_does_not_reuse_different_model_config():
    ...
```

- [ ] **Step 2: Run extractor tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_extract.py -v`

Expected: FAIL because the current API does not accept model overrides or settings

- [ ] **Step 3: Introduce extraction config and configurable agent construction**

Refactor `backend/app/extract.py` to add a configuration object and explicit agent creation. Keep the production default equal to the current behavior.

Recommended shape:

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "google-gla:gemini-3-flash-preview"
    model_settings: dict[str, Any] | None = None
    prompt_version: str = "v1"
```

Add:

```python
def build_extraction_agent(config: ExtractionConfig) -> Agent[None, ExtractionResult]:
    ...
```

Update:

```python
async def extract_todos(
    transcript: str,
    *,
    reference_dt: datetime | None = None,
    previous_todos: list[Todo] | None = None,
    config: ExtractionConfig | None = None,
) -> list[Todo]:
    ...
```

Implementation guidance:

- preserve the current default model when `config is None`
- allow experiments to pass provider-specific settings such as `google_thinking_config`
- avoid a bare module-level singleton keyed only by "first call wins"
- if caching is retained, key it by the full config rather than a single global

- [ ] **Step 4: Run extractor tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_extract.py -v`

Expected: PASS

- [ ] **Step 5: Commit the extraction-config refactor**

```bash
git add backend/app/extract.py backend/tests/test_extract.py
git commit -m "refactor: make todo extraction model configurable"
```

---

## Task 2: Create the dedicated extraction dataset asset

**Files:**
- Add: `backend/evals/extraction_quality/todo_extraction_v1.json`
- Add: `backend/evals/extraction_quality/dataset_loader.py`

We already have nine labeled extraction fixtures. The design decision for v1 is to create one dedicated JSON dataset file for evals, seeded from those fixtures but maintained independently from them.

- [x] **Step 1: Resolve the dataset asset design**

Resolved dataset decisions:

- dataset file name: `todo_extraction_v1.json`
- dataset path: `backend/evals/extraction_quality/todo_extraction_v1.json`
- serialized format: JSON
- scope: extraction-specific for finalized transcript evaluation in v1
- source of truth: this dataset file, not the fixture directory
- seed source: existing `backend/tests/fixtures/*/result.json`
- new cases should be added by editing the dataset file directly after the initial seed import

Expected output of this step:

- a documented dataset decision
- a stable asset path and naming convention
- a case schema we agree to support

- [ ] **Step 2: Create the first dedicated dataset asset**

Create the dedicated asset from the agreed dataset design.

Implementation guidance:

- use the existing fixtures as the initial seed
- preserve empty-output cases such as transcripts with no actionable todos
- keep the file human-reviewable in git
- keep the schema stable enough that future experiment runs do not require rewriting the dataset
- include `reference_dt` for every case
- include `previous_todos` in the schema, set to `null` for the current finalized-transcript cases
- keep the full expected todo objects in the dataset even though the initial evaluator only checks count

- [ ] **Step 3: Implement the dataset loader**

Add `backend/evals/extraction_quality/dataset_loader.py` that loads the dedicated asset and produces a `Dataset` of cases.

Recommended case shape:

```python
Case(
    name=case_name,
    inputs={
        "transcript": transcript_text,
        "reference_dt": reference_dt,
        "previous_todos": None,
    },
    expected_output=expected_todos,
    metadata={
        "dataset": "todo_extraction_v1",
        "case_type": "extraction",
        "source_fixture": source_fixture,
    },
)
```

Implementation guidance:

- keep the loader deterministic
- use the existing `Todo` schema shape as the normalized expected output
- do not require Logfire access to build the dataset

- [ ] **Step 4: Commit the dataset asset and loader**

```bash
git add backend/evals/extraction_quality/todo_extraction_v1.json backend/evals/extraction_quality/dataset_loader.py
git commit -m "feat: add dedicated extraction eval dataset"
```

---

## Task 3: Implement the evaluator strategy

**Files:**
- Add: `backend/evals/extraction_quality/evaluators.py`

The first eval pass intentionally uses one deterministic metric only: todo count match. This keeps the first version focused on extraction presence and leaves wording and field-quality checks for a later plan revision.

- [x] **Step 1: Resolve the evaluator strategy**

Resolved evaluator decisions:

- required metric: `todo_count_match`
- success rule: predicted todo count equals expected todo count
- empty / noisy transcript rule: pass only when both counts are zero
- no text matching in v1
- no field-level scoring in v1
- no LLM judge in v1

Expected output of this step:

- a documented evaluator strategy
- a first-pass metric set
- clear rules for how scores should be interpreted in Logfire

- [ ] **Step 2: Implement the first evaluator set**

Add `backend/evals/extraction_quality/evaluators.py` based on the chosen strategy.

Recommended evaluator outputs:

- `todo_count_match`
- `expected_todo_count`
- `predicted_todo_count`

Implementation guidance:

- keep the evaluator deterministic and explainable
- report expected and predicted counts alongside the pass/fail metric
- do not infer text quality or field correctness from this metric alone
- keep the module small enough that future evaluators can be added without rewriting the runner

- [ ] **Step 3: Commit the evaluator module**

```bash
git add backend/evals/extraction_quality/evaluators.py
git commit -m "feat: add count-based extraction eval evaluator"
```

---

## Task 4: Add a config-driven Pydantic Evals runner with Logfire metadata

**Files:**
- Add: `backend/evals/extraction_quality/experiment_configs.py`
- Add: `backend/evals/extraction_quality/run.py`
- Modify: `backend/app/extract.py` (if needed for final wiring)

This is the heart of the experiment workflow. The runner should accept named experiment configs, execute the same dataset for each, and record enough metadata in Logfire to compare runs without code edits.

- [ ] **Step 1: Write a minimal smoke test or dry-run check for the runner**

If a full integration test is too heavy, add a smoke-level unit test or at least a `--list-experiments` mode that can be asserted in CI.

Suggested behavior:

```bash
cd backend && uv run python evals/extraction_quality/run.py --list-experiments
```

Expected output includes:

- `gemini3_default`
- `gemini3_minimal_thinking`
- `gemini25_flash_no_thinking`
- `gemini25_flash_lite_no_thinking`

- [ ] **Step 2: Implement named experiment configs**

Define a small experiment-config registry in `backend/evals/extraction_quality/experiment_configs.py`:

```python
EXPERIMENTS = {
    "gemini3_default": ExtractionConfig(...),
    "gemini3_minimal_thinking": ExtractionConfig(
        model_name="google-gla:gemini-3-flash-preview",
        model_settings={"google_thinking_config": {"thinking_level": "minimal"}},
    ),
    "gemini25_flash_no_thinking": ExtractionConfig(
        model_name="google-gla:gemini-2.5-flash",
        model_settings={"google_thinking_config": {"thinking_budget": 0}},
    ),
    ...
}
```

Implementation guidance:

- keep the runner generic enough to add OpenAI / Anthropic configs later
- include a stable `prompt_version` field in experiment metadata
- allow `--repeat N` and `--max-concurrency N`

- [ ] **Step 3: Wire dataset evaluation and Logfire metadata**

Use Pydantic Evals to evaluate the same dataset against each named config.

Recommended metadata:

- `experiment`
- `model_name`
- `prompt_version`
- `provider`
- `thinking_mode`

Recommended CLI flags:

- `--experiment <name>` (repeatable)
- `--all`
- `--repeat <n>`
- `--max-concurrency <n>`
- `--list-experiments`

Important behavior:

- if a required provider key is missing, skip that experiment with a clear message
- do not require any code edit to switch models
- default to Google-only experiments if only `GEMINI_API_KEY` is present

- [ ] **Step 4: Manually run the first experiment set**

Run:

```bash
cd backend && uv run python evals/extraction_quality/run.py --all --repeat 2 --max-concurrency 2
```

Expected:

- the same dataset runs against each named experiment
- console output prints a Pydantic Evals report per experiment
- Logfire shows separate experiments with model metadata attached

- [ ] **Step 5: Commit the eval runner**

```bash
git add backend/evals/extraction_quality/experiment_configs.py backend/evals/extraction_quality/run.py backend/app/extract.py
git commit -m "feat: add config-driven extraction eval runner"
```

---

## Task 5: Document the experiment workflow

**Files:**
- Add: `backend/evals/extraction_quality/README.md`

The goal is to make future model trials easy and boring. A teammate should be able to add a config, run the experiments, and compare results in Logfire without reading implementation code. The docs should also record the dataset and evaluator decisions once those are made.

- [ ] **Step 1: Write the README**

Document:

1. what this eval harness measures
2. what it does not measure
3. how the dedicated dataset asset is structured and maintained
4. how to list experiments
5. how to run one experiment
6. how to run the whole matrix
7. how to compare experiments in Logfire
8. how to add a new model config safely

Include example commands:

```bash
cd backend && uv run python evals/extraction_quality/run.py --list-experiments
cd backend && uv run python evals/extraction_quality/run.py --experiment gemini3_default
cd backend && uv run python evals/extraction_quality/run.py --all --repeat 3 --max-concurrency 2
```

- [ ] **Step 2: Add caveats and guardrails**

Document the main traps explicitly:

- the production extractor previously used a singleton agent
- dataset asset scope is intentionally extraction-specific unless explicitly expanded later
- the initial evaluator only measures todo count, not todo wording or field correctness
- cross-provider experiments need corresponding API keys
- eval scores are decision support, not automatic rollout criteria

- [ ] **Step 3: Commit the docs**

```bash
git add backend/evals/extraction_quality/README.md
git commit -m "docs: add extraction eval workflow guide"
```

---

## Validation Checklist

- [ ] `extract_todos()` supports explicit runtime config without changing production defaults
- [ ] the dataset asset decision is documented and implemented as a stable repo asset
- [ ] the evaluator strategy is documented before metric implementation begins
- [ ] the count-based evaluator explains why a case passed or failed via expected and predicted counts
- [ ] the eval runner can compare multiple model configs in one run
- [ ] Logfire metadata cleanly separates experiments by model / thinking configuration
- [ ] no code edits are required to switch between experiment configs

---

## Recommended First Execution Order

1. Implement the extraction-config refactor.
2. Create the dataset asset and loader using the resolved `todo_extraction_v1.json` design.
3. Implement the count-based evaluator.
4. Add the Google-only experiment matrix and run it.
5. Review Logfire results and sample outputs before adding non-Google providers.

---

## Open Questions To Revisit After The First Eval Run

- Are the current nine fixtures enough seed material for `todo_extraction_v1.json`?
- When should we add field-level evaluators for `due_date`, `assign_to`, or `category` after the prompt and schema are tightened?
- Do we need separate scoring for transcript-noise robustness versus extraction count accuracy?
- Is `gemini-3-flash-preview` with minimal thinking competitive enough that a provider switch is unnecessary?
- Do we need a second eval track for incremental extraction with `previous_todos`, not just final transcript extraction?
