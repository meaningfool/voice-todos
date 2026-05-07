# Spike: B1 SGLang + Outlines on Modal

## Context

This spike supports shape `B1`, the remote SGLang service with the Outlines grammar backend.

The goal of the spike is to de-risk the first implementation step before committing to `B1` over `B3`. The uncertainty is not whether SGLang and Outlines can work together in principle, but what exact deployment path, credentials, cost envelope, and smoke-validation shape are required to make the path real in this project.

## Goal

Learn the smallest practical path to a remote SGLang endpoint we control that can serve one Qwen model for:

- unconstrained text generation
- constrained JSON generation using Outlines

and determine whether the first spike can likely run inside a Modal Starter workspace.

## Questions

| ID | Question |
|---|---|
| B1-Q1 | What is the smallest end-to-end spike that proves SGLang + Outlines works behind a remote API endpoint? |
| B1-Q2 | Which model should be used for the first B1 spike so that failures are least ambiguous? |
| B1-Q3 | What external accounts, tokens, or local tooling are required before this spike can be executed? |
| B1-Q4 | What does the likely cost envelope look like on Modal Starter for a short B1 spike? |
| B1-Q5 | What should the spike prove at the API level before we treat B1 as substantially de-risked? |

## Findings

### Finding 1

The official Outlines docs describe SGLang as a separate server, local or remote, accessed through an OpenAI-compatible client.

They explicitly say to launch SGLang with `--grammar-backend outlines` to use Outlines instead of the default backend.

This is the strongest evidence currently found that `B1` cleanly matches the shaping intent of "with and without Outlines" on one remote API endpoint.

References:

- `https://dottxt-ai.github.io/outlines/1.0.3/features/models/sglang/`
- `https://docs.sglang.io/docs/advanced_features/structured_outputs`

### Finding 2

SGLang's structured output docs say:

- JSON schema, regex, and EBNF-style constraints are supported
- SGLang supports multiple grammar backends
- `XGrammar` is the default backend
- `Outlines` is available and can be selected with `--grammar-backend outlines`

This means the B1 spike must not rely on defaults. The launch command itself needs to make the Outlines selection explicit.

Reference:

- `https://docs.sglang.io/docs/advanced_features/structured_outputs`

### Finding 3

Modal has current official examples for both SGLang and vLLM remote deployments.

For SGLang specifically, Modal documents:

- running SGLang remotely on GPU
- starting from an SGLang-provided Docker image
- attaching Modal Volumes for model weights and compiled artifacts
- using an OpenAI-compatible API server

This makes Modal a credible execution environment for the B1 spike rather than a speculative host.

References:

- `https://modal.com/docs/examples/sglang_low_latency`
- `https://modal.com/docs/examples/sglang_snapshot`
- `https://frontend.modal.com/docs/examples/sglang_vlm`

### Finding 4

The current local workspace is now prepared to run a Modal-based spike:

- `modal` CLI is installed and authenticated against the user's Modal workspace
- no `HF_TOKEN` or related Hugging Face token environment variable is present

Inference:

- Modal account and CLI setup were required before execution, but are no longer blockers in this workspace.
- `HF_TOKEN` remains optional for this public-model spike.

### Finding 5

The Qwen 3.5 models under consideration are public Hugging Face repositories with Apache 2.0 licenses and no visible gated-access prompt in the pages inspected.

That suggests a Hugging Face token is not inherently required for access to these weights.

However, the official Outlines Modal example says a Hugging Face token is needed if the model is gated and shows `HF_TOKEN` wiring as the normal pattern for cloud execution.

Inference:

- For public Qwen weights, `HF_TOKEN` is likely optional rather than mandatory.
- It may still be useful operationally for avoiding anonymous download friction or rate limits.

References:

- `https://huggingface.co/Qwen/Qwen3.5-0.8B`
- `https://huggingface.co/Qwen/Qwen3.5-2B`
- `https://huggingface.co/Qwen/Qwen3.5-4B`
- `https://huggingface.co/Qwen/Qwen3.5-9B`
- `https://dottxt-ai.github.io/outlines/1.1.1/examples/deploy-using-modal/`

### Finding 6

Modal Starter currently includes:

- `$30 / month` free compute credit
- up to `10` GPU concurrency
- up to `8` deployed web endpoints
- `1 TiB / month` free included volume usage

Current published GPU rates include:

- `T4`: `$0.000164 / sec`
- `L4`: `$0.000222 / sec`
- `L40S`: `$0.000542 / sec`
- `A10`: `$0.000306 / sec`
- `A100 40 GB`: `$0.000583 / sec`
- `A100 80 GB`: `$0.000694 / sec`
- `H100`: `$0.001097 / sec`

This strongly suggests that a short single-model spike should fit inside the free Starter credit, assuming we do not jump immediately to large-GPU long-lived multi-model deployments.

References:

- `https://modal.com/pricing`
- `https://modal.com/docs/guide/billing`

### Finding 7

The best current compute heuristic for this spike is:

1. Use total model footprint as the memory baseline, not only active parameters.
2. Add headroom for KV cache and runtime overhead.
3. Keep context short for the spike, because context length is the main memory multiplier.

For this project, that means the first spike should not try to preserve Qwen's full advertised context window. It should intentionally cap context to something like `4k` or `8k` tokens so the spike tests serving mechanics rather than extreme-context capacity.

Modal's own GPU guide recommends starting with `L40S` for inference workloads, and the `L40S` gives `48 GB` of GPU RAM. That makes it the cleanest low-risk default for the B1 spike, especially because it leaves comfortable room above the approximate `9.34 GB` weight footprint of `Qwen/Qwen3.5-4B`.

Inference:

- `L40S` is the recommended first GPU for the B1 spike.
- `A10` remains a plausible lower-cost alternative if we later want to optimize down.
- `L40S` is also a more credible candidate than `A10` for later `9B` work.

References:

- `https://huggingface.co/blog/moe`
- `https://huggingface.co/docs/transformers/main/kv_cache`
- `https://modal.com/docs/guide/high-performance-llm-inference`
- `https://modal.com/docs/guide/gpu`
- `https://huggingface.co/Qwen/Qwen3.5-0.8B`
- `https://huggingface.co/Qwen/Qwen3.5-2B`
- `https://huggingface.co/Qwen/Qwen3.5-9B`

### Finding 8

For the first B1 spike, `Qwen/Qwen3.5-4B` is the best candidate model.

Reasoning:

- It is small enough to keep GPU cost modest relative to `9B`
- It is large enough that a failed constrained-output smoke test is less likely to be explained by "the model is simply too small"
- In this project's prior DeepInfra evaluation, `4B` already produced valid structured extraction output after tuning, so it is a better mechanics canary than `0.8B` or `2B`

The inspected Hugging Face file pages show approximate repository sizes:

- `0.8B`: `1.77 GB`
- `2B`: `4.57 GB`
- `4B`: `9.34 GB`
- `9B`: `19.3 GB`

References:

- `https://huggingface.co/Qwen/Qwen3.5-0.8B/tree/main`
- `https://huggingface.co/Qwen/Qwen3.5-2B/tree/main`
- `https://huggingface.co/Qwen/Qwen3.5-4B/tree/main`
- `https://huggingface.co/Qwen/Qwen3.5-9B/tree/main`

### Finding 9

The smallest useful B1 spike should prove five mechanics:

1. A remote SGLang endpoint can be launched on Modal for one Qwen model we control.
2. The endpoint accepts plain unconstrained OpenAI-compatible requests.
3. The endpoint is launched with `--grammar-backend outlines`.
4. A constrained JSON request returns schema-valid output.
5. The existing project can plausibly target that endpoint through its current benchmark architecture without inventing a separate runner.

### Finding 10

The checked-in runnable artifact for this spike is:

- `scripts/qwen_sglang_outlines_smoke.py`

The script intentionally uses `modal run`, not `modal deploy`, so the app lifetime is tied to the command execution rather than leaving a long-lived deployed endpoint behind.

It launches:

- one remote `SGLang` server on `L40S`
- one `Qwen/Qwen3.5-4B` model
- explicit `--grammar-backend outlines`
- one unconstrained request
- one constrained JSON-schema request

### Finding 11

The first real execution uncovered two integration issues that had to be fixed before the spike would run end to end:

1. Modal rejected mounting a Volume at `/root/.cache` because that path in the base `SGLang` image is not empty.
2. Modal's runtime dependency layer downgraded `typing_extensions` enough to break `SGLang`'s `pydantic` import path.

The fixes were:

- move the cache mount to `/cache`
- explicitly add `typing_extensions>=4.15.0` back into the image

These are meaningful implementation details for any follow-up `B1` work.

### Finding 12

The spike was executed successfully with:

- `modal run scripts/qwen_sglang_outlines_smoke.py`

Observed result:

- the remote `SGLang` endpoint launched successfully on `L40S`
- the launch path used `--grammar-backend outlines`
- the unconstrained request returned text successfully
- the constrained request returned schema-valid JSON
- the constrained path exercised the Outlines backend at runtime

Observed caveat:

- the unconstrained response still included a visible "Thinking Process" section rather than a clean minimal answer

Observed constrained output summary:

- todo 1: `Email Alice the budget update`
- todo 2: `Book the dentist appointment`

This means the basic `B1` mechanics are now proven in this environment.

### Finding 13

The richer follow-up run used the same extraction task in both unconstrained and constrained modes, instead of a toy free-form prompt.

The richer transcript included:

- a timed email task with reminder timing
- an assigned review task with a deadline
- an appointment-booking task
- explicit priority and category hints
- one explicitly non-actionable commentary sentence

This produced a more meaningful behavioral comparison than the first smoke.

### Finding 14

On the richer extraction task, the unconstrained request remained visibly unsuitable as a benchmark-grade structured extraction path.

Observed unconstrained behavior:

- it returned a long "Thinking Process" trace
- it did not return directly usable JSON
- it spent many tokens reasoning through the task instead of producing a compact machine-readable output

This is a better control than the earlier toy prompt because it shows the unconstrained extraction behavior on the actual extraction task shape.

### Finding 15

The final Outlines-specific check used the server argument:

- `--constrained-json-whitespace-pattern`

This is documented by SGLang as an `outlines` / `llguidance` runtime option, and Outlines' own JSON generation docs explain that the default whitespace pattern is `r"[ ]?"` while more permissive patterns such as `r"[\n\t ]*"` allow pretty-printed JSON but can cause repetition problems on smaller models.

References:

- `https://docs.sglang.io/docs/advanced_features/server_arguments`
- `https://dottxt-ai.github.io/outlines/reference/generation/json/`

### Finding 16

Two richer constrained runs were executed successfully:

1. Default Outlines whitespace behavior
2. Permissive Outlines whitespace behavior with `[\n\t ]*`

Observed result:

- with default Outlines whitespace behavior, the constrained output stayed compact even when explicitly asked to return pretty-printed JSON
- with permissive Outlines whitespace behavior, the constrained output switched to multi-line indented JSON

Concrete comparison:

- default run:
  - `whitespace_pattern`: `None`
  - `constrained_has_newlines`: `False`
  - `constrained_max_space_run`: `1`
- permissive run:
  - `whitespace_pattern`: `[\n\t ]*`
  - `constrained_has_newlines`: `True`
  - `constrained_max_space_run`: `6`

This is the clearest evidence from the spike that an Outlines-specific runtime configuration is actually active and materially changes the constrained output shape.

## Conclusion

The B1 spike is no longer just concrete enough to pursue. It has now been executed successfully.

The current best shape for the first spike is:

- host: Modal Starter workspace
- stack: remote SGLang server with `--grammar-backend outlines`
- model: `Qwen/Qwen3.5-4B`
- GPU: `L40S`
- context assumption: short context, likely `4k` or `8k`
- proof target: one unconstrained request plus one constrained JSON extraction request
- runnable artifact: `scripts/qwen_sglang_outlines_smoke.py`
- final backend-specific check: compare default Outlines whitespace behavior against permissive `[\n\t ]*`

Expected user/environment prerequisites before execution:

- a Modal account with Starter credit or equivalent
- local Modal CLI installation and authentication
- optionally a Hugging Face token for operational convenience

Current workspace status:

- Modal CLI/auth: satisfied
- Hugging Face token: still skipped, and not required for the successful public-model run

Likely cost position:

- a short single-model spike is likely compatible with Starter free credit
- `L40S` is currently `$0.000542 / sec`, about `$1.95 / hour`
- cost risk grows mostly with repeated cold starts, oversized context, or long-lived deployed endpoints

## Proposed Execution Plan

The current best execution plan for this spike is:

1. Prepare one Modal Starter workspace and authenticate local `modal` CLI access.
2. Provision an optional `HF_TOKEN` secret only if download friction appears during execution.
3. Start from Modal's SGLang example rather than inventing a new deployment shape.
4. Configure one remote deployment for `Qwen/Qwen3.5-4B` on `L40S`.
5. Launch SGLang explicitly with `--grammar-backend outlines`.
6. Cap context to `4k` or `8k` tokens for the spike.
7. Send one unconstrained OpenAI-compatible request.
8. Send one constrained JSON request matching a minimal extraction schema.
9. Record whether the response is schema-valid and whether the endpoint contract looks compatible with the existing benchmark path.
10. Tear the deployment down after the smoke test to avoid unnecessary warm-idle cost.

## User Intervention Needed

Before execution, the main things that likely need user help are:

- a Modal account with Starter credit or equivalent
- successful local `modal` CLI install and login
- confirmation that using `L40S` is acceptable for the first spike
- optional `HF_TOKEN` provisioning if anonymous model download turns out to be flaky

## Success Criteria

Treat the B1 spike as successful if all of these are true:

1. One remote SGLang endpoint launches on Modal for `Qwen/Qwen3.5-4B`.
2. The launch path explicitly selects `--grammar-backend outlines`.
3. One unconstrained API request returns a plausible text response.
4. One constrained JSON request returns schema-valid output.
5. Nothing about the request/response shape obviously forces a separate eval runner.

Status:

- satisfied in the current run

## Shape Impact

This spike does not yet change the selected shape.

What it does change:

- It proves `B1` works end to end in this environment for one model.
- It identifies `Qwen/Qwen3.5-4B` as the best first spike model and validates that choice.
- It records two concrete implementation hazards: cache mount path selection and `typing_extensions` compatibility in the Modal image.
- It adds a stronger Outlines-specific validation: changing `--constrained-json-whitespace-pattern` changed the constrained JSON formatting in exactly the way Outlines and SGLang documentation suggest.
- It upgrades the recommended first spike GPU from `A10` to `L40S`.
- It suggests that cost is unlikely to block a one-model B1 spike on Modal Starter.
