# Item 9: STT Benchmark Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-10-item9-stt-benchmark-evals-design.md`

**Goal:** Add a repeatable benchmark-first STT eval harness so we can compare Soniox, Google Cloud Speech-to-Text `chirp_3`, and Voxtral on the same recorded audio fixtures using WER and speed as the main outputs.

**Architecture:** Use Item 7's top-level `evals/` structure for canonical STT datasets and benchmark definitions, and build the STT runner/reporting path on top of that benchmark model rather than a standalone experiment registry. Reuse the provider abstraction from Item 8 so benchmark code can call into production-adjacent STT adapters without putting eval logic back into `backend/app/`.

**Tech Stack:** benchmark-first eval CLI/reporting, backend STT provider abstractions, pytest, Logfire, Soniox realtime STT, Google Cloud Speech-to-Text, Mistral realtime transcription APIs

---

## Scope

This plan covers exactly five deliverables:

1. Create a canonical STT dataset under `evals/datasets/stt/`.
2. Implement deterministic STT evaluator logic for WER, latency, and provider capability notes.
3. Define the first STT benchmark file with explicit provider entries.
4. Wire STT benchmark execution and reporting into the benchmark-first CLI/report flow.
5. Document how to run and compare the STT benchmark locally.

Out of scope for this plan:

- changing the production `/ws` endpoint off Soniox
- downstream todo extraction scoring
- browser microphone end-to-end testing
- automatic fixture capture from live sessions
- conversational voice-agent evals
- collapsing WER and latency into one total score

---

## Implementation Notes

- This plan assumes the Item 8 provider abstraction exists first.
- This plan targets Item 7's top-level `evals/` structure even if a temporary
  bootstrap launcher is needed because the repo's current Python project root is
  still `backend/`.
- `backend/tests/fixtures/` remains the raw evidence source; the canonical STT
  dataset lives under `evals/datasets/stt/`.

---

## File Map

### Evals - New files

| File | Responsibility |
|------|----------------|
| `evals/datasets/stt/stt_transcription_v1.json` | Canonical STT dataset for benchmark runs |
| `evals/benchmarks/stt_transcription_model_matrix_v1.yaml` | Benchmark definition with explicit provider entries |
| `evals/stt/dataset_loader.py` | Load the STT dataset into deterministic benchmark cases |
| `evals/stt/evaluator.py` | Compute WER, latency, and normalized STT result records |
| `evals/stt/provider_capabilities.py` | Static capability map for endpointing, manual finalization, partial text, and final transcript markers |
| `evals/stt/provider_adapters.py` | Benchmark-facing adapters that call into Item 8 provider abstractions |
| `evals/stt/runner.py` | STT-specific benchmark execution logic used by the benchmark CLI/report flow |
| `evals/stt/README.md` | Usage guide for STT benchmark runs and interpretation |

### Evals - Modified files

| File | Change |
|------|--------|
| `evals/cli.py` | Register the STT benchmark with benchmark-first commands |
| `evals/run.py` | Route STT benchmark entries through the STT runner |
| `evals/report.py` | Extend benchmark reporting to include STT WER/latency summaries |

### Tests - New files

| File | Responsibility |
|------|----------------|
| `backend/tests/test_stt_dataset_loader.py` | Verifies the canonical STT dataset loads correctly |
| `backend/tests/test_stt_evaluator.py` | Verifies WER and timing metrics remain deterministic |
| `backend/tests/test_stt_benchmark_manifest.py` | Verifies the STT benchmark file parses into the expected entries |

---

## Task 1: Create the canonical STT dataset

**Files:**
- Add: `evals/datasets/stt/stt_transcription_v1.json`
- Add: `evals/stt/dataset_loader.py`
- Add: `backend/tests/test_stt_dataset_loader.py`

The dataset should be the reviewed source of truth for STT benchmark cases, not
direct directory scanning of raw fixture folders.

- [ ] **Step 1: Write a failing dataset loader test**

Add `backend/tests/test_stt_dataset_loader.py` with a focused case that proves
the loader reads the canonical STT dataset and resolves known audio fixtures.

Suggested case:

```python
def test_load_stt_dataset_returns_known_cases():
    ...
```

