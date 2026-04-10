# Eval Models And Stack Candidates

Reference list for the local evals we want to run.

## Summary

These evals run locally. The tables below summarize the current model candidates and the two colocated stack directions we want to validate next.

| Block | Candidates |
|------|------------|
| STT | `stt-rt-v4`, `chirp_3`, `voxtral-mini-transcribe-realtime-2602` |
| LLM extraction | `gemini-3-flash-preview` (default), `gemini-3-flash-preview` (`thinking_level="minimal"`), `gemini-3.1-flash-lite-preview` (default), `gemini-3.1-flash-lite-preview` (`thinking_level="minimal"`), `mistral-small-2603`, `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.5-4B` |

| Stack | App host | STT | LLM |
|------|----------|-----|-----|
| Mistral | Koyeb | `voxtral-mini-transcribe-realtime-2602` | `mistral-small-2603` |
| Google | Cloud Run | `chirp_3` | `gemini-3-flash-preview` |

Soniox stays in the candidate list as the current baseline outside the two main colocated stacks.

## Current Decisions

This reference doc reflects the decisions captured in this thread and recorded in the source-of-truth docs:

- STT evals now focus on dedicated transcription models rather than conversational live/omni models
- `qwen3.5-omni-plus-realtime` is removed from the current STT eval matrix
- Google STT moves from Gemini Live to Google Cloud Speech-to-Text `chirp_3`
- Item 8 should optimize for WER and speed, with provider capability differences recorded explicitly

Decision records:

- `docs/superpowers/specs/2026-04-01-item8-stt-model-evals-design.md`
- `docs/superpowers/plans/2026-04-01-item8-stt-model-evals.md`
- `docs/superpowers/plans/2026-03-25-item6-extraction-model-evals.md`

## STT Candidates

### Soniox

- **Model:** `stt-rt-v4`
- **Role in evals:** Current baseline. This is the realtime STT path already used in the repo.
- **Stack fit:** Outside the two main target stacks below, but important as a comparison baseline.
- **Official docs:**
  - Models: https://soniox.com/docs/stt/models
  - WebSocket API: https://soniox.com/docs/stt/api-reference/websocket-api
  - Manual finalization: https://soniox.com/docs/stt/rt/manual-finalization
  - Endpoint detection: https://soniox.com/docs/stt/rt/endpoint-detection

### Mistral Voxtral Mini Transcribe Realtime

- **Model:** `voxtral-mini-transcribe-realtime-2602`
- **Role in evals:** Primary STT candidate for the Mistral-oriented stack.
- **Quick description:** Realtime transcription-focused model optimized for low-latency live STT.
- **Official docs:**
  - Model page: https://docs.mistral.ai/models/voxtral-mini-transcribe-realtime-26-02
  - Realtime transcription guide: https://docs.mistral.ai/capabilities/audio_transcription/realtime_transcription
  - Audio overview: https://docs.mistral.ai/capabilities/audio/

### Google Cloud Chirp 3

- **Model:** `chirp_3`
- **Role in evals:** Primary Google dedicated STT candidate.
- **Quick description:** Google Cloud Speech-to-Text transcription model positioned for better accuracy and speed than earlier Chirp versions.
- **Official docs:**
  - Chirp 3 model docs: https://docs.cloud.google.com/speech-to-text/v2/docs/chirp-model
  - Transcription models overview: https://docs.cloud.google.com/speech-to-text/docs/transcription-model
  - Speech-to-Text overview: https://docs.cloud.google.com/speech-to-text/docs/basics

## LLM Candidates

### Gemini3 Flash default

- **Model:** `gemini-3-flash-preview`
- **Config:** Default Gemini 3 thinking behavior.
- **Role in evals:** Primary Google extraction candidate.
- **Notes:** The current Gemini 3 docs say the default thinking level is dynamic and maps to `high` unless explicitly changed.
- **Official docs:**
  - Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
  - Model catalog: https://ai.google.dev/models/gemini
  - Thinking controls: https://ai.google.dev/gemini-api/docs/thinking

### Gemini3 Flash minimal thinking

- **Model:** `gemini-3-flash-preview`
- **Config:** `thinking_level="minimal"`
- **Role in evals:** Lower-latency Google extraction candidate.
- **Notes:** This is the paired Gemini3 Flash comparison we already identified for extraction evals.

