# Establish DeepInfra Qwen Structured Comparison Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the extraction benchmark and extraction runtime so all four DeepInfra Qwen models run in two distinct structured-output families, report separately, and share one normalized baseline.

**Architecture:** Keep `evals/benchmarks/todo_extraction_bench_v1.yaml` as the public benchmark contract. Thread optional `implementation.family` through benchmark resolution and experiment metadata so the two DeepInfra families stay separate in report identity, then branch `app.extract` between PydanticAI output-tool mode and DeepInfra provider-native `response_format=json_schema` mode while preserving the same `ExtractionResult` schema.

**Tech Stack:** Python 3.14, pydantic, pydantic_ai, OpenAI-compatible DeepInfra chat API, YAML benchmark definitions, pytest, existing `uv`-driven eval CLI.

---

## File Map

- Modify `evals/benchmarks/todo_extraction_bench_v1.yaml`
  Replace the two historical DeepInfra entries with eight explicit family entries covering 0.8B, 2B, 4B, and 9B for both `deepinfra-output-tool` and `deepinfra-provider-json-schema`.

- Modify `evals/models.py`
  Add a resolved runtime field for the benchmark implementation family so downstream code can distinguish two entries that otherwise share provider, model, prompt, and model settings.

- Modify `evals/resolution.py`
  Parse `config.implementation.family`, pass it into synthetic experiment creation, and include it in selector fingerprinting so report identity does not collapse the two DeepInfra families together.

- Modify `backend/evals/extraction_quality/experiment_configs.py`
  Extend synthetic `ExperimentDefinition` creation to carry `implementation_family` without expanding the legacy direct-run registry in this slice.

- Modify `backend/evals/extraction_quality/run.py`
  Include `implementation_family` in benchmark-launched experiment metadata so benchmark report queries can distinguish the two families after execution.

- Modify `backend/app/extract.py`
  Add family-aware extraction configuration, keep `deepinfra-output-tool` on the current `output_type=ExtractionResult` path, and make `deepinfra-provider-json-schema` use `NativeOutput(ExtractionResult, strict=True)` with `enable_thinking=false`.

- Modify `backend/app/model_providers.py`
  Make all four target Qwen model names first-class DeepInfra models so 0.8B and 2B are not second-class inference exceptions.

- Modify `backend/tests/test_benchmark_definitions.py`
  Lock the eight-entry benchmark contract and resolved `implementation_family` behavior.

- Modify `backend/tests/test_benchmark_extraction_runner.py`
  Prove benchmark resolution passes the family-aware contract into the extraction runner.

- Modify `backend/tests/test_benchmark_report.py`
  Prove missing-entry expectations use the new ids and that report identity keeps output-tool and provider-json-schema runs separate.

- Modify `backend/tests/test_extract.py`
  Prove family-specific output-mode selection, forced `enable_thinking=false`, cache separation, and DeepInfra model inference.

- Modify `backend/tests/test_extraction_runner.py`
  Add synthetic experiment coverage for `implementation_family` and update any fake experiments that now need the field in metadata assembly.

- Modify `backend/tests/test_eval_experiment_metadata.py`
  Add a small guard that `config_fingerprint(...)` changes when `implementation_family` changes.

- Leave `backend/evals/incremental_extraction_quality/experiment_configs.py` unchanged
  Registry cleanup and replay mirroring are intentionally out of scope for this slice.

## Acceptance Gates From Spec

## Acceptance Gate: The Extraction Benchmark Reports The Two-Family DeepInfra Qwen Baseline

Why this gate matters:
This slice is about establishing the benchmark-visible DeepInfra comparison lane. If the report does not show both families across all four models as executed current entries, the slice is incomplete regardless of local config edits.

Criteria:

- The benchmark report contains exactly these DeepInfra Qwen entries:
  - `deepinfra_qwen35_0_8b_output_tool`
  - `deepinfra_qwen35_2b_output_tool`
  - `deepinfra_qwen35_4b_output_tool`
  - `deepinfra_qwen35_9b_output_tool`
  - `deepinfra_qwen35_0_8b_provider_json_schema`
  - `deepinfra_qwen35_2b_provider_json_schema`
  - `deepinfra_qwen35_4b_provider_json_schema`
  - `deepinfra_qwen35_9b_provider_json_schema`
