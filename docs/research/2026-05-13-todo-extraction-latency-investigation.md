# Todo Extraction Latency Investigation

Date: 2026-05-13

## Scope

Short record of the follow-up investigation into the todo extraction benchmark,
focused on the Qwen Modal Outlines lanes, the DeepInfra comparison lanes, and
historical Mistral Small 4 timing.

## What We Did

- Rechecked the final `todo_extraction_bench_v1` report and refreshed the
  current HTML and JSON artifacts.
- Aligned the Modal Outlines benchmark settings with the DeepInfra structured
  baseline so the comparison used the same `max_tokens` and `enable_thinking`
  behavior.
- Fixed the managed Modal warmup path so it exercised the real structured JSON
  extraction flow and had access to the extraction prompt file.
- Verified that the managed Modal Qwen server selection was wrong for the small
  model lanes, then fixed it so each requested model starts its own explicit
  server class.
- Reran the managed Qwen Modal Outlines entries and refreshed the benchmark
  report.
- Compared current Mistral Small 4 benchmark timing with prior committed report
  snapshots and older raw extraction eval artifacts.

## Conclusions

- The earlier high-quality `Modal Outlines 0.8B` and `2B` results were
  misleading because those managed lanes were effectively running the default
  `Qwen/Qwen3.5-4B` server.
- After fixing model selection, true `0.8B` and `2B` Modal Outlines runs are
  faster, but their extraction quality is much worse than the earlier report
  suggested.
- The best current managed Outlines tradeoff in this benchmark is `Qwen 3.5 4B`
  rather than the smaller models.
- The remaining Modal Outlines latency gap does not look like plain network
  round-trip overhead. Lightweight host probing suggested the larger delays are
  more likely in the constrained-decoding and serving path.
- Mistral Small 4 was not materially reconfigured during this work. On the
  recent 26-case benchmark history it has already been in the roughly
  `0.7s-0.8s` average range, though older April raw extraction eval artifacts
  did show much slower runs with larger tail latencies.

## Artifacts

- Benchmark snapshot: `docs/research/2026-05-13-todo-extraction-bench-v1.html`
- Source report generator output: `evals/reports/todo_extraction_bench_v1.html`