- [ ] **Step 2: Run the dataset loader test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_loader.py -v
```

Expected: FAIL because the dataset and loader do not exist yet

- [ ] **Step 3: Create the canonical STT dataset and loader**

Create `evals/datasets/stt/stt_transcription_v1.json` and
`evals/stt/dataset_loader.py`.

Implementation guidance:

- store canonical rows in Item 7 dataset format
- point `input.audio_path` at the existing fixture audio files
- keep provider-specific trace files out of the dataset schema
- preserve no-todo, noisy-speech, and short-utterance cases in the seed set

- [ ] **Step 4: Run the dataset loader test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_loader.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the STT dataset**

```bash
git add evals/datasets/stt/stt_transcription_v1.json evals/stt/dataset_loader.py backend/tests/test_stt_dataset_loader.py
git commit -m "feat: add canonical stt benchmark dataset"
```

---

## Task 2: Implement WER, latency, and provider capability evaluation

**Files:**
- Add: `evals/stt/evaluator.py`
- Add: `evals/stt/provider_capabilities.py`
- Add: `backend/tests/test_stt_evaluator.py`

The first STT benchmark pass should stay deterministic and easy to read.

- [ ] **Step 1: Write failing evaluator tests**

Add `backend/tests/test_stt_evaluator.py` with focused tests that prove:

1. WER is zero for identical transcripts
2. WER reflects word-level insertions, deletions, and substitutions
3. timing fields preserve `None` when a provider does not expose partials
4. capability records remain separate from transcript metrics

Suggested cases:

```python
def test_word_error_rate_is_zero_for_identical_transcripts():
    ...

def test_build_stt_case_result_reports_wer_and_latencies():
    ...
```

- [ ] **Step 2: Run the evaluator tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_stt_evaluator.py -v
```

Expected: FAIL because the evaluator module does not exist yet

- [ ] **Step 3: Implement the evaluator and capability map**

Create `evals/stt/evaluator.py` and `evals/stt/provider_capabilities.py`.

Recommended shape:

```python
def word_error_rate(reference: str, hypothesis: str) -> float:
    ...

def build_stt_case_result(
    *,
    reference_transcript: str,
    predicted_transcript: str,
    first_partial_latency_ms: float | None,
    final_latency_ms: float | None,
    capability_flags: dict[str, bool | str | None],
) -> dict[str, object]:
    ...
```

- [ ] **Step 4: Run the evaluator tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_stt_evaluator.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the evaluator logic**

```bash
git add evals/stt/evaluator.py evals/stt/provider_capabilities.py backend/tests/test_stt_evaluator.py
git commit -m "feat: add stt benchmark evaluator"
```

---

## Task 3: Define the first STT benchmark file

**Files:**
- Add: `evals/benchmarks/stt_transcription_model_matrix_v1.yaml`
- Add: `backend/tests/test_stt_benchmark_manifest.py`

The benchmark file should be the stable source of truth for what is being
compared.

- [ ] **Step 1: Write a failing benchmark manifest test**

Add `backend/tests/test_stt_benchmark_manifest.py` with a focused case that
proves the benchmark parser sees the expected first STT matrix.

Suggested case:

```python
def test_stt_benchmark_manifest_exposes_expected_entries():
    ...
```