- The benchmark report no longer contains:
  - `deepinfra_qwen35_9b_default`
  - `deepinfra_qwen35_4b_structured_tuned`
- Each `*_output_tool` entry reports `config.implementation.family = "deepinfra-output-tool"`
- Each `*_provider_json_schema` entry reports `config.implementation.family = "deepinfra-provider-json-schema"`
- Each restored entry has successful benchmark run state:
  - `status` is `current`
  - `selected_run_id` is present
  - `selected_timestamp` is present
- Incorrect cases or incomplete cases for any of those entries do not fail this gate

Proof:

- Update the extraction benchmark definition to the eight entry ids and explicit family configs
- Run the benchmark:

```bash
cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --all
```

- Generate the JSON report:

```bash
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json
```

- Verify from the report output that:
  - the eight DeepInfra entry ids are present
  - the two old entry ids are absent
  - each entry reports the expected `implementation.family`
  - each entry has `status: "current"`, `selected_run_id`, and `selected_timestamp`

Expected evidence:

- the exact `benchmark run` command used
- the exact `benchmark report --json` command used
- extracted JSON assertions or report snippets showing:
  - presence of the eight DeepInfra entry ids
  - absence of the two old entry ids
  - correct `implementation.family` per entry
  - populated `selected_run_id` and `selected_timestamp` for each entry

## Gate Execution

Run this only after all implementation tasks below pass their supporting verification.

1. Preflight live-run prerequisites. Do not weaken the gate if these are missing.

```bash
cd backend && uv run python - <<'PY'
from app.backend_env import read_backend_env_var
from app.logfire_setup import has_logfire_write_credentials

assert read_backend_env_var("DEEPINFRA_API_KEY"), "Missing DEEPINFRA_API_KEY"
assert has_logfire_write_credentials(), "Missing Logfire write credentials"
print("DeepInfra and Logfire credentials present")
PY
```

Expected: `DeepInfra and Logfire credentials present`

2. Run the benchmark exactly as specified.

```bash
cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --all
```

Expected: benchmark run completes without crashing the eight DeepInfra entries. Some cases may still be incorrect or incomplete.

3. Capture the JSON report to a local artifact for inspection.

```bash
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json > ../.context/021_benchmark_report.json
```

Expected: `.context/021_benchmark_report.json` exists and contains the full benchmark report.

4. Assert the gate criteria directly from the saved report.

```bash
cd backend && uv run python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("../.context/021_benchmark_report.json").read_text())
entries = {entry["entry_id"]: entry for entry in report["entries"]}
expected_families = {
    "deepinfra_qwen35_0_8b_output_tool": "deepinfra-output-tool",
    "deepinfra_qwen35_2b_output_tool": "deepinfra-output-tool",
    "deepinfra_qwen35_4b_output_tool": "deepinfra-output-tool",
    "deepinfra_qwen35_9b_output_tool": "deepinfra-output-tool",
    "deepinfra_qwen35_0_8b_provider_json_schema": "deepinfra-provider-json-schema",
    "deepinfra_qwen35_2b_provider_json_schema": "deepinfra-provider-json-schema",
    "deepinfra_qwen35_4b_provider_json_schema": "deepinfra-provider-json-schema",
    "deepinfra_qwen35_9b_provider_json_schema": "deepinfra-provider-json-schema",
}
removed_ids = {
    "deepinfra_qwen35_9b_default",
    "deepinfra_qwen35_4b_structured_tuned",
}

assert set(expected_families) <= set(entries), sorted(set(expected_families) - set(entries))
assert removed_ids.isdisjoint(entries), sorted(removed_ids & set(entries))

for entry_id, expected_family in expected_families.items():
    entry = entries[entry_id]
    assert entry["config"]["implementation"]["family"] == expected_family, entry_id
    assert entry["status"] == "current", entry_id
    assert entry["selected_run_id"], entry_id
    assert entry["selected_timestamp"], entry_id

print("Acceptance gate assertions passed")
PY
```

Expected: `Acceptance gate assertions passed`

5. Record the evidence in the final handoff.

- Include the exact benchmark run command used.
- Include the exact benchmark report command used.
- Quote or summarize the assertion output from step 4.

## Supporting Verification

