# Shaping: Qwen Constrained Evals

## Source

- Inbox item: `INB-0002_qwen-constrained-evals.md`
- Current phase: Complete
- Status: Shaping complete; final slices selected; ready for `meanpowers:write-spec`

## Compressed Problem

**Problem statement:**  
How might we compare structured Qwen todo-extraction paths across DeepInfra and a managed Outlines stack for `0.8B`, `2B`, `4B`, and `9B`?

## Context Log

| ID | Point | Type | Object | Importance | Status | Notes |
|---|---|---|---|---|---|---|
| CL1 | CHANGED: The current benchmark matrix only covers DeepInfra `Qwen/Qwen3.5-9B` and tuned `Qwen/Qwen3.5-4B`; `Qwen/Qwen3.5-2B` and `Qwen/Qwen3.5-0.8B` are currently out after failing the structured extraction path. | expectation | shape | high | active | Baseline from the current benchmark files and the April 7 smoke-test note. |
| CL2 | CHANGED: The durable goal is to compare structured extraction paths for smaller Qwen models and see whether a different structured-output mechanism makes them reliable enough for todo extraction. | expectation | shape | high | active | The key comparison is no longer plain text versus structured output, but one structured path versus another. |
| CL3 | CHANGED: The earlier broad provider/product comparison across DeepInfra, Doubleword, open-source structured outputs, and gated `.txt` `dotjson` is no longer the active framing. | uncertainty | shape | high | superseded | Kept as history from the intake; the shape space is now narrower. |
| CL4 | CHANGED: Paid or gated constrained-generation paths are out of scope for this item; the work should use what is available now. | constraint | shape | high | active | This supersedes the earlier “cheaper before paid/gated” preference. |
| CL5 | CHANGED: Terminology cleanup only matters for terms that stay in scope, especially Outlines, constrained generation, `response_format`, and the model/provider names used in the eval matrix. | risk | shape | low | active | `.txt` / `dotjson` terminology no longer needs to drive the work unless it still appears in project docs that matter here. |
| CL6 | CHANGED: New experiments should extend the existing shared extraction and replay benchmark registries rather than introduce a separate runner. | constraint | shape | high | active | This could become a requirement if you want it stated as finished-system behavior. |
| CL7 | CHANGED: Modal is now the proven candidate host for self-served Outlines runs, though it is not yet a hard requirement of the final shape. | uncertainty | shape | low | active | The executed B1 spike proved the path on Modal, but the shaping still treats hosting choice as replaceable if needed. |
| CL8 | CHANGED: A formal reliability threshold is not required for this item; the user will decide qualitatively whether a model should stay in the matrix. | other | meta | high | active | This replaces the earlier threshold requirement candidate. |
| CL9 | CHANGED: The active comparison target is a four-model matrix (`0.8B`, `2B`, `4B`, `9B`) across three structured extraction families: the current DeepInfra structured path, a more explicit DeepInfra JSON-schema path, and a managed Modal/SGLang/Outlines path. | expectation | shape | high | active | This replaces the earlier with/without-Outlines framing. |
| CL10 | CHANGED: The earlier assumption that provider or host may vary by model or path is no longer the active framing. | uncertainty | shape | low | superseded | Replaced by the decision to remove DeepInfra from the target matrix and contrast fully remote-hosted shapes. |
| CL11 | CHANGED: For this item, “hosted” means a remote deployment we run ourselves, such as Modal, not a vendor-hosted API. | expectation | shape | high | active | Confirmed by the latest user feedback. |
| CL12 | CHANGED: Deployment topology, benchmark integration pattern, and schema-variant choices should be treated as sub-decisions under a top-level shape, not as independent top-level shapes themselves. | other | meta | high | active | This narrows the option taxonomy after the earlier A/B/C vs D/E/F/G confusion. |
| CL13 | CHANGED: A vendor-hosted API with Outlines-style constrained generation does not currently appear to cover the four-model breadth needed for this item; a partial exception may exist for a single Doubleword model, but that is insufficient for the target matrix. | constraint | shape | high | active | Based on the latest user guidance and prior search context. |
| CL14 | CHANGED: DeepInfra stays in the comparison matrix as a preserved structured baseline rather than being replaced outright. | expectation | shape | high | active | The active comparison now includes two DeepInfra structured families plus one managed Modal family. |
| CL15 | CHANGED: `B1`/`B2`/`B3` are no longer the right top-level shapes; they are stack-level variants or components under a benchmark-orchestration shape. | other | meta | high | active | The top-level problem is now how the benchmark system manages remote model sessions, not just which serving stack exists. |
| CL16 | CHANGED: The current benchmark runner is entry-oriented, but the desired server lifecycle for the managed Modal family is model-oriented. | constraint | shape | high | active | `run_benchmark(...)` launches entries one by one, while the managed Qwen path should start one model server and reuse it for all managed structured entries for that model. |
| CL17 | CHANGED: A single managed SGLang endpoint can serve all structured extraction requests for one model under the Modal/Outlines family, so server count should remain per-model for that family. | expectation | shape | high | active | The executed B1 spike proved that one server can handle the structured extraction workload shape for a model. |
| CL18 | CHANGED: Because the managed Modal path exists only for evals, startup and warmup should happen outside the measured request window, and teardown should happen automatically after grouped entries finish. | constraint | shape | high | active | This keeps benchmark latency measurements focused on warm inference while preventing idle GPU servers from lingering after the run. |
| CL19 | CHANGED: Extraction and replay are separate benchmark definitions, but the first slice should focus on extraction only. | expectation | shape | high | active | The new comparison family count already expands the matrix significantly; replay can follow once extraction comparisons are understood. |
| CL20 | CHANGED: Because the managed path is eval-only and GPU-backed, the default operational stance should be one live managed Qwen server at a time. | preference | shape | high | active | This minimizes accidental spend and makes teardown easier to reason about. |
| CL21 | CHANGED: Warmup should cover the structured extraction request shape that will be benchmarked on the managed Modal path before measured evaluation begins for a model. | constraint | shape | high | active | The goal is to measure warm structured inference, not cold-start behavior. |
| CL22 | CHANGED: The current `extract_todos(...)` path is already structured-output oriented, so the key seam is not “unconstrained versus constrained”; it is how many structured-output families we compare and how we inject them. | constraint | shape | high | active | The shape should preserve structured extraction as the comparison contract rather than introducing a plain-text baseline. |
| CL23 | CHANGED: The DeepInfra baseline may itself have at least two structured-output variants: the current SDK default structured path and an explicit provider-side `response_format=json_schema` path. | uncertainty | shape | high | active | Clarifying whether the current DeepInfra path is tool-structured versus provider-native JSON-schema changes the comparison matrix and likely adds a second DeepInfra family. |
| CL24 | CHANGED: Re-establishing `0.8B` and `2B` on DeepInfra is part of the comparison scope because they were previously discarded for structured-path failures rather than auth or routing failures. | expectation | shape | high | active | The follow-up comparison should test whether alternative structured paths recover these smaller models. |

