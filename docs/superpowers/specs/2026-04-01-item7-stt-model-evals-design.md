# Item 7 Design: STT Model Evals

Scope: define the local STT eval set for comparing dedicated speech-to-text candidates on the same recorded audio with WER and speed as the main outputs.

## Why this exists

The project currently uses Soniox for live STT. We want a clean STT eval track that compares dedicated transcription models on the same audio corpus without mixing in extraction quality or voice-agent behavior.

## Goals

- Compare dedicated STT candidates on the same recorded audio fixtures
- Keep Soniox as the baseline
- Measure final-transcript quality with WER
- Measure speed, with latency to final transcript as the primary timing metric
- Record which streaming/finalization features each provider actually exposes

## Non-goals

- Evaluating downstream todo extraction quality
- Benchmarking conversational voice-agent quality
- Choosing a final deployment stack in this document
- Designing rollout or migration work

## Approved Decisions

- Keep this track focused on dedicated STT, not omni/live conversational models
- Remove `qwen3.5-omni-plus-realtime` from the current STT matrix
- Replace Gemini Live with Google Cloud Speech-to-Text `chirp_3`
- Use recorded fixture audio as input and `result.json` transcript text as the reference
- Use WER and latency to final transcript as the primary reported metrics
- Treat partial text, endpointing, and manual finalization as provider capability notes and optional diagnostics, not required shared metrics

## First STT Candidate Matrix

| Candidate ID | Model | Role |
|---|---|---|
| `soniox_baseline` | `stt-rt-v4` | Current production baseline |
| `google_chirp3` | `chirp_3` | Main Google dedicated STT candidate |
| `voxtral_realtime` | `voxtral-mini-transcribe-realtime-2602` | Main Mistral dedicated STT candidate |

## Eval Shape

- Input: recorded fixture audio from `backend/tests/fixtures/`
- Reference text: saved transcript from each fixture `result.json`
- Output per run: final transcript, WER, final latency, and provider status
- Optional output when available: first partial latency, partial count, endpoint/finalization markers, timestamps

## Provider Capability Mapping

The implementation should explicitly record, per provider:

- whether server-side endpoint detection exists
- whether manual finalization / commit exists
- whether partial transcript events exist
- what event marks the final transcript for a segment or session

We do not need every provider to expose the same features. We only need the mapping to be explicit so comparisons are honest.

## Relationship To Extraction Evals

- Item 7 answers which STT path gives the best transcript quality and speed
- Item 6 answers which LLM best converts a finalized transcript into todos
- End-to-end stack trials can happen later after both tracks are independently measured

## Expected Next Deliverables

- an implementation plan
- a fixture manifest
- a provider capability map
- a WER + latency reporting path

## References

- `docs/references/eval-models-and-stacks.md`
- `backend/tests/fixtures/`
- `docs/references/soniox.md`