Run these focused checks during implementation. They support the gate but do not replace it.

- Benchmark contract and resolution:

```bash
cd backend && uv run pytest tests/test_benchmark_definitions.py tests/test_benchmark_extraction_runner.py -q
```

- Report identity and metadata separation:

```bash
cd backend && uv run pytest tests/test_benchmark_report.py tests/test_extraction_runner.py tests/test_eval_experiment_metadata.py -q
```

- Extraction family selection and DeepInfra model wiring:

```bash
cd backend && uv run pytest tests/test_extract.py -q
```

- Final focused regression pass for this slice:

```bash
cd backend && uv run pytest tests/test_benchmark_definitions.py tests/test_benchmark_extraction_runner.py tests/test_benchmark_report.py tests/test_extract.py tests/test_extraction_runner.py tests/test_eval_experiment_metadata.py -q
```

## Tasks

### Task 1.1: Encode the eight-entry benchmark contract and resolve `implementation.family`

**Purpose:**
Replace the historical two-entry DeepInfra benchmark surface with the eight-entry two-family contract and make the resolved benchmark config carry the explicit family.

**Files:**
- Modify: `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Modify: `evals/models.py`
- Modify: `evals/resolution.py`
- Test: `backend/tests/test_benchmark_definitions.py`
- Test: `backend/tests/test_benchmark_extraction_runner.py`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Reports The Two-Family DeepInfra Qwen Baseline
- Supporting Verification: benchmark contract and resolution

- [ ] **Step 1: Write the failing benchmark-contract tests**

Add these tests to `backend/tests/test_benchmark_definitions.py` and `backend/tests/test_benchmark_extraction_runner.py`:

```python
def test_deepinfra_entries_use_explicit_families_and_shared_baseline():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
    deepinfra_entries = {
        entry.id: entry
        for entry in benchmark.entries
        if entry.config["provider"] == "deepinfra"
    }

    assert set(deepinfra_entries) == {
        "deepinfra_qwen35_0_8b_output_tool",
        "deepinfra_qwen35_2b_output_tool",
        "deepinfra_qwen35_4b_output_tool",
        "deepinfra_qwen35_9b_output_tool",
        "deepinfra_qwen35_0_8b_provider_json_schema",
        "deepinfra_qwen35_2b_provider_json_schema",
        "deepinfra_qwen35_4b_provider_json_schema",
        "deepinfra_qwen35_9b_provider_json_schema",
    }
    assert "deepinfra_qwen35_9b_default" not in deepinfra_entries
    assert "deepinfra_qwen35_4b_structured_tuned" not in deepinfra_entries


def test_resolve_entry_config_surfaces_implementation_family():
    benchmark = load_benchmark_definition(BENCHMARK_DEFINITION)
    entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_provider_json_schema"
    )

    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == "deepinfra"
    assert resolved.model_name == "Qwen/Qwen3.5-4B"
    assert resolved.prompt_version == "v1"
    assert resolved.implementation_family == "deepinfra-provider-json-schema"
    assert resolved.model_settings == {
        "temperature": 0,
        "max_tokens": 512,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }
```

- [ ] **Step 2: Run the focused tests to confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_benchmark_definitions.py tests/test_benchmark_extraction_runner.py -q
```

Expected: FAIL because the benchmark YAML still contains the old DeepInfra ids and `ResolvedEntryConfig` does not expose `implementation_family`.

- [ ] **Step 3: Implement the minimal benchmark-contract changes**

Update the benchmark YAML to exactly these DeepInfra entries and add the resolved family field:

```yaml
- id: deepinfra_qwen35_0_8b_output_tool
  label: Qwen 3.5 0.8B / DeepInfra output tool
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-0.8B
    prompt_version: v1
    implementation:
      family: deepinfra-output-tool
    model_settings:
      temperature: 0
      max_tokens: 512
- id: deepinfra_qwen35_2b_output_tool
  label: Qwen 3.5 2B / DeepInfra output tool
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-2B
    prompt_version: v1
    implementation:
      family: deepinfra-output-tool
    model_settings:
      temperature: 0
      max_tokens: 512
- id: deepinfra_qwen35_4b_output_tool
  label: Qwen 3.5 4B / DeepInfra output tool
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    implementation:
      family: deepinfra-output-tool
    model_settings:
      temperature: 0
      max_tokens: 512
- id: deepinfra_qwen35_9b_output_tool
  label: Qwen 3.5 9B / DeepInfra output tool
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-9B
    prompt_version: v1
    implementation:
      family: deepinfra-output-tool
    model_settings:
      temperature: 0
      max_tokens: 512
- id: deepinfra_qwen35_0_8b_provider_json_schema
  label: Qwen 3.5 0.8B / DeepInfra provider json_schema
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-0.8B
    prompt_version: v1
    implementation:
      family: deepinfra-provider-json-schema
    model_settings:
      temperature: 0
      max_tokens: 512
      extra_body:
        chat_template_kwargs:
          enable_thinking: false
- id: deepinfra_qwen35_2b_provider_json_schema
  label: Qwen 3.5 2B / DeepInfra provider json_schema
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-2B
    prompt_version: v1
    implementation:
      family: deepinfra-provider-json-schema
    model_settings:
      temperature: 0
      max_tokens: 512
      extra_body:
        chat_template_kwargs:
          enable_thinking: false
- id: deepinfra_qwen35_4b_provider_json_schema
  label: Qwen 3.5 4B / DeepInfra provider json_schema
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    implementation:
      family: deepinfra-provider-json-schema
    model_settings:
      temperature: 0
      max_tokens: 512
      extra_body:
        chat_template_kwargs:
          enable_thinking: false
- id: deepinfra_qwen35_9b_provider_json_schema
  label: Qwen 3.5 9B / DeepInfra provider json_schema
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-9B
    prompt_version: v1
    implementation:
      family: deepinfra-provider-json-schema
    model_settings:
      temperature: 0
      max_tokens: 512
      extra_body:
        chat_template_kwargs:
          enable_thinking: false
```

```python
class ResolvedEntryConfig(BaseModel):
    suite: str
    dataset_family: str
    provider: str
    model_name: str
    prompt_version: str
    implementation_family: str | None = None
    model_settings: dict = Field(default_factory=dict)
```

```python
def resolve_entry_config(
    *,
    benchmark: BenchmarkDefinition,
    entry: BenchmarkEntry,
) -> ResolvedEntryConfig:
    implementation = entry.config.get("implementation", {})

    return ResolvedEntryConfig(
        suite=(
            "incremental_extraction_quality"
            if benchmark.dataset_family == "replay"
            else "extraction_quality"
        ),
        dataset_family=benchmark.dataset_family,
        provider=entry.config["provider"],
        model_name=entry.config["model"],
        prompt_version=entry.config["prompt_version"],
        implementation_family=implementation.get("family"),
        model_settings=entry.config.get("model_settings", {}),
    )
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_benchmark_definitions.py tests/test_benchmark_extraction_runner.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evals/benchmarks/todo_extraction_bench_v1.yaml evals/models.py evals/resolution.py backend/tests/test_benchmark_definitions.py backend/tests/test_benchmark_extraction_runner.py
git commit -m "feat: define explicit deepinfra benchmark families"
```

### Task 1.2: Keep benchmark identity and synthetic DeepInfra experiments family-aware

**Purpose:**
Make the benchmark runner and report treat `deepinfra-output-tool` and `deepinfra-provider-json-schema` as distinct execution lanes even when provider, model, prompt, and baseline params otherwise match.

**Files:**
- Modify: `evals/resolution.py`
- Modify: `backend/evals/extraction_quality/experiment_configs.py`
- Modify: `backend/evals/extraction_quality/run.py`
- Test: `backend/tests/test_benchmark_report.py`
- Test: `backend/tests/test_extraction_runner.py`
- Test: `backend/tests/test_eval_experiment_metadata.py`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Reports The Two-Family DeepInfra Qwen Baseline
- Supporting Verification: report identity and metadata separation

- [ ] **Step 1: Write the failing identity and report-separation tests**

Add these tests:

