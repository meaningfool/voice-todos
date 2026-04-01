# Eval Models And Stack Candidates

Reference list for the local evals we want to run.

## Summary

These evals run locally. The tables below summarize the current model candidates and the two colocated stack directions we want to validate next.

| Block | Candidates |
|------|------------|
| STT | `stt-rt-v4`, `gemini-3.1-flash-live-preview`, `qwen3.5-omni-plus-realtime`, `voxtral-mini-transcribe-realtime-2602` |
| LLM extraction | `gemini-3-flash-preview` (default), `gemini-3-flash-preview` (`thinking_level="minimal"`), `gemini-3.1-flash-lite-preview` (default), `gemini-3.1-flash-lite-preview` (`thinking_level="minimal"`), `mistral-small-2603` |

| Stack | App host | STT | LLM |
|------|----------|-----|-----|
| Mistral | Koyeb | `voxtral-mini-transcribe-realtime-2602` | `mistral-small-2603` |
| Google | Cloud Run | `gemini-3.1-flash-live-preview` | `gemini-3-flash-preview` |

Soniox and Qwen stay in the candidate list as comparison baselines outside the two main colocated stacks.

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

### Google Gemini 3.1 Flash Live Preview

- **Model:** `gemini-3.1-flash-live-preview`
- **Role in evals:** Primary Google-side live speech candidate.
- **Quick description:** Realtime multimodal live model. For our evals, the relevant part is using it as a live speech-to-text candidate.
- **Official docs:**
  - Model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview
  - Live API capabilities: https://ai.google.dev/gemini-api/docs/live-api/capabilities
  - Live API guide: https://ai.google.dev/gemini-api/docs/live-guide
  - Announcement: https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-live/

### Qwen Omni Realtime

- **Model:** `qwen3.5-omni-plus-realtime`
- **Role in evals:** Additional live STT candidate to compare against Soniox, Gemini Live, and Voxtral.
- **Quick description:** Realtime omni model with speech input/output support. For our evals, the relevant part is using it as a live speech-to-text candidate.
- **Official docs:**
  - Realtime API: https://www.alibabacloud.com/help/en/model-studio/realtime
  - Model catalog: https://www.alibabacloud.com/help/en/model-studio/models
  - Qwen Omni repo: https://github.com/QwenLM/Qwen3-Omni

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
- **STT:** `gemini-3.1-flash-live-preview`
- **LLM:** `gemini-3-flash-preview`
- **Direction:** Cloud Run-hosted Python app plus Google-managed live speech and LLM APIs
- **Notes:** This is the Google-oriented stack we want to test, centered on a live Gemini speech path rather than Chirp.
- **Official docs:**
  - Cloud Run overview: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
  - Gemini 3.1 Flash Live Preview: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview
  - Live API guide: https://ai.google.dev/gemini-api/docs/live-guide
  - Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
