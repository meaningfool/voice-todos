# .txt, Doubleword, Outlines, and Qwen Eval Discussion

Date: 2026-04-29

This note consolidates the discussion about retrying small Qwen extraction evals
with constrained structured generation.

## Starting Point

The existing voice-todos eval work already includes DeepInfra-hosted Qwen 3.5
experiments:

- `Qwen/Qwen3.5-9B`
- `Qwen/Qwen3.5-4B`

Earlier small-model trials also included:

- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-0.8B`

The earlier conclusion was:

- `Qwen/Qwen3.5-9B` passed the structured extraction path.
- `Qwen/Qwen3.5-4B` only passed after tuning with `temperature=0` and
  `max_tokens=1024`.
- `Qwen/Qwen3.5-2B` failed output validation.
- `Qwen/Qwen3.5-0.8B` repeatedly exhausted token budget or entered thinking
  loops before producing valid structured output.

Local references:

- `docs/references/2026-04-07-deepinfra-qwen-smoke-test.md`
- `docs/superpowers/specs/2026-04-07-item6.7-deepinfra-qwen-evals-design.md`
- `evals/benchmarks/todo_extraction_bench_v1.yaml`
- `evals/benchmarks/todo_replay_bench_v1.yaml`

## Naming Clarifications

The relevant names are:

- `.txt` / `dottxt`: the company/platform.
- `dotjson`: .txt's JSON Schema constrained-generation product/technology.
- `JSON Schema`: the schema format describing the exact output shape.
- `response_format`: the OpenAI-compatible API field used to send a JSON Schema.
- `Outlines`: .txt's open-source structured generation library.

There is no separate `.json` or `.dxt` product in this discussion. When earlier
notes used `.json` informally, the intended term was `dotjson`.

## .txt Hosted API

.txt has a hosted OpenAI-compatible API at:

```text
https://api.dottxt.ai/v1
```

The public .txt model catalog currently lists larger models:

- `Qwen/Qwen3.5-397B-A17B`
- `Qwen/Qwen3-14B-FP8`
- `openai/gpt-oss-20b`
- `Qwen/Qwen3-VL-235B-A22B-Instruct-FP8`
- `Qwen/Qwen3-VL-30B-A3B-Instruct-FP8`

Public docs do not currently list `Qwen/Qwen3.5-0.8B`, `2B`, `4B`, or `9B` on
the .txt hosted API.

The account-specific check is:

```bash
curl https://api.dottxt.ai/v1/models \
  -H "Authorization: Bearer $DOTTXT_API_KEY"
```

References:

- https://docs.dottxt.ai/api/overview
- https://docs.dottxt.ai/api/models
- https://docs.dottxt.ai/api/list-models

## Doubleword Relationship

Doubleword is the inference provider/launch partner that .txt names for its
production inference stack. The relationship is:

```text
User calls api.dottxt.ai
  -> .txt hosted API/product layer
  -> production inference stack operated with Doubleword
```

The APIs are not necessarily the same:

- .txt hosted API: `https://api.dottxt.ai/v1`
- Doubleword API: `https://api.doubleword.ai/v1`

They may have different API keys, model lists, pricing, and availability.

Doubleword's public model/pricing docs list:

- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`
- `Qwen/Qwen3.5-9B-dotjson`

For the small-ish Qwen sizes, the only clearly listed named dotjson variant is
`Qwen/Qwen3.5-9B-dotjson`. A `Qwen/Qwen3.5-4B-dotjson` model was not found in
the public docs. The 4B model may still accept generic `response_format` JSON
Schema requests, but that needs to be tested.

Reference:

- https://docs.doubleword.ai/inference-api/model-pricing

## Pricing And Access

No public .txt hosted API price table or confirmed free tier was found.

The public .txt site says the hosted `api.dottxt.ai` platform is available on a
pay-per-token basis, but the exact rates were not visible in public docs during
this review.

Treat .txt hosted API and dotjson self-hosting as likely paid or gated until an
API key, trial, or license terms are confirmed.

References:

- https://dottxt.ai/
- https://dottxt.ai/pricing

## Open Source Status

.txt does have open-source work on GitHub:

- `dottxt-ai/outlines`
- `dottxt-ai/outlines-core`

Outlines is the open-source structured generation library. dotjson appears to be
the gated/commercial production product.

The GitHub organization mentions deployable packages such as:

- `dotvllm`
- `dotsglang`
- `dottensorrt_llm`

Public GitHub repositories for those packages were not found in the review,
which suggests they may be private, packaged, or commercial.

References:

- https://github.com/dottxt-ai
- https://github.com/dottxt-ai/outlines
- https://github.com/dottxt-ai/outlines-core
- https://dottxt-ai.github.io/outlines/main/index.html
- https://docs.dottxt.ai/dotjson/

## Possible Eval Matrix

A useful hosted/provider comparison would be:

```text
deepinfra_qwen35_9b_default
deepinfra_qwen35_4b_structured_tuned
doubleword_qwen35_4b_plain
doubleword_qwen35_4b_response_format
doubleword_qwen35_9b_plain
doubleword_qwen35_9b_dotjson
```

The old failures could be revisited only if the models are available on the
chosen provider or self-hosted:

```text
qwen35_2b_plain
qwen35_2b_constrained
qwen35_0_8b_plain
qwen35_0_8b_constrained
```

## Self-Hosting Path

To test all four Qwen sizes, self-hosting is likely necessary:

- `Qwen/Qwen3.5-0.8B`
- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`

There are three possible self-hosting levels.

### Level 1: Plain vLLM Or SGLang

Expose each model through an OpenAI-compatible endpoint.

Example:

```bash
vllm serve Qwen/Qwen3.5-0.8B \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --language-model-only
```

Then swap in:

```text
Qwen/Qwen3.5-2B
Qwen/Qwen3.5-4B
Qwen/Qwen3.5-9B
```

The eval runner can target:

```text
http://HOST:8000/v1
```

### Level 2: Open-Source Structured Outputs

Use vLLM/SGLang structured output support or Outlines to enforce JSON Schema.
This is not dotjson, but it tests the core question: does constrained decoding
rescue tiny Qwen models enough to matter?

References:

- https://docs.vllm.ai/features/structured_outputs.html
- https://docs.sglang.io/advanced_features/structured_outputs.html

### Level 3: True dotjson Self-Hosting

This requires dotjson access from .txt.

Likely process:

1. Get dotjson/dotvllm/dotsglang access or license from .txt.
2. Choose a serving stack: vLLM, SGLang, TensorRT-LLM, or custom Transformers.
3. Load the Qwen model from Hugging Face.
4. Compile the `ExtractionResult` JSON Schema with dotjson for the model
   tokenizer.
5. Attach dotjson as a constrained decoder/logits processor.
6. Expose an OpenAI-compatible `/v1/chat/completions` endpoint.
7. Point the voice-todos eval runner at that endpoint.

## Running On Modal

Modal is a plausible place to run these experiments because local hardware will
be limiting.

Two paths:

### Modal + vLLM

Use Modal's Qwen/vLLM OpenAI-compatible server example as the starting point.
This is likely the easiest path for plugging into the current eval runner.

Reference:

- https://modal.com/docs/examples/vllm_inference

### Modal + Outlines

Run a custom Modal FastAPI endpoint that:

1. Installs `torch`, `transformers`, `accelerate`, `outlines`, and `fastapi`.
2. Loads a Qwen model.
3. Uses Outlines to generate from the `ExtractionResult` Pydantic schema.
4. Returns JSON over HTTP.

Modal references:

- https://modal.com/docs/guide/gpu
- https://modal.com/docs/guide/webhooks

Suggested GPU sizing:

```text
0.8B: T4 or L4
2B:   L4
4B:   L4 or A10G
9B:   A10G, L40S, or A100 depending on precision and context
```

Cap context aggressively, probably `4096` or `8192`, because todo extraction
does not need huge Qwen context and KV cache can dominate memory cost.

## Recommended Next Step

Start with the lowest-cost behavioral question:

1. Run plain Qwen `0.8B`, `2B`, `4B`, and `9B` through a Modal/vLLM endpoint.
2. Add vLLM or SGLang structured outputs and rerun the same evals.
3. Compare with Doubleword's hosted `Qwen/Qwen3.5-9B-dotjson`.
4. Only pursue paid/gated .txt dotjson self-hosting if open-source constrained
   decoding shows the smaller models become semantically useful.