```python
def test_build_entry_query_selector_changes_when_implementation_family_changes():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    output_entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_output_tool"
    )
    provider_entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_provider_json_schema"
    )

    output_selector = build_entry_query_selector(benchmark=benchmark, entry=output_entry)
    provider_selector = build_entry_query_selector(benchmark=benchmark, entry=provider_entry)

    assert output_selector.model_name == provider_selector.model_name == "Qwen/Qwen3.5-4B"
    assert output_selector.config_fingerprint != provider_selector.config_fingerprint


def test_benchmark_report_keeps_deepinfra_families_separate():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    output_entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_output_tool"
    )
    provider_entry = next(
        entry
        for entry in benchmark.entries
        if entry.id == "deepinfra_qwen35_4b_provider_json_schema"
    )
    output_selector = build_entry_query_selector(benchmark=benchmark, entry=output_entry)
    provider_selector = build_entry_query_selector(benchmark=benchmark, entry=provider_entry)

    report = build_benchmark_report(
        benchmark_id="todo_extraction_bench_v1",
        query_client=FakeBenchmarkQueryClient(
            rows=[
                _history_row(
                    output_selector,
                    run_id="run-output-tool",
                    started_at="2026-05-11T09:00:00+00:00",
                    trace_id="trace-output-tool",
                ),
                _history_row(
                    provider_selector,
                    run_id="run-provider-json-schema",
                    started_at="2026-05-11T09:01:00+00:00",
                    trace_id="trace-provider-json-schema",
                ),
            ]
        ),
    )

    entries = {row.entry_id: row for row in report.entries}
    assert entries["deepinfra_qwen35_4b_output_tool"].selected_run_id == "run-output-tool"
    assert (
        entries["deepinfra_qwen35_4b_provider_json_schema"].selected_run_id
        == "run-provider-json-schema"
    )
```

And add this metadata guard:

```python
def test_config_fingerprint_changes_when_implementation_family_changes():
    first = config_fingerprint({"model": "Qwen/Qwen3.5-4B", "implementation_family": "deepinfra-output-tool"})
    second = config_fingerprint({"model": "Qwen/Qwen3.5-4B", "implementation_family": "deepinfra-provider-json-schema"})

    assert first != second
```

- [ ] **Step 2: Run the focused tests to confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_benchmark_report.py tests/test_extraction_runner.py tests/test_eval_experiment_metadata.py -q
```

Expected: FAIL because selector fingerprinting still ignores `implementation_family`, benchmark-launched synthetic experiments do not carry the field, and report expectations still point at the old DeepInfra ids.

- [ ] **Step 3: Implement the minimal identity and runner changes**

Carry `implementation_family` through synthetic experiment creation and metadata:

```python
@dataclass(frozen=True)
class ExperimentDefinition:
    name: str
    extraction_config: ExtractionConfig
    provider: str
    thinking_mode: str
    implementation_family: str | None = None


def experiment_definition_from_entry_config(
    *,
    experiment_name_hint: str,
    provider: str,
    model_name: str,
    prompt_version: str,
    implementation_family: str | None = None,
    model_settings: dict[str, object] | None = None,
) -> ExperimentDefinition:
    legacy = EXPERIMENTS.get(experiment_name_hint)
    if legacy is not None:
        same_config = (
            legacy.provider == provider
            and legacy.extraction_config.model_name == model_name
            and legacy.extraction_config.prompt_version == prompt_version
            and legacy.extraction_config.model_settings == (model_settings or {})
            and legacy.implementation_family == implementation_family
        )
        if same_config:
            return legacy

    resolved_model_settings = dict(model_settings or {})
    extraction_provider = None if provider == "google-gla" else provider
    thinking_mode = "provider_default" if not resolved_model_settings else "custom"

    return ExperimentDefinition(
        name=experiment_name_hint,
        extraction_config=ExtractionConfig(
            model_name=model_name,
            provider=extraction_provider,
            model_settings=resolved_model_settings,
            prompt_version=prompt_version,
            implementation_family=implementation_family,
        ),
        provider=provider,
        thinking_mode=thinking_mode,
        implementation_family=implementation_family,
    )
```

```python
experiment = experiment_definition_from_entry_config(
    experiment_name_hint=entry.id,
    provider=resolved.provider,
    model_name=resolved.model_name,
    prompt_version=resolved.prompt_version,
    implementation_family=resolved.implementation_family,
    model_settings=resolved.model_settings,
)

