# Spec: Add Managed Modal/Outlines Extraction Family

## Source

- Shaping document: [020_shaping_qwen-constrained-evals.md](020_shaping_qwen-constrained-evals.md)
- This spec implements shaping `V3`.
- This spec builds directly on the merged DeepInfra baseline in [021_spec_restore-deepinfra-qwen-baseline.md](021_spec_restore-deepinfra-qwen-baseline.md).
- This spec replaces the unmerged local Modal draft that incorrectly reused the `021` number.

## Baseline

Today `origin/main` already contains the first two shaping slices. The extraction benchmark in [todo_extraction_bench_v1.yaml](../../../evals/benchmarks/todo_extraction_bench_v1.yaml) exposes the eight-entry DeepInfra comparison:

- `deepinfra-output-tool`
- `deepinfra-provider-json-schema`

across all four Qwen sizes:

- `Qwen/Qwen3.5-0.8B`
- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`

That merged baseline already made `implementation.family` part of benchmark identity. Resolution, config fingerprinting, and benchmark reports already use that field to keep the two DeepInfra families separate. The extraction layer already supports two structured paths:

- output-tool mode through `ExtractionResult`
- provider-native JSON schema through `NativeOutput(ExtractionResult, strict=True)`

What does not exist yet is the managed family from shaping `V3`:

- no Modal-backed benchmark entries
- no managed runtime transport override at benchmark launch time
- no managed session lease lifecycle in `evals/run.py`
- no warmup-outside-measurement guarantee
- no teardown guarantee for managed benchmark servers

## Target System

After this slice, the extraction benchmark compares all four Qwen sizes across three explicit families:

- `deepinfra-output-tool`
- `deepinfra-provider-json-schema`
- `modal-outlines`

The benchmark now contains `4 models x 3 families = 12` Qwen comparison entries. The existing eight DeepInfra entries remain unchanged. Four new managed entries are added:

- `modal_outlines_qwen35_0_8b`
- `modal_outlines_qwen35_2b`
- `modal_outlines_qwen35_4b`
- `modal_outlines_qwen35_9b`

Each managed entry:

- uses `provider: managed-openai`
- uses `implementation.family: modal-outlines`
- keeps the typed extraction contract returning `ExtractionResult` / `Todo`
- carries a stable `session` spec that describes the managed runtime shape
- is launched through a runtime-injected OpenAI-compatible endpoint rather than a static provider URL in benchmark config

The benchmark runner owns the managed lifecycle:

- group managed entries by stable session spec plus model
- open one managed lease for a group
- wait for readiness
- run a warmup request before measurement
- execute the benchmark entries through the warmed endpoint
- always tear the lease down on success and failure

The modal family is additive. This slice does not replace, rename, or reinterpret the merged DeepInfra comparison from `021`.

## Benchmark Entry Shape

Merged `021` already established `implementation.family` as the benchmark identity seam. This slice keeps that contract and adds `session` only for managed families.

Illustrative managed entry:

```yaml
- id: modal_outlines_qwen35_4b
  label: Qwen 3.5 4B / Modal Outlines
  config:
    provider: managed-openai
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    implementation:
      family: modal-outlines
    model_settings:
      temperature: 0
      max_tokens: 1024
    session:
      stack: sglang-outlines
      host: modal
      gpu: L40S
      context_window: 4096