## Requirements

| ID | Requirement | Status | Notes |
|---|---|---|---|
| R0 | CHANGED: The first delivered eval matrix compares Qwen `0.8B`, `2B`, `4B`, and `9B` on the extraction benchmark across three structured extraction families: current DeepInfra structured baseline, explicit DeepInfra JSON-schema path, and managed Modal/SGLang/Outlines. | Core goal | This captures the revised comparison contract and keeps the first slice limited to extraction. |
| R2 | CHANGED: The new experiments extend the existing shared extraction and replay benchmark registries instead of introducing a separate runner. | Must-have | Confirmed from the recent requirements clarification. |
| R3 | CHANGED: The target execution path supports both provider-backed structured runs and managed remote API-backed structured runs within the same benchmark framework. | Must-have | The comparison contract now depends on running both DeepInfra families and the managed Modal family side by side. |
| R4 | CHANGED: The final shape includes at least one remote-hosted stack we control in addition to the preserved DeepInfra baseline. | Must-have | The comparison is no longer framed as a full replacement of DeepInfra in the first slice. |
| R5 | CHANGED: Managed Qwen benchmark measurements begin only after the remote endpoint for that model is ready and warm. | Must-have | Startup, model loading, and warmup are intentionally outside the measured request window. |
| R6 | CHANGED: Any managed Qwen servers started by a benchmark run are automatically torn down after their grouped entries finish, including failure paths. | Must-have | The eval path must not leave remote GPU servers running after benchmark execution. |

