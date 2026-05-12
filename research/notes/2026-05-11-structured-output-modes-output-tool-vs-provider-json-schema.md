# Structured Output Modes: Output Tool vs Provider JSON Schema

Date: 2026-05-11

This note records the current understanding behind the two DeepInfra extraction
families now referenced by the Qwen constrained-evals spec:

- `deepinfra-output-tool`
- `deepinfra-provider-json-schema`

It is intentionally narrower than the broader constrained-decoding landscape.

## Executive Summary

The current extraction path in this repo is not an unstructured baseline. It is
a structured-output path implemented through `pydantic_ai` output tools over an
OpenAI-compatible API.

The proposed second DeepInfra family is a different structured-output path:
explicit provider-side `response_format=json_schema`.

So the benchmark is not comparing:

- structured vs unstructured

It is comparing:

- tool-call-based structured output
- provider-native JSON-schema structured output

For pure extraction tasks, the provider JSON-schema path is the stronger default
hypothesis for structural reliability. That is still an inference for this repo,
not a proven result yet.

## What The Current Repo Actually Does

The extraction agent is built with a typed output model in
[extract.py](../../backend/app/extract.py):

```python
agent = Agent(
    _build_model(config),
    output_type=ExtractionResult,
    instructions=resolved_prompt_ref.content,
    model_settings=_resolve_model_settings(config),
)
```

Relevant `pydantic_ai` behavior:

- `ModelProfile.default_structured_output_mode` defaults to `tool` in
  [profiles/__init__.py](../../backend/.venv/lib/python3.14/site-packages/pydantic_ai/profiles/__init__.py)
- output tools are materialized from the output schema in
  [_output.py](../../backend/.venv/lib/python3.14/site-packages/pydantic_ai/_output.py)
- the OpenAI-compatible adapter only sends `response_format` when output mode is
  `native` in
  [openai.py](../../backend/.venv/lib/python3.14/site-packages/pydantic_ai/models/openai.py)

This means the current DeepInfra path is:

- schema exposed to the model as a tool definition
- model expected to answer with a tool call carrying JSON arguments
- framework validates those arguments and turns them into `ExtractionResult`

## Two Modes In Practical Terms

### 1. Output Tool Mode

This is the current repo path.

Request shape:

- send `tools`
- optionally require or prefer a tool call
- schema is attached to the tool definition

Expected model response:

- assistant emits a `tool_call`
- arguments contain JSON matching the schema

Framework behavior:

- framework validates tool-call arguments
- if valid, that becomes the final typed result
- if the model emits plain text instead, the framework retries

Important nuance:

- in this repo, this path is driven by `pydantic_ai`
- it is not a DeepInfra-specific feature
- it depends on the provider supporting OpenAI-compatible tool calling

### 2. Provider JSON Schema Mode

This is the proposed new DeepInfra family.

Request shape:

- send `response_format={"type":"json_schema","json_schema":...}`

Expected model response:

- assistant emits JSON content directly
- response is expected to match the supplied schema

Framework behavior:

- app parses assistant content as JSON
- app validates it as `ExtractionResult`

Important nuance:

- this path depends on provider-native support for `response_format=json_schema`
- it is not the same API surface as tool calling

## What The Official Docs Say

OpenAI's structured-outputs guide says:

- use function calling when the model is connecting to tools, functions, or
  data in your system
- use structured `response_format` when you want to structure the model's own
  response

DeepInfra's structured-output docs say:

- `json_object` returns valid JSON without a fixed schema
- `json_schema` enforces a strict JSON schema
- prefer `json_schema` when downstream code depends on specific fields and types

This lines up with the intended use here:

- extraction is a typed response-generation task
- not a multi-step agent tool-execution task

## Reliability Findings

### Documented Facts

- OpenAI says strict structured outputs are available both through tools and
  through response formats.
- OpenAI reports much higher schema adherence for structured outputs than for
  prompting alone.
- DeepInfra recommends `json_schema` for production when code depends on a fixed
  structure.
- JSONSchemaBench shows that constrained-decoding engines greatly improve
  structural guarantees, but no single engine dominates every schema/task and
  engines can be over-constrained or under-constrained.

