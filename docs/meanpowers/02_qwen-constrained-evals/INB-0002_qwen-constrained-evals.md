# Re-evaluate Small Qwen Extraction Models With Constrained Structured Generation

## Baseline

The extraction eval matrix keeps DeepInfra `Qwen/Qwen3.5-9B` and tuned `Qwen/Qwen3.5-4B`, while `Qwen/Qwen3.5-2B` and `Qwen/Qwen3.5-0.8B` were removed after failing the structured extraction path.

## Target

The project has a defined experiment track to compare hosted and self-hosted constrained-generation paths for `Qwen/Qwen3.5-0.8B`, `Qwen/Qwen3.5-2B`, `Qwen/Qwen3.5-4B`, and `Qwen/Qwen3.5-9B`, including whether smaller models become usable enough to keep.

## Intent

Answer the durable research question of whether constrained decoding can make smaller Qwen models viable for todo extraction, and identify the lowest-cost provider or hosting path worth pursuing.

## Context

- Earlier DeepInfra extraction evals showed `Qwen/Qwen3.5-9B` working on provider defaults and `Qwen/Qwen3.5-4B` working only with tuning, while `2B` and `0.8B` failed output validation or exhausted token budgets.
- The attached April 29, 2026 note consolidates naming clarifications around `.txt`, `dotjson`, `response_format`, and `Outlines`, and distinguishes `.txt` hosted API access from Doubleword's public inference API.
- The same note proposes a comparison track across DeepInfra, Doubleword hosted models, open-source structured outputs on `vLLM` or `SGLang`, and gated `.txt` `dotjson` self-hosting.
- The note recommends treating this as a behavioral evaluation question first: test cheaper hosted or open-source constrained decoding paths before pursuing paid or gated `dotjson` self-hosting.

## Relevant References

- `.context/attachments/pasted_text_2026-04-30_12-11-07.txt`
- `docs/references/2026-04-07-deepinfra-qwen-smoke-test.md`
- `docs/superpowers/specs/2026-04-07-item6.7-deepinfra-qwen-evals-design.md`
- `evals/benchmarks/todo_extraction_bench_v1.yaml`
- `evals/benchmarks/todo_replay_bench_v1.yaml`

## Questions For Later

- Which provider path should be tried first: Doubleword hosted models, open-source structured outputs on `vLLM` or `SGLang`, or gated `.txt` `dotjson`?
- Should terminology cleanup for `.txt`, `dotjson`, Doubleword, and `response_format` also be applied to existing project docs as part of this work?
- What evaluation threshold counts as semantically useful enough to restore `2B` or `0.8B` to the active extraction matrix?
- Is Modal the preferred environment for self-hosted experiments, or is there another deployment target that should be evaluated first?