```

Only managed entries use `session`. The eight merged DeepInfra entries remain as they are on `origin/main`.

## Managed Family Requirements

`modal-outlines` must:

- use a managed OpenAI-compatible transport that is injected at runtime
- use native JSON-schema structured output against the managed endpoint
- preserve the same `ExtractionResult` / `Todo` contract as the DeepInfra families
- use one stable benchmark-level family name: `modal-outlines`
- use one stable benchmark-level session spec per model/runtime shape
- use `temperature: 0` and `max_tokens: 1024` for all four managed entries

The stable `session` spec is part of benchmark config and must participate in run identity for managed entries. Runtime lease details are not part of persisted benchmark config:

- `base_url`
- `api_key`
- transport headers
- ephemeral session ids

Those values may be injected only at execution time.

## Structural Delta

Before this slice:

- the extraction benchmark has eight DeepInfra Qwen entries across two families
- managed Modal/Outlines entries do not exist
- the benchmark runner has no managed session lifecycle
- extraction launches cannot override provider transport per benchmark run

After this slice:

- the extraction benchmark has twelve Qwen entries across three families
- the four managed Modal/Outlines entries are benchmark-visible
- managed benchmark launches can inject a runtime OpenAI-compatible transport
- the benchmark runner can open, warm, reuse, and tear down managed leases safely

## Decisions

- Build on merged `021` instead of rewriting it.
- Keep `implementation.family` as the comparison identity seam.
- Add `session` only for managed families instead of introducing a second family field.
- Keep the Modal family additive: four new entries, not a rewrite of the eight DeepInfra entries.
- Keep managed `max_tokens: 1024` as a family-level contract for this slice rather than re-normalizing back to the DeepInfra `512` baseline.
- Treat benchmark visibility and managed lifecycle as separate blocking outcomes.

## Non-Goals

- No replay benchmark mirroring yet.
- No change to the eight DeepInfra entry ids or family names from `021`.
- No attempt to normalize quality across the three families.
- No multi-model shared lease across different model names.
- No persistent managed service outside the benchmark runtime.
- No benchmark CLI redesign for per-entry selection in this slice.

## Design And Implementation Constraints

- [todo_extraction_bench_v1.yaml](../../../evals/benchmarks/todo_extraction_bench_v1.yaml) remains the benchmark contract surface.
- `implementation.family` must continue to participate in benchmark resolution, config fingerprinting, and report identity.
- The new managed `session` spec must also participate in benchmark identity so materially different managed runtime shapes do not collapse into the same result stream.
- The extraction layer must support runtime transport overrides without changing the persisted benchmark config for the eight DeepInfra entries.
- The managed family must use native structured output against the runtime endpoint rather than the output-tool path.
- Warmup must happen before measured benchmark evaluation, not inside case timing.
- Teardown must run after successful completion and after failures.
- The implementation must not leave managed Modal benchmark servers running after the benchmark returns.
- Incorrect or incomplete extraction results remain valid benchmark outcomes. This slice is about infrastructure and comparison shape, not model quality.

## Acceptance Gate: The Extraction Benchmark Surfaces The Three-Family Qwen Comparison

Why this gate matters:
This slice is not real until the benchmark visibly contains the managed family as the third lane beside the two merged DeepInfra lanes.

Criteria:

- `benchmark show` contains all twelve Qwen comparison entries:
  - `deepinfra_qwen35_0_8b_output_tool`
  - `deepinfra_qwen35_2b_output_tool`
  - `deepinfra_qwen35_4b_output_tool`
  - `deepinfra_qwen35_9b_output_tool`
  - `deepinfra_qwen35_0_8b_provider_json_schema`
  - `deepinfra_qwen35_2b_provider_json_schema`
  - `deepinfra_qwen35_4b_provider_json_schema`
  - `deepinfra_qwen35_9b_provider_json_schema`
  - `modal_outlines_qwen35_0_8b`
  - `modal_outlines_qwen35_2b`
  - `modal_outlines_qwen35_4b`
  - `modal_outlines_qwen35_9b`
- Each managed entry reports:
  - `provider: managed-openai`
  - `config.implementation.family = "modal-outlines"`
  - a stable `session` block with `stack`, `host`, `gpu`, and `context_window`
- At least one managed canary run appears in benchmark reporting as `current` with:
  - `selected_run_id`
  - `selected_timestamp`
  - `total_case_count > 0`

Proof:

- Update the benchmark definition to include the four managed entries without changing the eight merged DeepInfra ids.
- Run:

```bash
cd backend && uv run python ../evals/cli.py benchmark show todo_extraction_bench_v1
```

- Run a managed canary through the benchmark path.
- Generate:

```bash
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json
```

- Verify from the show/report output that:
  - all twelve Qwen entries are present
  - the four managed entries report `provider: managed-openai`
  - the four managed entries report `config.implementation.family = "modal-outlines"`
  - at least one managed entry is `current` with non-zero case counts

Expected evidence:

- the exact `benchmark show` command used
- the exact managed canary command used
- the exact `benchmark report --json` command used
- extracted report assertions showing:
  - presence of the twelve Qwen entry ids
  - managed family metadata on the four managed entries
  - one `current` managed canary with non-zero case counts

## Acceptance Gate: Managed Modal Benchmark Runs Are Warm And Cleaned Up

Why this gate matters:
Shaping `V3` is not only about adding four config entries. The managed runtime must be safe to use for benchmarking and must not contaminate measurements with startup latency or leaked servers.

Criteria:

- Running the managed Modal entries through the benchmark path produces `current` benchmark results for all four managed entries with non-zero case counts.
- The benchmark runtime measures managed cases against a warmed endpoint, not a cold-start request.
- After a managed benchmark run completes or fails, no managed benchmark server remains running locally.

Proof:

- Add focused benchmark-runner acceptance tests that prove:
  - warmup happens before managed entry execution
  - teardown runs after success
  - teardown runs after failure
- Run the managed family through the benchmark path.
- Generate the benchmark JSON report and verify all four managed entries are `current` with non-zero case counts.
- After the run, check that no `modal run scripts/qwen_sglang_outlines_smoke.py --mode serve` process remains.

Expected evidence:

- the exact focused acceptance test command(s) used
- the exact managed benchmark command used
- the exact post-run process-check command used
- extracted output showing:
  - focused lifecycle acceptance tests passed
  - all four managed entries are `current` with non-zero case counts
  - no managed benchmark server process remains

## Supporting Verification

- targeted tests for benchmark definition parsing and managed `session` resolution
- targeted tests for managed transport injection into extraction launches
- targeted tests for managed launcher readiness parsing and termination behavior
- focused regression tests for benchmark report identity after adding the managed family
- `ty` and targeted `ruff` on touched files
