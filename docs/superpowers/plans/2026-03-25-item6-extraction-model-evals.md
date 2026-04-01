# Item 6: Extraction Model Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-01-item6-extraction-model-evals-design.md`

**Goal:** Add a repeatable, config-driven eval harness for todo extraction so we can compare multiple LLM models and Gemini thinking settings against the same labeled dataset without editing production code between runs.

**Architecture:** The production extractor currently hardcodes a singleton `Agent("google-gla:gemini-3-flash-preview", ...)` in `backend/app/extract.py`. We will refactor that path so model choice and model settings are injectable, then build a code-first eval runner using Pydantic Evals. The plan now assumes a dedicated `extraction_quality` eval suite under `backend/evals/`, with one stable dataset file (`todo_extraction_v1.json`), one dataset loader module, one count-based evaluator module, one experiment-config module, and one runner module.

**Tech Stack:** FastAPI backend code, PydanticAI, Pydantic Evals, Logfire, pytest, Gemini via Google GLA, Mistral APIs, optional OpenAI / Anthropic providers later

**References:** `backend/app/extract.py`, `backend/app/models.py`, `backend/tests/test_extract.py`, `backend/tests/fixtures/`, `docs/references/logfire-trace-analysis.md`, `docs/references/eval-models-and-stacks.md`

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
  - `google-gla:gemini-3.1-flash-lite-preview` with provider defaults
  - `google-gla:gemini-3.1-flash-lite-preview` with minimal thinking
  - `mistral-small-2603` with provider defaults
- Later experiment matrix:
  - additional Gemini variants to be defined later
  - OpenAI / Anthropic variants once keys are available

The initial goal is not to find a perfect scoring system. It is to create a stable harness that lets us compare quality, latency, token use, and cost on the same cases.

Experiment availability note:

- the four Gemini experiments should work with the existing Google routing and `GEMINI_API_KEY`
- the Mistral experiment is intentionally listed, but it requires explicit Mistral provider wiring plus `MISTRAL_API_KEY`
- if the Mistral provider dependency or key is missing, the runner should skip that experiment clearly rather than fail the whole run

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

- `gemini3_flash_default`
- `gemini3_flash_minimal_thinking`
- `gemini31_flash_lite_default`
- `gemini31_flash_lite_minimal_thinking`
- `mistral_small_4_default`

- [ ] **Step 2: Implement named experiment configs**

Define a small experiment-config registry in `backend/evals/extraction_quality/experiment_configs.py`:

```python
EXPERIMENTS = {
    "gemini3_flash_default": ExtractionConfig(...),
    "gemini3_flash_minimal_thinking": ExtractionConfig(
        model_name="google-gla:gemini-3-flash-preview",
        model_settings={"google_thinking_config": {"thinking_level": "minimal"}},
    ),
    "gemini31_flash_lite_default": ExtractionConfig(
        model_name="google-gla:gemini-3.1-flash-lite-preview",
    ),
    "gemini31_flash_lite_minimal_thinking": ExtractionConfig(
        model_name="google-gla:gemini-3.1-flash-lite-preview",
        model_settings={"google_thinking_config": {"thinking_level": "minimal"}},
    ),
    "mistral_small_4_default": ExtractionConfig(
        model_name="mistral-small-2603",
    ),
    ...
}
```

Implementation guidance:

- the Gemini configs should use the existing Google path and current API key setup
- the Mistral config should only be enabled when `MISTRAL_API_KEY` and the Mistral provider dependency are available
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
- run only the subset of experiments whose provider keys are available

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
cd backend && uv run python evals/extraction_quality/run.py --experiment gemini3_flash_default
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
4. Add the initial LLM experiment matrix and run it.
5. Review Logfire results and sample outputs before adding non-Google providers.

---

## Open Questions To Revisit After The First Eval Run

- Are the current nine fixtures enough seed material for `todo_extraction_v1.json`?
- When should we add field-level evaluators for `due_date`, `assign_to`, or `category` after the prompt and schema are tightened?
- Do we need separate scoring for transcript-noise robustness versus extraction count accuracy?
- Is `gemini-3.1-flash-lite-preview` competitive enough that it should replace `gemini-3-flash-preview` as the lightweight default?
- Is `mistral-small-2603` competitive enough to justify expanding the Mistral-oriented stack work?
- Do we need a second eval track for incremental extraction with `previous_todos`, not just final transcript extraction?

---

## Follow-On Plan For Recommended Amendments After V1

