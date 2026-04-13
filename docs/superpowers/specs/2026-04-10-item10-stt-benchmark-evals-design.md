# Item 10 Design: STT Benchmark Evals

Scope: define the dedicated STT benchmark track for comparing dedicated
speech-to-text providers on the same recorded audio corpus using the benchmark
architecture from Item 7 and the provider seam introduced in Item 8.

## Why this exists

The project currently uses Soniox for live STT, but we need a clean way to
compare dedicated transcription candidates on the same recorded audio without
mixing that work into production backend code or into downstream extraction
quality.

Item 8 creates the production abstraction seam. Item 10 uses that seam to define
the actual STT benchmark we want to run.

## Goals

- compare dedicated STT candidates on the same recorded audio fixtures
- keep Soniox as the baseline entry
- measure final-transcript quality with WER
- measure speed, with latency to final transcript as the primary timing metric
- record which streaming and finalization features each provider actually
  exposes
- express the STT comparison in Item 7's dataset-plus-benchmark model

## Non-goals

- changing the production `/ws` provider in this item
- evaluating downstream todo extraction quality
- benchmarking conversational voice-agent quality
- designing rollout or migration work
- collapsing WER and latency into one total score

## Approved Decisions

- keep this track focused on dedicated STT, not omni/live conversational models
- remove `qwen3.5-omni-plus-realtime` from the current STT matrix
- replace Gemini Live with Google Cloud Speech-to-Text `chirp_3`
- use recorded fixture audio as input and saved transcript text as the reference
- use WER and latency to final transcript as the primary reported metrics
- treat partial text, endpointing, and manual finalization as provider
  capability notes and optional diagnostics, not required shared metrics

## First STT Candidate Matrix

| Candidate ID | Model | Role |
|---|---|---|
| `soniox_baseline` | `stt-rt-v4` | Current production baseline |
| `google_chirp3` | `chirp_3` | Main Google dedicated STT candidate |
| `voxtral_realtime` | `voxtral-mini-transcribe-realtime-2602` | Main Mistral dedicated STT candidate |

## Design Decisions

### 1. STT eval-owned data and orchestration live in top-level `evals/`

Item 7 moved canonical eval data and orchestration out of `backend/evals/`.
Item 10 should follow that architecture directly.

Target shape:

```text
backend/
  app/
    stt.py
    stt_factory.py
  tests/
    fixtures/

evals/
  cli.py
  run.py
  report.py
  datasets/
    stt/
      stt_transcription_v1.json
  benchmarks/
    stt_transcription_model_matrix_v1.yaml
  stt/
    dataset_loader.py
    evaluator.py
    provider_capabilities.py
    provider_adapters.py
```

The public interface should remain benchmark-first even if a temporary bootstrap
launcher is needed during migration.

### 2. `backend/tests/fixtures/` remains raw evidence, not the canonical dataset

Recorded audio and fixture artifacts stay in `backend/tests/fixtures/`.

Their role is:

- raw recorded audio
- transcript evidence
- provider-specific trace/debug material where present

The canonical STT benchmark dataset should live in `evals/datasets/stt/`.

### 3. The STT dataset should use the Item 7 dataset contract

The canonical STT dataset should stay small and git-reviewable.

Recommended dataset shape:

```json
{
  "name": "stt_transcription",
  "version": "v1",
  "rows": [
    {
      "id": "stop-the-button",
      "input": {
        "audio_path": "backend/tests/fixtures/stop-the-button/audio.pcm",
        "audio_format": "pcm_s16le",
        "sample_rate_hz": 16000,
        "num_channels": 1
      },
      "expected_output": {
        "transcript": "Stop the button."
      },
      "metadata": {
        "source_fixture": "stop-the-button",
        "tags": ["short_utterance", "finalization"]
      }
    }
  ]
}
```

The dataset should not encode benchmark entries or provider-specific result
fields.

### 4. The STT benchmark should use explicit entries

The benchmark file should be the stable source of truth for which providers are
being compared.

Recommended benchmark shape:

```yaml
benchmark_id: stt_transcription_model_matrix_v1
dataset: evals/datasets/stt/stt_transcription_v1.json
focus: model
headline_metric: word_error_rate

repeat: 3
task_retries: 1
max_concurrency: 1

entries:
  - id: soniox_baseline
    label: Soniox / stt-rt-v4
    config:
      provider: soniox
      model: stt-rt-v4

  - id: google_chirp3
    label: Google Cloud Speech-to-Text / chirp_3
    config:
      provider: google_cloud_speech
      model: chirp_3

  - id: voxtral_realtime
    label: Mistral / voxtral-mini-transcribe-realtime-2602
    config:
      provider: mistral
      model: voxtral-mini-transcribe-realtime-2602
```

Adding later STT providers should be an additive benchmark-entry change, not a
new one-off experiment registry.

### 5. Reporting should separate transcript quality, speed, and capability notes

Per-case STT result records should include:

- `reference_transcript`
- `predicted_transcript`
- `word_error_rate`
- `final_latency_ms`
- optional `first_partial_latency_ms`
- provider capability flags
- provider/runtime status for skipped or failed runs

The benchmark report's headline metric should be WER, but latency and capability
differences should remain first-class outputs rather than hidden footnotes.

### 6. Item 10 should build on Item 8, not bypass it

The STT benchmark should reuse the production-adjacent provider abstraction from
Item 8 wherever practical.

That preserves the dependency rule:

- `evals` may depend on `backend/app`
- `backend/app` must not depend on `evals`

It also avoids maintaining two unrelated notions of what an STT provider is.

## Relationship To Extraction Evals

- Item 10 answers which STT path gives the best transcript quality and speed
- Item 6 answers which LLM best converts a finalized transcript into todos
- end-to-end stack trials can happen later after both tracks are independently
  measured

## Expected Next Deliverables

- an implementation plan
- a canonical STT dataset under `evals/datasets/stt/`
- a provider capability map
- a benchmark definition under `evals/benchmarks/`
- benchmark-first reporting for WER plus latency

## References

- `docs/superpowers/specs/2026-04-10-item7-evals-restructure-design.md`
- `docs/superpowers/specs/2026-04-10-item8-stt-provider-abstraction-design.md`
- `docs/references/eval-models-and-stacks.md`
- `backend/tests/fixtures/`
- `docs/references/soniox.md`