## Shapes

| ID | Shape | Summary | Status |
|---|---|---|---|
| S0 | CHANGED: Benchmark-integrated structured Qwen extraction comparison lane | Extend the extraction benchmark with Qwen `0.8B`, `2B`, `4B`, and `9B` entries across three structured extraction families: current DeepInfra structured path, explicit DeepInfra JSON-schema path, and managed Modal/SGLang/Outlines. | Leading candidate |
| S0.ALT1 | CHANGED: vLLM + Outlines serving stack | Keep the old `B3` idea only as a fallback stack alternative under `S0`, not as a peer top-level shape. | Fallback component |

### Shape `S0`

| ID | Component | Flag | Notes |
|---|---|:---:|---|
| S0.1 | CHANGED: Benchmark entry families are explicit |  | The extraction benchmark can represent `deepinfra-current`, `deepinfra-json-schema`, and `modal-outlines` as separate comparison families. |
| S0.2 | CHANGED: `deepinfra-current` extraction canary exists |  | One anchor-model extraction entry proves the historical DeepInfra structured path is represented explicitly in the new comparison shape. |
| S0.3 | CHANGED: `deepinfra-current` extraction family is complete for all 4 models |  | The historical DeepInfra structured baseline is restored for `0.8B`, `2B`, `4B`, and `9B` on extraction. |
| S0.4 | CHANGED: `deepinfra-json-schema` extraction canary exists | WARNING | One anchor-model extraction entry proves DeepInfra's explicit provider-side `response_format=json_schema` path works in the benchmark. |
| S0.5 | CHANGED: `deepinfra-json-schema` extraction family is complete for all 4 models | WARNING | The explicit DeepInfra JSON-schema family is present for `0.8B`, `2B`, `4B`, and `9B` on extraction. |
| S0.6 | CHANGED: `modal-outlines` extraction canary exists | WARNING | One anchor-model extraction entry proves the managed Modal/SGLang/Outlines structured family works end to end in the benchmark. |
| S0.7 | CHANGED: `modal-outlines` extraction family is complete for all 4 models | WARNING | The managed Modal/SGLang/Outlines family is present for `0.8B`, `2B`, `4B`, and `9B` on extraction. |
| S0.8 | CHANGED: Managed extraction lifecycle is safe and measurable | WARNING | Managed runs warm before timing starts, keep one live server by default, and always tear down after grouped benchmark work completes. |
| S0.9 | CHANGED: Replay mirrors the confirmed extraction comparison |  | The replay benchmark gets the same family structure after the extraction comparison is established. |

## Selected Shape

**Selected option:**  
`S0` Benchmark-integrated structured Qwen extraction comparison lane

**Why this shape:**  
It preserves the current DeepInfra structured baseline, adds a second DeepInfra structured family that uses explicit provider-native JSON schema, and introduces one managed Modal/SGLang/Outlines family inside the same benchmark framework. That keeps the comparison contract structured-to-structured instead of mixing in an unconstrained baseline that would not be apples-to-apples.

**Key tradeoffs:**

- The first meaningful comparison is extraction only, with replay deferred until the extraction comparison is understood.
- The managed Modal family adds server lifecycle complexity, but only for the family that actually needs it.
- The current DeepInfra path remains visible as a historical baseline rather than being silently replaced.

**Rejected options:**

- Plain unconstrained Modal runs as a headline comparison contract, because they do not compare structured extraction paths fairly.
- A separate Qwen-only runner, because the work should extend the existing benchmark framework instead.
- Full replay inclusion in the first slice, because it would double the matrix before the extraction comparison is understood.

## Derived Actor Journeys

Derived actor journeys do not apply cleanly here. This shape is mainly benchmark and orchestration infrastructure rather than a user-facing workflow change.

## Lifecycle Clarification