Tasks 1 through 5 cover the first shipped harness. The tasks below implement the
recommended amendments recorded in
`docs/superpowers/specs/2026-04-01-item6-extraction-model-evals-design.md`
under `Recommended Amendments After V1`.

These tasks should preserve the existing dataset and evaluator behavior while
making prompt changes, metadata, and cross-run comparisons more durable and less
error-prone.

### Additional File Map For The Follow-On Slice

| File | Responsibility |
|------|----------------|
| `backend/app/prompts/todo_extraction/v1.md` | Canonical repo-backed prompt asset for the existing extraction prompt |
| `backend/app/prompts/registry.py` | Prompt registry that resolves prompt family/version into content and stable metadata |
| `backend/app/model_providers.py` | Provider-specific model factory helpers with lazy optional-provider loading |
| `backend/evals/extraction_quality/result_artifacts.py` | Serialize evaluation reports into append-only local artifact files |
| `backend/.env.example` | Example env file documenting eval-relevant credentials |
| `backend/tests/test_prompt_registry.py` | Focused tests for prompt loading and prompt fingerprint metadata |

Existing files to extend in this slice:

- `backend/app/extract.py`
- `backend/evals/extraction_quality/experiment_configs.py`
- `backend/evals/extraction_quality/run.py`
- `backend/evals/extraction_quality/README.md`
- `backend/tests/test_extract.py`
- `backend/tests/test_extraction_runner.py`

### Task 6: Externalize extraction prompts and introduce prompt references

**Files:**
- Add: `backend/app/prompts/todo_extraction/v1.md`
- Add: `backend/app/prompts/registry.py`
- Add: `backend/tests/test_prompt_registry.py`
- Modify: `backend/app/extract.py`
- Modify: `backend/tests/test_extract.py`

The current prompt is still embedded inline in `backend/app/extract.py`, and
`prompt_version` is only a loose string label. The next step is to make the
prompt repo-backed, explicitly addressable, and fingerprinted so later runs can
be compared exactly instead of by convention.

- [ ] **Step 1: Write failing tests for prompt loading and prompt metadata**

Add focused tests that prove:

1. prompt `todo_extraction/v1` is loaded from a repo-backed file
2. the resolved prompt object exposes `family`, `version`, `path`, `content`,
   and `sha256`
3. `build_extraction_agent()` uses resolved prompt content rather than an inline
   string constant
4. `extract.py` can reject unknown prompt versions with a clear error

Suggested tests:

```python
def test_get_prompt_ref_returns_expected_metadata():
    ...

def test_build_extraction_agent_uses_prompt_ref_content():
    ...

def test_unknown_prompt_version_raises_value_error():
    ...
```

- [ ] **Step 2: Run the prompt-related tests and confirm the new coverage fails**

Run:

```bash
cd backend && uv run pytest tests/test_prompt_registry.py tests/test_extract.py -v
```

Expected:

- FAIL because prompts are still inline and no prompt registry exists yet

- [ ] **Step 3: Add the prompt asset and registry**

Create the new prompt asset and registry.

Recommended shape:

```python
@dataclass(frozen=True)
class PromptRef:
    family: str
    version: str
    path: Path
    content: str
    sha256: str
```

Recommended helper:

```python
def get_prompt_ref(*, family: str, version: str) -> PromptRef:
    ...
```

Implementation guidance:

- move the existing extraction prompt text into
  `backend/app/prompts/todo_extraction/v1.md`
- compute `sha256` from the exact file content
- keep `version` human-facing and stable
- use `sha256` for exact-content identity in later metadata
- keep the registry small and explicit rather than dynamically scanning the
  filesystem

- [ ] **Step 4: Refactor extraction to consume prompt references**

Update `backend/app/extract.py` so `ExtractionConfig` no longer treats
`prompt_version` as a loose inline-string selector.

Recommended direction:

```python
@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "gemini-3-flash-preview"
    model_settings: dict[str, Any] | None = None
    prompt_family: str = "todo_extraction"
    prompt_version: str = "v1"
```

Implementation guidance:

- resolve prompt content via the prompt registry
- stop storing the extraction prompt text inline in `extract.py`
- preserve the current v1 behavior exactly
- thread prompt reference metadata through a helper so the runner can reuse it

- [ ] **Step 5: Prefer `instructions` over `system_prompt`**

Update agent construction to use Pydantic AI `instructions=` unless a concrete
need for `system_prompt=` remains after the refactor.

Implementation guidance:

