# DeepInfra Qwen 3.5 Smoke Test

Date: 2026-04-07

This note records the first live DeepInfra smoke test for the extraction path
after adding `DEEPINFRA_API_KEY`.

## What was tested

- `backend/evals/extraction_quality/run.py --list-experiments`
- direct `extract_todos(...)` calls through the backend's structured extraction path
- direct OpenAI-compatible chat-completions calls against DeepInfra for model-id and auth validation

## Result summary

| Model | DeepInfra auth / routing | Structured extraction path | Decision |
|---|---|---|---|
| `Qwen/Qwen3.5-9B` | pass | pass with provider-default settings | keep |
| `Qwen/Qwen3.5-4B` | pass | fails at defaults, passes with `temperature=0` and `max_tokens=1024` | keep with tuned config |
| `Qwen/Qwen3.5-2B` | pass | fails output validation even after tuning attempts | remove |
| `Qwen/Qwen3.5-0.8B` | pass | repeatedly exhausts token budget / enters thinking loops before valid output | remove |

## Notes

- The provider key and model ids were valid for all four models. The failures on
  `2B` and `0.8B` were not authentication failures.
- `Qwen/Qwen3.5-4B` started returning usable structured extraction output only
  after setting:
  - `temperature=0`
  - `max_tokens=1024`
- `Qwen/Qwen3.5-2B` still failed the strict structured-output path with
  `UnexpectedModelBehavior: Exceeded maximum retries (1) for output validation`
  after tuning attempts.
- `Qwen/Qwen3.5-0.8B` kept consuming the token budget before producing a valid
  structured output. Testing `enable_thinking=False` through `extra_body` did
  not resolve the extraction-path failure.

## Follow-up decision

- Keep `Qwen/Qwen3.5-9B` in the active extraction matrix.
- Keep `Qwen/Qwen3.5-4B` only as a tuned experiment, not a provider-default one.
- Remove `Qwen/Qwen3.5-2B` and `Qwen/Qwen3.5-0.8B` from the active experiment matrix.

## External references

- DeepInfra OpenAI-compatible API example:
  https://stage.deepinfra.com/zai-org/GLM-4.5V/api
- DeepInfra models catalog:
  https://stage.deepinfra.com/models/featured/2
- Qwen 3.5 0.8B model card warning about thinking loops:
  https://huggingface.co/Qwen/Qwen3.5-0.8B/blob/main/README.md