- **Official docs:**
  - Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
  - Thinking controls: https://ai.google.dev/gemini-api/docs/thinking

### Gemini 3.1 Flash-Lite, default thinking

- **Model:** `gemini-3.1-flash-lite-preview`
- **Config:** Default Gemini 3.1 Flash-Lite thinking behavior.
- **Role in evals:** New Google-side lightweight extraction candidate focused on speed and cost efficiency.
- **Notes:** Official Gemini docs position this model for high-frequency lightweight tasks, simple data extraction, and structured JSON output. This is the main newer small/fast Gemini candidate we want to compare against Gemini 3 Flash.
- **Official docs:**
  - Model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-preview
  - Model catalog: https://ai.google.dev/gemini-api/docs/models
  - Thinking controls: https://ai.google.dev/gemini-api/docs/thinking
  - Announcement: https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/

### Gemini 3.1 Flash-Lite, minimal thinking

- **Model:** `gemini-3.1-flash-lite-preview`
- **Config:** `thinking_level="minimal"`
- **Role in evals:** Lower-latency Google extraction candidate within the Flash-Lite tier.
- **Notes:** This pairs with the default-thinking Flash-Lite run so we can see whether the newer lightweight Gemini line is competitive for structured extraction when tuned for speed.
- **Official docs:**
  - Model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-preview
  - Thinking controls: https://ai.google.dev/gemini-api/docs/thinking
  - Announcement: https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/

### Mistral Small 4

- **Model:** `mistral-small-2603`
- **Role in evals:** First Mistral LLM candidate for extraction evals.
- **Notes:** This is the main Mistral-side extraction model we want to start comparing now. We can add a newer top-tier Mistral model later if we decide to widen the Mistral stack eval.
- **Official docs:**
  - Model page: https://docs.mistral.ai/models/mistral-small-4-0-26-03
  - Model catalog: https://docs.mistral.ai/getting-started/models/

### DeepInfra Qwen 3.5 family

- **Models:** `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.5-4B`
- **Role in evals:** DeepInfra-hosted Qwen 3.5 comparison set for extraction experiments after narrowing the matrix with live smoke tests.
- **Notes:** `Qwen/Qwen3.5-9B` works in the current structured extraction path with provider-default settings. `Qwen/Qwen3.5-4B` stays in the matrix with a tuned config (`temperature=0`, `max_tokens=1024`). `Qwen/Qwen3.5-2B` and `Qwen/Qwen3.5-0.8B` were removed after failing structured-output smoke tests despite successful authentication and direct chat-completion access.
- **Reference:** `docs/references/2026-04-07-deepinfra-qwen-smoke-test.md`
- **Official docs:**
  - DeepInfra API reference example: https://stage.deepinfra.com/zai-org/GLM-4.5V/api
  - DeepInfra models catalog: https://stage.deepinfra.com/models/featured/2

## Envisioned Colocated Stacks

### Mistral Stack

- **App host:** Koyeb
- **STT:** `voxtral-mini-transcribe-realtime-2602`
- **LLM:** Start with `mistral-small-2603` in local extraction evals
- **Direction:** Koyeb-hosted Python app plus Mistral-managed model APIs
- **Notes:** This is the main Mistral-oriented stack to test first. Soniox remains a useful comparison baseline but sits outside this stack.
- **Official docs:**
  - Koyeb FastAPI deployment: https://www.koyeb.com/docs/deploy/fastapi
  - Koyeb scaling: https://www.koyeb.com/docs/reference/scaling
  - Koyeb sandboxes: https://www.koyeb.com/docs/sandboxes
  - Mistral models catalog: https://docs.mistral.ai/getting-started/models/
  - Mistral audio overview: https://docs.mistral.ai/capabilities/audio/

### Google Stack

- **App host:** Cloud Run
- **STT:** `chirp_3`
- **LLM:** `gemini-3-flash-preview`
- **Direction:** Cloud Run-hosted Python app plus Google Cloud Speech-to-Text and Gemini-managed LLM APIs
- **Notes:** This is the Google-oriented stack we want to test, centered on dedicated Google STT rather than Gemini Live.
- **Official docs:**
  - Cloud Run overview: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
  - Chirp 3 model docs: https://docs.cloud.google.com/speech-to-text/v2/docs/chirp-model
  - Speech-to-Text overview: https://docs.cloud.google.com/speech-to-text/docs/basics
  - Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