- keep the prompt static for now; do not introduce dynamic instructions unless
  required by the current extraction task
- make this a behavior-preserving change
- keep the switch tightly covered by tests so the agent still receives the same
  extraction guidance

- [ ] **Step 6: Run the prompt and extractor tests to verify the refactor**

Run:

```bash
cd backend && uv run pytest tests/test_prompt_registry.py tests/test_extract.py -v
```

Expected:

- PASS

- [ ] **Step 7: Commit the prompt-registry slice**

```bash
git add backend/app/prompts/todo_extraction/v1.md backend/app/prompts/registry.py backend/app/extract.py backend/tests/test_prompt_registry.py backend/tests/test_extract.py
git commit -m "refactor: externalize extraction prompts"
```

### Task 7: Isolate provider-specific model construction

**Files:**
- Add: `backend/app/model_providers.py`
- Modify: `backend/app/extract.py`
- Modify: `backend/tests/test_extract.py`

The current extractor still contains provider-specific model construction logic.
That is serviceable for the first slice, but it mixes extraction orchestration
with provider bootstrapping and makes the optional-provider story harder to
reason about.

- [ ] **Step 1: Add failing tests for provider factory boundaries**

Extend the extractor tests so they prove:

1. Google model construction remains available without importing optional
   Mistral modules
2. Mistral construction stays lazy and only executes when a Mistral model is
   requested
3. `extract.py` delegates provider selection instead of assembling provider
   objects inline

Suggested tests:

```python
def test_build_model_uses_google_factory_for_gemini():
    ...

def test_build_model_uses_mistral_factory_lazily():
    ...
```

- [ ] **Step 2: Run the extractor tests and confirm the new coverage fails**

Run:

```bash
cd backend && uv run pytest tests/test_extract.py -v
```

Expected:

- FAIL because provider construction still lives directly in `extract.py`

- [ ] **Step 3: Move provider construction into focused helpers**

Create `backend/app/model_providers.py` with explicit helpers such as:

```python
def build_google_model(model_name: str, *, api_key: str) -> Any:
    ...

def build_mistral_model(model_name: str, *, api_key: str | None) -> Any:
    ...

def build_model(model_name: str, *, gemini_api_key: str) -> Any:
    ...
```

Implementation guidance:

- keep lazy imports for optional providers inside the provider-specific helper
- keep required-provider imports at module top level only when they are truly
  part of the always-available path
- make `extract.py` responsible for choosing config, formatting input, and
  requesting a model object from the provider module

- [ ] **Step 4: Re-run the extractor tests**

Run:

```bash
cd backend && uv run pytest tests/test_extract.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit the provider-boundary refactor**

```bash
git add backend/app/model_providers.py backend/app/extract.py backend/tests/test_extract.py
git commit -m "refactor: split extraction provider factories"
```

### Task 8: Enrich experiment metadata and persist local result artifacts

**Files:**
- Add: `backend/evals/extraction_quality/result_artifacts.py`
- Modify: `backend/evals/extraction_quality/experiment_configs.py`
- Modify: `backend/evals/extraction_quality/run.py`
- Modify: `backend/tests/test_extraction_runner.py`

The current runner prints a report and relies primarily on Logfire for durable
inspection. That is not enough for clean long-term comparison if we start
running many prompt variants or work across multiple worktrees.

- [ ] **Step 1: Add failing tests for richer metadata and local artifact export**

Extend `backend/tests/test_extraction_runner.py` so it proves:

1. experiment metadata includes prompt family, prompt version, and prompt sha
2. experiment metadata includes git branch and commit sha
3. successful runs write a local artifact to a timestamped result directory
4. artifact writing does not overwrite previous runs

Suggested tests:

```python
def test_experiment_metadata_includes_prompt_identity():
    ...

def test_write_report_artifact_creates_timestamped_json(tmp_path):
    ...
```

- [ ] **Step 2: Run the runner tests and confirm the new coverage fails**

Run:

```bash
cd backend && uv run pytest tests/test_extraction_runner.py -v
```

Expected:

- FAIL because metadata and local artifact writing are not implemented yet

- [ ] **Step 3: Extend the experiment config object and metadata helpers**

Implementation guidance:

- derive prompt metadata from the same configuration object used to build the
  extraction agent
- add helpers that capture git branch and commit sha at run time
- keep metadata generation centralized so the console report, Logfire metadata,
  and artifact output all share the same source of truth

Minimum metadata fields:

- `experiment`
- `dataset_name`
- `model_name`
- `provider`
- `thinking_mode`
- `prompt_family`
- `prompt_version`
- `prompt_sha`
- `git_branch`
- `git_commit_sha`

- [ ] **Step 4: Implement append-only local artifact export**

Create `backend/evals/extraction_quality/result_artifacts.py`.

Recommended output layout:

```text
backend/evals/extraction_quality/results/
  2026-04-01T16-20-00Z/
    gemini3_flash_default.json
    gemini3_flash_minimal_thinking.json