config_fingerprint(
    {
        "provider": experiment.provider,
        "implementation_family": experiment.implementation_family,
        "thinking_mode": experiment.thinking_mode,
        "model_settings": experiment.extraction_config.model_settings,
        "prompt_version": experiment.extraction_config.prompt_version,
        "repeat": benchmark.repeat,
        "task_retries": benchmark.task_retries,
        "max_concurrency": benchmark.max_concurrency,
    }
)
```

```python
full_config={
    "provider": experiment.provider,
    "implementation_family": experiment.implementation_family,
    "thinking_mode": experiment.thinking_mode,
    "model_settings": experiment.extraction_config.model_settings,
    "prompt_version": experiment.extraction_config.prompt_version,
    "repeat": repeat,
    "task_retries": task_retries,
    "max_concurrency": max_concurrency,
}
```

Also update any fake `SimpleNamespace(...)` experiments in `backend/tests/test_extraction_runner.py` so they include `implementation_family=None`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_benchmark_report.py tests/test_extraction_runner.py tests/test_eval_experiment_metadata.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evals/resolution.py backend/evals/extraction_quality/experiment_configs.py backend/evals/extraction_quality/run.py backend/tests/test_benchmark_report.py backend/tests/test_extraction_runner.py backend/tests/test_eval_experiment_metadata.py
git commit -m "feat: separate deepinfra benchmark family identity"
```

### Task 1.3: Implement family-specific DeepInfra extraction behavior

**Purpose:**
Keep the current DeepInfra path on PydanticAI output-tool mode, add the provider-native JSON-schema family, force `enable_thinking=false` for that family, and make all four Qwen sizes first-class DeepInfra models.

**Files:**
- Modify: `backend/app/extract.py`
- Modify: `backend/app/model_providers.py`
- Test: `backend/tests/test_extract.py`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Reports The Two-Family DeepInfra Qwen Baseline
- Supporting Verification: extraction family selection and DeepInfra model wiring

- [ ] **Step 1: Write the failing extraction-family tests**

Add these tests to `backend/tests/test_extract.py`:

```python
from pydantic_ai import NativeOutput


def test_build_extraction_agent_keeps_output_tool_family():
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract.build_model", return_value=fake_model),
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        build_extraction_agent(
            ExtractionConfig(
                model_name="Qwen/Qwen3.5-4B",
                provider="deepinfra",
                implementation_family="deepinfra-output-tool",
                model_settings={"temperature": 0, "max_tokens": 512},
            )
        )

    assert mock_agent.call_args.kwargs["output_type"] is ExtractionResult


def test_build_extraction_agent_uses_native_output_for_provider_json_schema():
    fake_model = object()
    fake_agent = object()

    with (
        patch("app.extract.build_model", return_value=fake_model),
        patch("app.extract.Agent", return_value=fake_agent) as mock_agent,
    ):
        build_extraction_agent(
            ExtractionConfig(
                model_name="Qwen/Qwen3.5-4B",
                provider="deepinfra",
                implementation_family="deepinfra-provider-json-schema",
                model_settings={"temperature": 0, "max_tokens": 512},
            )
        )

    output_type = mock_agent.call_args.kwargs["output_type"]
    assert isinstance(output_type, NativeOutput)
    assert output_type.outputs is ExtractionResult
    assert output_type.strict is True
    assert (
        mock_agent.call_args.kwargs["model_settings"]["extra_body"]["chat_template_kwargs"]["enable_thinking"]
        is False
    )


def test_config_cache_key_changes_when_implementation_family_changes():
    prompt_ref = _extract_mod.get_extraction_prompt_ref()
    output_tool_key = _extract_mod._config_cache_key(
        ExtractionConfig(
            model_name="Qwen/Qwen3.5-4B",
            provider="deepinfra",
            implementation_family="deepinfra-output-tool",
            model_settings={"temperature": 0, "max_tokens": 512},
        ),
        prompt_sha256=prompt_ref.sha256,
    )
    provider_json_key = _extract_mod._config_cache_key(
        ExtractionConfig(
            model_name="Qwen/Qwen3.5-4B",
            provider="deepinfra",
            implementation_family="deepinfra-provider-json-schema",
            model_settings={"temperature": 0, "max_tokens": 512},
        ),
        prompt_sha256=prompt_ref.sha256,
    )

    assert output_tool_key != provider_json_key
```