- [ ] **Step 2: Run the benchmark manifest test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_manifest.py -v
```

Expected: FAIL because the benchmark file does not exist yet

- [ ] **Step 3: Create the STT benchmark definition**

Create `evals/benchmarks/stt_transcription_model_matrix_v1.yaml` with:

- `benchmark_id`
- dataset path
- `focus: model`
- `headline_metric: word_error_rate`
- explicit entries for Soniox, Chirp 3, and Voxtral
- conservative default `repeat`, `task_retries`, and `max_concurrency`

- [ ] **Step 4: Run the benchmark manifest test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_manifest.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the benchmark file**

```bash
git add evals/benchmarks/stt_transcription_model_matrix_v1.yaml backend/tests/test_stt_benchmark_manifest.py
git commit -m "feat: add stt benchmark definition"
```

---

## Task 4: Wire STT execution and reporting into the benchmark-first flow

**Files:**
- Add: `evals/stt/provider_adapters.py`
- Add: `evals/stt/runner.py`
- Modify: `evals/cli.py`
- Modify: `evals/run.py`
- Modify: `evals/report.py`

This is the heart of the STT benchmark workflow.

- [ ] **Step 1: Write a minimal benchmark CLI smoke test**

Add or extend tests so the benchmark CLI/report path can list or resolve the STT
benchmark by ID.

Suggested behavior:

```bash
cd backend && uv run python ../evals/cli.py benchmark show stt_transcription_model_matrix_v1
```

Expected output includes:

- `soniox_baseline`
- `google_chirp3`
- `voxtral_realtime`

- [ ] **Step 2: Run the smoke check to verify it fails**

Run:

```bash
cd backend && uv run python ../evals/cli.py benchmark show stt_transcription_model_matrix_v1
```

Expected: FAIL because the STT benchmark is not wired into the benchmark flow yet

- [ ] **Step 3: Implement STT adapters and runner**

Create `evals/stt/provider_adapters.py` and `evals/stt/runner.py`.

Implementation guidance:

- reuse the Item 8 provider abstraction rather than opening raw provider
  transports directly from eval code
- normalize provider outputs into one STT benchmark result shape
- continue past single-case provider failures and mark them explicitly
- keep default concurrency conservative for realtime providers

- [ ] **Step 4: Wire benchmark CLI/run/report support**

Update `evals/cli.py`, `evals/run.py`, and `evals/report.py` so:

- `benchmark show <id>` exposes the STT benchmark definition
- `benchmark run <id>` can execute missing STT entries
- `benchmark report <id>` shows current WER/latency state with missing entries
- JSON report output includes full STT configs and history references

- [ ] **Step 5: Run the first smoke checks**

Run:

```bash
cd backend && uv run python ../evals/cli.py benchmark show stt_transcription_model_matrix_v1
cd backend && uv run python ../evals/cli.py benchmark run stt_transcription_model_matrix_v1 --all
```

Expected:

- the benchmark can be shown by ID
- Soniox baseline can run on the canonical dataset
- providers without credentials are skipped clearly rather than crashing

- [ ] **Step 6: Commit the benchmark runner**

```bash
git add evals/stt/provider_adapters.py evals/stt/runner.py evals/cli.py evals/run.py evals/report.py
git commit -m "feat: wire stt benchmark execution"
```

---

## Task 5: Document the STT benchmark workflow

**Files:**
- Add: `evals/stt/README.md`

The goal is to make STT benchmark runs easy to repeat and easy to interpret.

- [ ] **Step 1: Write the README**

Document:

1. what this STT benchmark measures
2. what it does not measure
3. how the canonical dataset is structured and maintained
4. how to show the benchmark definition
5. how to run one benchmark
6. how to interpret WER, latency, and capability fields
7. how to add a new STT benchmark entry safely

- [ ] **Step 2: Add caveats and guardrails**

Document the main traps explicitly:

- the dataset is canonical, but the raw audio still lives under `backend/tests/fixtures/`
- Soniox finalization ordering remains the reference baseline behavior
- WER and final latency are the primary metrics
- provider capability fields explain what is and is not comparable across providers
- STT benchmark results are decision support, not rollout automation

- [ ] **Step 3: Commit the docs**

```bash
git add evals/stt/README.md
git commit -m "docs: add stt benchmark workflow guide"
```

---

## Validation Checklist

- [ ] the canonical STT dataset is git-tracked under `evals/datasets/stt/`
- [ ] the STT benchmark definition is git-tracked under `evals/benchmarks/`
- [ ] WER and timing metrics are deterministic and provider-agnostic
- [ ] provider capability differences are recorded explicitly
- [ ] benchmark-first CLI/reporting works for the STT benchmark
- [ ] skipped entries are reported clearly when provider credentials are missing
- [ ] transcript quality and latency remain separate outputs
- [ ] backend production code stays free of eval-specific logic

---

## Recommended First Execution Order

1. Land Item 8 so the provider seam exists.
2. Create the canonical STT dataset and loader.
3. Implement WER, latency, and provider capability evaluation.
4. Define the benchmark file with explicit entries.
5. Wire STT execution and reporting into the benchmark-first flow.