```

Each experiment artifact should record:

- timestamp
- dataset name
- experiment id
- model/provider summary
- prompt family, version, and sha
- git branch and commit sha
- repeat count and max concurrency
- aggregate metrics
- per-case expected and predicted todo counts
- trace id and span id when available

Implementation guidance:

- make the results directory append-only
- prefer JSON so artifacts stay diffable and easy to inspect
- keep artifact serialization separate from the CLI parsing logic
- if helpful, add `--output-dir` with the default pointing to the standard
  results path

- [ ] **Step 5: Re-run the runner tests and perform a manual smoke run**

Run:

```bash
cd backend && uv run pytest tests/test_extraction_runner.py -v
cd backend && .venv/bin/python evals/extraction_quality/run.py --experiment gemini3_flash_default
```

Expected:

- tests PASS
- the manual run writes a JSON artifact even if only one experiment is run
- the artifact metadata matches the console and Logfire metadata

- [ ] **Step 6: Commit the metadata and artifact slice**

```bash
git add backend/evals/extraction_quality/result_artifacts.py backend/evals/extraction_quality/experiment_configs.py backend/evals/extraction_quality/run.py backend/tests/test_extraction_runner.py
git commit -m "feat: persist extraction eval run artifacts"
```

### Task 9: Document worktree credentials and local run workflow

**Files:**
- Add: `backend/.env.example`
- Modify: `backend/evals/extraction_quality/README.md`

The current harness assumes the reader already understands that `backend/.env`
is gitignored, per-worktree, and required for provider discovery. That is too
easy to miss, especially once multiple worktrees exist.

- [ ] **Step 1: Add the example env file**

Create `backend/.env.example` documenting the variables relevant to this eval
suite.

Minimum contents:

```dotenv
GEMINI_API_KEY=
LOGFIRE_TOKEN=
MISTRAL_API_KEY=
```

Implementation guidance:

- keep secrets empty
- add brief comments explaining which variables are required now versus optional
- do not include provider keys that are not supported anywhere in the current
  harness

- [ ] **Step 2: Update the eval README with worktree and artifact guidance**

Document:

1. why `backend/.env` does not automatically appear in new worktrees
2. how to copy or symlink `.env` into a worktree
3. how `LOGFIRE_TOKEN` changes the observability experience
4. where local result artifacts are written
5. the recommended iteration loop:
   run one experiment after a prompt change, then rerun the full matrix only
   after the targeted run looks promising

- [ ] **Step 3: Manually verify the docs against the current branch workflow**

Run:

```bash
cd backend && .venv/bin/python evals/extraction_quality/run.py --list-experiments
```

Expected:

- the docs match the actual command names and file paths
- the env file guidance reflects the current worktree behavior accurately

- [ ] **Step 4: Commit the workflow docs**

```bash
git add backend/.env.example backend/evals/extraction_quality/README.md
git commit -m "docs: clarify extraction eval setup and workflow"
```

## Extended Validation Checklist

- [ ] extraction prompts live in repo-backed assets instead of inline extractor
      constants
- [ ] prompt metadata includes prompt family, version, path, and sha-derived
      identity
- [ ] the extraction agent uses `instructions` unless a specific
      `system_prompt` need remains
- [ ] provider-specific model construction is isolated from extraction
      orchestration
- [ ] Logfire metadata and local artifact metadata come from the same
      configuration source of truth
- [ ] the runner writes append-only local JSON artifacts for each experiment run
- [ ] run metadata includes git branch and commit sha
- [ ] `backend/.env.example` documents the credentials needed for this harness
- [ ] the README explains worktree-specific `.env` behavior and the recommended
      prompt-iteration loop

## Recommended Execution Order For The Follow-On Slice

1. Externalize the current extraction prompt and introduce prompt references.
2. Switch the extraction agent to prompt-registry-backed `instructions`.
3. Split provider-specific model construction out of `extract.py`.
4. Enrich experiment metadata and add local result artifact export.
5. Document `.env` handling, artifact locations, and the recommended rerun
   workflow.