1. One benchmark invocation still targets one benchmark definition, and the first slice should target extraction rather than extraction plus replay.
2. Ordinary vendor-backed entries continue to run through the current path.
3. Qwen entries in that benchmark are partitioned by structured family.
4. DeepInfra-family entries continue to run without managed server lifecycle.
5. Managed Modal-family entries are partitioned into per-model groups based on the benchmark entry configs.
6. For the first managed model group:
   - start one remote SGLang session
   - wait for endpoint readiness
   - run structured warmup requests outside the measured benchmark window
7. Execute the benchmark entries for that model against the warmed endpoint, preserving separate experiment identities for each structured family entry.
8. Tear the server down in cleanup logic even if one of the grouped entries fails.
9. Repeat the same lifecycle for the next managed model group until all managed Qwen entries for that benchmark are complete.

## Integration Seam Clarification

### Benchmark entry shape

Qwen comparison entries should stop pretending to be ordinary vendor entries with only `provider`, `model`, and `model_settings`. They need two extra concepts:

- `structured_family`: which structured extraction family the entry belongs to
- `session`: only for managed families, a groupable remote-session spec that describes the shared stack for a model

Illustrative benchmark entry shape:

```yaml
- id: deepinfra_qwen35_4b_current
  label: Qwen 3.5 4B / DeepInfra current structured
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    structured_family: deepinfra-current
    model_settings:
      temperature: 0
      max_tokens: 1024

- id: deepinfra_qwen35_4b_json_schema
  label: Qwen 3.5 4B / DeepInfra json_schema
  config:
    provider: deepinfra
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    structured_family: deepinfra-json-schema
    model_settings:
      temperature: 0
      max_tokens: 1024

- id: managed_qwen35_4b_modal_outlines
  label: Qwen 3.5 4B / Modal Outlines
  config:
    provider: managed-openai
    model: Qwen/Qwen3.5-4B
    prompt_version: v1
    structured_family: modal-outlines
    model_settings:
      temperature: 0
      max_tokens: 1024
    session:
      stack: sglang-outlines
      host: modal
      gpu: L40S
      context_window: 4096
```

Only the managed Modal entry needs a session block; the two DeepInfra entries stay provider-backed but differ in how structure is requested.

### Benchmark runtime seam

The cleanest integration point is the top-level benchmark loop, not the eval suite internals:

1. `run_benchmark(...)` resolves benchmark entries as it does now.
2. It partitions ordinary entries from managed Qwen entries.
3. DeepInfra-family entries continue directly to the current provider-backed path.
4. Managed Qwen entries are grouped by `session` plus `model`, excluding family-irrelevant fields.
5. For one managed group, the runtime creates a `ManagedSessionLease` with:
   - `base_url`
   - `api_key` or equivalent auth material
   - readiness/warmup status
   - teardown callback
6. That lease is passed into each grouped entry launch.

This keeps per-entry experiment identity intact while letting infrastructure lifecycle live only where it is needed: the managed Modal family.

### Extraction seam

The extraction layer needs three controlled structured paths:

- `deepinfra-current`:
  - preserve the current SDK-structured extraction path
  - use it as the historical baseline

- `deepinfra-json-schema`:
  - call DeepInfra with explicit provider-side `response_format=json_schema`
  - preserve the same `Todo`-typed return contract

- `modal-outlines`:
  - call the managed OpenAI-compatible endpoint backed by SGLang + Outlines
  - preserve the same `Todo`-typed return contract

That means the extraction config needs to carry:

- a runtime transport override such as `base_url`
- a structured family selector

The provider builder should therefore grow both:

- a generic OpenAI-compatible path for managed endpoints
- an explicit way to request DeepInfra's provider-native JSON-schema mode

## Spike Notes

- `020_spike_b1-sglang-modal.md`
  - Question: What is the smallest practical Modal-based spike that proves `B1` works behind a remote API endpoint, and what prerequisites, compute choice, and cost envelope does it require?
  - Outcome: The spike was executed successfully with `modal run scripts/qwen_sglang_outlines_smoke.py` against `Qwen/Qwen3.5-4B` on `L40S`, using a remote SGLang server launched with `--grammar-backend outlines`; a richer extraction case showed that unconstrained extraction remained free-form while constrained extraction returned valid JSON, and an Outlines-specific whitespace-pattern rerun changed the constrained JSON formatting from compact to pretty-printed.
  - Shape Impact: This substantially de-risks `B1` at the mechanical level, records two concrete implementation hazards for follow-up work, and adds a stronger Outlines-specific signal because changing `--constrained-json-whitespace-pattern` materially changed the constrained JSON output.

