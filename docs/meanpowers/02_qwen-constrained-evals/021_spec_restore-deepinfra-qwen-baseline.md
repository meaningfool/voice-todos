# Spec: Establish DeepInfra Qwen Structured Comparison Baseline

## Source

- Work item: [020_shaping_qwen-constrained-evals.md](020_shaping_qwen-constrained-evals.md)
- This revised spec supersedes the earlier narrow draft saved at this path.
- Scope here is the first provider-local slice, combining the original shaping `V1` and `V2` without pulling in Modal/Outlines or replay.

## Baseline

Today the extraction benchmark only contains two DeepInfra Qwen entries in [todo_extraction_bench_v1.yaml](../../../evals/benchmarks/todo_extraction_bench_v1.yaml):

- `deepinfra_qwen35_9b_default`
- `deepinfra_qwen35_4b_structured_tuned`

The shaping already defined the intended two-family DeepInfra comparison. It describes the old family as the `current SDK-default structured path` and the `historical DeepInfra structured path`, and the new family as the explicit provider-side `response_format=json_schema` path in [020_shaping_qwen-constrained-evals.md](020_shaping_qwen-constrained-evals.md).

In this repo's current implementation, that old family is not unstructured. It is the `pydantic_ai` output-tool path. The extraction agent is built with `output_type=ExtractionResult` in [extract.py](../../../backend/app/extract.py), `pydantic_ai` defaults structured output to `tool` mode in [profiles/__init__.py](../../../backend/.venv/lib/python3.14/site-packages/pydantic_ai/profiles/__init__.py), and the OpenAI-compatible adapter only sends `response_format` when the output mode is `native` in [openai.py](../../../backend/.venv/lib/python3.14/site-packages/pydantic_ai/models/openai.py). To make the family names explicit about mechanism instead of chronology, this spec names the two families `deepinfra-output-tool` and `deepinfra-provider-json-schema`.

The benchmark runner is already benchmark-first. It resolves YAML entry configs and can synthesize experiment definitions from entry data in [experiment_configs.py](../../../backend/evals/extraction_quality/experiment_configs.py) and [run.py](../../../backend/evals/extraction_quality/run.py). However, benchmark/report identity currently has no explicit family field, so this slice must add that comparison axis to the benchmark contract.

## Target System

After this slice, the extraction benchmark compares all four target Qwen sizes across two explicit DeepInfra structured families:

- `Qwen/Qwen3.5-0.8B`
- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`

The two families are:

- `deepinfra-output-tool`
  - the current DeepInfra structured extraction path in this repo
  - implemented through `pydantic_ai` output-tool mode
  - preserves the existing typed extraction contract returning [ExtractionResult / Todo](../../../backend/app/models.py)
  - does not explicitly send provider-side `response_format=json_schema`

- `deepinfra-provider-json-schema`
  - the explicit DeepInfra provider-side JSON-schema path
  - explicitly sends `response_format=json_schema`
  - uses the same `ExtractionResult / Todo` schema contract as `deepinfra-output-tool`

Benchmark entry ids after this slice:

- `deepinfra_qwen35_0_8b_output_tool`
- `deepinfra_qwen35_2b_output_tool`
- `deepinfra_qwen35_4b_output_tool`
- `deepinfra_qwen35_9b_output_tool`
- `deepinfra_qwen35_0_8b_provider_json_schema`
- `deepinfra_qwen35_2b_provider_json_schema`
- `deepinfra_qwen35_4b_provider_json_schema`
- `deepinfra_qwen35_9b_provider_json_schema`

Shared baseline profile for all eight entries:

- `provider: deepinfra`
- `prompt_version: v1`
- `temperature: 0`
- `max_tokens: 512`

Shared baseline means the common extraction settings above. The provider-json-schema family also requires one family-specific compatibility setting:

- `extra_body.chat_template_kwargs.enable_thinking = false`

That setting is part of the provider-json-schema family contract because a live probe on 2026-05-11 showed that all four models accepted `response_format=json_schema`, but `0.8B` and `2B` could place the JSON into `reasoning_content` instead of normal `content` when thinking remained enabled.

## Benchmark Entry Shape

The benchmark contract becomes explicit about structured family:

```yaml
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
```

`implementation.family` is part of benchmark identity when present, not just display metadata. Ordinary benchmark entries that have no alternative implementation path can omit `implementation` entirely.

## Family Requirements

`deepinfra-output-tool` must:

- use the current structured extraction path described in shaping
- use `pydantic_ai` output-tool mode rather than provider-native JSON-schema mode
- preserve the existing typed extraction contract based on `ExtractionResult`
- use the shared baseline profile for all four models
- avoid model-specific exceptions, including the old `4B max_tokens=1024` override

`deepinfra-provider-json-schema` must:

- use the shared baseline profile for all four models
- explicitly request provider-side structure with `response_format=json_schema`
- derive that JSON schema from the same `ExtractionResult` / `Todo` contract used by the existing extraction path
- set `extra_body.chat_template_kwargs.enable_thinking = false`
- preserve the same typed return contract as `deepinfra-output-tool`

## Structural Delta

Before this slice:

- the benchmark exposes only two DeepInfra Qwen entries
- family identity is implicit and incomplete
- `2B` and `0.8B` are absent
- the DeepInfra comparison is not visible as a two-family benchmark lane

After this slice:

- the benchmark exposes eight DeepInfra Qwen entries
- all four Qwen sizes are present in both families
- family identity is explicit in benchmark config, resolution, and reporting
- the benchmark compares one DeepInfra structured path against another, not structured versus unstructured

## Decisions

- The first spec now covers the provider-local comparison baseline, not just the historical baseline restoration
- Use `deepinfra-output-tool` and `deepinfra-provider-json-schema` as explicit mechanism-level family names
- Add optional `implementation.family` to the benchmark contract
- Use one shared baseline profile across both families and all four models
- Make `response_format=json_schema` the defining behavior of the `deepinfra-provider-json-schema` family
- Make `enable_thinking=false` part of the `deepinfra-provider-json-schema` family contract
- Keep acceptance focused on benchmark report execution state, not extraction quality
- Keep legacy experiment-registry cleanup out of scope for this slice

## Non-Goals

- No Modal/SGLang/Outlines family yet
- No managed lifecycle work yet
- No replay benchmark mirroring yet
- No per-model rescue-tuning sweep
- No requirement that `0.8B` or `2B` become good extractors in this slice
- No legacy registry cleanup in this slice

## Design And Implementation Constraints

- The benchmark definition in [todo_extraction_bench_v1.yaml](../../../evals/benchmarks/todo_extraction_bench_v1.yaml) is the contract surface for this slice
- `implementation.family`, when present, must participate in benchmark resolution, query selection, config fingerprinting, and report identity so alternative implementations do not collapse into one result stream
- `deepinfra-output-tool` and `deepinfra-provider-json-schema` must both preserve the same [ExtractionResult / Todo](../../../backend/app/models.py) contract
- `deepinfra-output-tool` must preserve the current output-tool path rather than re-implementing it through the new JSON-schema request path
- `deepinfra-provider-json-schema` must explicitly exercise DeepInfra's provider-side `response_format=json_schema` behavior rather than only relabeling the current path
- `deepinfra-provider-json-schema` must disable thinking unless the implementation is updated to treat `reasoning_content` as a supported result channel
- The implementation must not silently keep the old `4B`-only `max_tokens=1024` exception
- The implementation should not rely on the current special-case DeepInfra model-name inference that only covers `4B` and `9B`, because this slice makes `0.8B` and `2B` first-class benchmark entries
- Incorrect cases and incomplete cases remain valid benchmark outcomes for this slice

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

## Supporting Verification

- targeted tests for benchmark definition parsing and `implementation.family` resolution
- targeted tests that report identity keeps `deepinfra-output-tool` and `deepinfra-provider-json-schema` separate
- targeted extraction tests proving that `deepinfra-provider-json-schema` constructs a DeepInfra request with explicit `response_format=json_schema`
- targeted extraction tests proving that `deepinfra-output-tool` still routes through the existing output-tool path
- optional follow-up note on whether the legacy experiment registry should be removed, generated, or remain supported