### Local Inference

For this repo's extraction task, `deepinfra-provider-json-schema` is the better
default structural-reliability hypothesis than `deepinfra-output-tool`.

Why:

- extraction is a direct typed-output task
- provider JSON schema removes the extra "emit a tool call" protocol step
- the current repo path appears to be ordinary output-tool mode, not an explicit
  strict tool-calling setup

That last point matters. OpenAI documents strict tool mode separately, but the
current repo builds a plain typed output agent and does not explicitly mark the
output tool schema as strict in local app code. So the real comparison here is
likely:

- current non-native output-tool path
- provider-native JSON-schema path

not:

- strict tool structured outputs
- strict response-format structured outputs

## Live DeepInfra Verification On 2026-05-11

A live strict-schema probe was run against all four target models on
2026-05-11:

- `Qwen/Qwen3.5-0.8B`
- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`

What was verified:

- all four models accepted `response_format=json_schema`

What changed with thinking mode:

- with `enable_thinking=false`, all four returned valid schema-matching JSON in
  normal assistant `content`
- with thinking left on:
  - `0.8B` and `2B` returned the JSON in `reasoning_content`, leaving normal
    `content` empty
  - `4B` and `9B` returned valid JSON in `content`, but also emitted long
    reasoning text

Practical implication:

- if the application expects the JSON in normal assistant `content`, then
  `enable_thinking=false` should be treated as part of the
  `deepinfra-provider-json-schema` family contract
- the alternative would be explicitly teaching the extraction path to treat
  `reasoning_content` as a supported result channel, which is not the current
  contract

## Relationship To Outlines / SGLang

These are related, but not identical, mechanisms.

### What is similar

Both `provider_json_schema` and Outlines/SGLang aim to constrain generation so
the final output matches a schema.

### What is different

`deepinfra-provider-json-schema`:

- managed by the provider
- implementation details are opaque
- we control only the request contract

Outlines/SGLang:

- self-hosted or stack-controlled constrained decoding
- implementation mechanism is explicit and documented
- grammar engine is part of the runtime we choose and operate

SGLang docs explicitly say the output is guaranteed to follow the specified
constraint and describe grammar backends for constrained generation. That is a
transparent constrained-decoding stack.

DeepInfra's docs say the model is constrained to produce values matching the
schema, but they do not document the internal engine or whether it is:

- token-level constrained decoding
- a proprietary grammar engine
- a hybrid of training plus constrained decoding
- some other provider-side enforcement stack

## What We Know vs What We Do Not Know

### Known

- the current repo path is `pydantic_ai` output-tool mode
- DeepInfra exposes provider-native `json_schema`
- Outlines/SGLang are explicit constrained-decoding systems
- provider-native JSON-schema and output-tool mode are different request/response
  surfaces

### Unknown

- whether DeepInfra's `json_schema` implementation uses token-level constrained
  decoding internally
- whether its implementation is similar in principle to Outlines/SGLang or uses
  a different proprietary mechanism
- whether DeepInfra's provider-native schema mode recovers `0.8B` and `2B`
  enough to keep them in the matrix on the real extraction task

## Working Conclusion For The Spec

The first extraction comparison slice should stay provider-local and compare:

- `deepinfra-output-tool`
- `deepinfra-provider-json-schema`

with the same:

- model
- prompt
- `temperature`
- `max_tokens`
- output schema

This isolates one structural variable:

- output-tool protocol vs provider-native JSON-schema protocol

with one family-local compatibility requirement for the provider-native path:

- `enable_thinking=false`

It does not prove constrained decoding is the only underlying difference. It
does prove that the application-visible structured-output path changed.

## Sources

- OpenAI structured outputs guide:
  https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI function calling guide:
  https://developers.openai.com/api/docs/guides/function-calling
- OpenAI structured outputs launch note:
  https://openai.com/index/introducing-structured-outputs-in-the-api/
- DeepInfra structured outputs:
  https://docs.deepinfra.com/chat/structured-outputs
- SGLang structured outputs:
  https://docs.sglang.io/docs/advanced_features/structured_outputs
- JSONSchemaBench:
  https://openreview.net/pdf?id=FKOaJqKoio