## Final Slices

### Selected Slicing Logic

- Rationale: Minimize path length to the full extraction comparison, accepting larger slices.
- Sequence:
  1. Restore the full `deepinfra-current` extraction family.
  2. Add the full `deepinfra-json-schema` extraction family.
  3. Add the full `modal-outlines` extraction family together with the managed lifecycle guarantees.
  4. Mirror the confirmed comparison to replay.
- Demo scenario: Run the extraction benchmark and see the full three-family comparison emerge in three visible stages before replay is added as the final mirror slice.
- Notes for `meanpowers:write-spec`:
  - Treat `V1` to `V3` as extraction-only slices.
  - Keep replay entirely out of scope until `V4`.
  - Use the managed lifecycle proof in `V3` as an acceptance boundary, not as a background implementation detail.

| Component | V1 | V2 | V3 | V4 |
|---|---:|---:|---:|---:|
| S0.1 Benchmark entry families are explicit | X |  |  |  |
| S0.2 `deepinfra-current` extraction canary exists | X |  |  |  |
| S0.3 `deepinfra-current` extraction family is complete for all 4 models | X |  |  |  |
| S0.4 `deepinfra-json-schema` extraction canary exists |  | X |  |  |
| S0.5 `deepinfra-json-schema` extraction family is complete for all 4 models |  | X |  |  |
| S0.6 `modal-outlines` extraction canary exists |  |  | X |  |
| S0.7 `modal-outlines` extraction family is complete for all 4 models |  |  | X |  |
| S0.8 Managed extraction lifecycle is safe and measurable |  |  | X |  |
| S0.9 Replay mirrors the confirmed extraction comparison |  |  |  | X |

### V1: Restore the historical extraction baseline

**State after this slice:**  
The extraction benchmark explicitly represents the current DeepInfra structured family and restores all four Qwen sizes under that family, including the smaller models that previously dropped out.

**Included components:**

- `S0.1`
- `S0.2`
- `S0.3`

**Notes for `meanpowers:write-spec`:**

- This slice is about extraction coverage and report visibility, not about improving outcomes yet.
- Preserve the current DeepInfra structured path as-is.

### V2: Add the explicit DeepInfra JSON-schema family

**State after this slice:**  
The extraction benchmark compares all four Qwen sizes across two DeepInfra structured families: the current SDK-default structured path and the explicit provider-side JSON-schema path.

**Included components:**

- `S0.4`
- `S0.5`

**Notes for `meanpowers:write-spec`:**

- Keep this slice provider-local to isolate whether DeepInfra's native JSON-schema path changes behavior.
- `4B` is the natural canary model even if the full family lands in the same slice.

### V3: Add the full managed Modal/Outlines family

**State after this slice:**  
The extraction benchmark now contains the full `4 models x 3 families` comparison, and the managed Modal/SGLang/Outlines family runs with warmup outside measurement and guaranteed teardown.

**Included components:**

- `S0.6`
- `S0.7`
- `S0.8`

**Notes for `meanpowers:write-spec`:**

- The managed lifecycle guarantees are part of the slice contract, not optional hardening.
- Count managed startup and warmup outside measured benchmark latency.

### V4: Mirror the confirmed comparison to replay

**State after this slice:**  
The replay benchmark mirrors the confirmed three-family comparison structure already established on extraction.

**Included components:**

- `S0.9`

**Notes for `meanpowers:write-spec`:**

- Treat replay as a follow-on slice that inherits the family logic from extraction.
- Do not reopen the extraction comparison contract in this slice.

## Handoff To Write-Spec

- Final shape confirmed by user: yes
- Final slices confirmed by user: yes
- Slices ready for spec: `V1`, `V2`, `V3`, `V4`
- Open questions for spec:
  - Exact benchmark entry schema for the three structured families
  - Exact acceptance boundaries for managed lifecycle proof in `V3`

REQUIRED NEXT SKILL: `meanpowers:write-spec`