Also extend the DeepInfra model inference test with:

```python
@pytest.mark.parametrize(
    "model_name",
    [
        "Qwen/Qwen3.5-0.8B",
        "Qwen/Qwen3.5-2B",
        "Qwen/Qwen3.5-4B",
        "Qwen/Qwen3.5-9B",
    ],
)
def test_build_model_infers_deepinfra_for_all_qwen35_sizes(model_name):
    ...
```

- [ ] **Step 2: Run the focused tests to confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_extract.py -q
```

Expected: FAIL because `ExtractionConfig` has no family field, `build_extraction_agent(...)` always uses `ExtractionResult`, the cache key ignores family, and 0.8B/2B are not first-class DeepInfra inference names.

- [ ] **Step 3: Implement the minimal extraction-family changes**

Add family-aware output selection and forced thinking disablement:

```python
from pydantic_ai import Agent, NativeOutput


@dataclass(frozen=True)
class ExtractionConfig:
    model_name: str = "gemini-3-flash-preview"
    provider: str | None = None
    model_settings: dict[str, Any] | None = None
    prompt_family: str = "todo_extraction"
    prompt_version: str = "v1"
    implementation_family: str | None = None
```

```python
def _resolve_model_settings(config: ExtractionConfig) -> dict[str, Any]:
    resolved = (
        deepcopy(config.model_settings)
        if config.model_settings is not None
        else deepcopy(_DEFAULT_MODEL_SETTINGS)
    )

    if config.implementation_family == "deepinfra-provider-json-schema":
        extra_body = resolved.setdefault("extra_body", {})
        chat_template_kwargs = extra_body.setdefault("chat_template_kwargs", {})
        chat_template_kwargs["enable_thinking"] = False

    return resolved


def _resolve_output_type(config: ExtractionConfig) -> object:
    if config.implementation_family == "deepinfra-provider-json-schema":
        return NativeOutput(ExtractionResult, strict=True)
    return ExtractionResult
```

```python
def _config_cache_key(
    config: ExtractionConfig,
    *,
    prompt_sha256: str,
) -> tuple[Any, ...]:
    return (
        config.model_name,
        config.provider,
        config.prompt_family,
        config.prompt_version,
        config.implementation_family,
        prompt_sha256,
        _freeze_for_cache(_resolve_model_settings(config)),
    )
```

```python
def build_extraction_agent(
    config: ExtractionConfig,
    *,
    prompt_ref: PromptRef | None = None,
) -> Agent[None, ExtractionResult]:
    resolved_prompt_ref = prompt_ref or get_extraction_prompt_ref(config)
    resolved_model_settings = _resolve_model_settings(config)
    agent = Agent(
        _build_model(config),
        output_type=_resolve_output_type(config),
        instructions=resolved_prompt_ref.content,
        model_settings=resolved_model_settings,
    )
    return cast("Agent[None, ExtractionResult]", agent)
```

And make all four Qwen sizes first-class DeepInfra models:

```python
_DEEPINFRA_MODEL_NAMES = frozenset(
    {
        "Qwen/Qwen3.5-0.8B",
        "Qwen/Qwen3.5-2B",
        "Qwen/Qwen3.5-4B",
        "Qwen/Qwen3.5-9B",
    }
)
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_extract.py -q
```

Expected: PASS

- [ ] **Step 5: Run the slice-level focused regression pass**

Run:

```bash
cd backend && uv run pytest tests/test_benchmark_definitions.py tests/test_benchmark_extraction_runner.py tests/test_benchmark_report.py tests/test_extract.py tests/test_extraction_runner.py tests/test_eval_experiment_metadata.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/extract.py backend/app/model_providers.py backend/tests/test_extract.py
git commit -m "feat: add deepinfra provider json schema extraction mode"
```

## Checkpoint

Do not start the Modal/SGLang/Outlines slice or replay mirroring until all of the following are true:

- all three implementation tasks above are complete
- the focused regression pass in Task 1.3 passes
- the full acceptance gate procedure in `Gate Execution` passes with live DeepInfra runs
- the final handoff includes the exact benchmark commands and the saved report assertion result

REQUIRED HANDOFF: superpowers:executing-plans

OPTIONAL HANDOFF: superpowers:subagent-driven-development
