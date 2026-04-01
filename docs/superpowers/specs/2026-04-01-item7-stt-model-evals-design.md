# Item 7 Design: STT Model Evals

Scope: define the local STT experiment set, fixture boundary, and evaluation goals for comparing live speech-to-text candidates.

## Why this exists

The project currently depends on Soniox for live speech recognition, but we now have multiple candidate STT directions that could improve colocation, latency, or stack simplicity. We need a dedicated STT eval track because transcript quality problems and extraction quality problems should not be conflated.

## Goals

- Compare live STT candidates against the same recorded audio fixtures
- Keep Soniox as the current baseline
- Evaluate transcript fidelity, stop/finalization correctness, and latency as separate concerns
- Produce a shortlist that can feed later end-to-end stack trials

## Non-goals

- Choosing a final deployment stack in this document
- Scoring downstream todo extraction quality directly here
- Replacing the existing extraction eval harness
- Designing a production rollout plan

## First STT Candidate Matrix

| Candidate ID | Model | Role |
|---|---|---|
| `soniox_baseline` | `stt-rt-v4` | Current production baseline |
| `gemini31_flash_live` | `gemini-3.1-flash-live-preview` | Main Google live STT candidate |
| `qwen_omni_realtime` | `qwen3.5-omni-plus-realtime` | Additional realtime comparison candidate |
| `voxtral_realtime` | `voxtral-mini-transcribe-realtime-2602` | Main Mistral-oriented STT candidate |

## Eval Shape

The STT eval should stay local and replay-driven:

- use recorded audio fixtures as the seed corpus
- feed equivalent audio inputs through each provider-specific realtime or transcription path
- capture finalized transcript output plus any useful intermediate timing signals
- compare candidates on the same cases without changing application behavior between runs

## Fixture Boundary

The initial seed corpus should come from `backend/tests/fixtures/`:

- `audio.pcm` or equivalent audio asset per case
- `result.json` transcript as the transcript-quality reference

The fixture set should remain STT-focused:

- preserve current no-todo and noisy-speech cases
- preserve cases with multiple todos and natural pauses
- add more STT-targeted fixtures later if we need stronger coverage for accents, continuous speech, or correction-heavy utterances

## Primary Evaluation Dimensions

The first STT eval pass should report the following dimensions separately:

- final transcript quality against the saved transcript reference
- stop/finalization correctness
- endpointing behavior and partial transcript usefulness
- latency to first useful transcript
- latency to final transcript
- operational stability across repeated runs

This design intentionally does not collapse STT quality into a single score yet.

## Relationship To Extraction Evals

- STT evals answer which speech model gives us the best transcript behavior
- extraction evals answer which LLM best converts a finalized transcript into todos
- end-to-end stack comparisons can happen later after both tracks have their own evidence

## Expected Next Deliverables

An implementation plan based on this spec should eventually define:

- the STT fixture manifest
- provider adapters or harness entry points
- transcript comparison rules
- latency instrumentation
- a reporting format for repeated runs

## References

- `docs/references/eval-models-and-stacks.md`
- `backend/tests/fixtures/`
- `docs/references/soniox.md`
