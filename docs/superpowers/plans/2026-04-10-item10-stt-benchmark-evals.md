# STT Benchmark Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-10-item10-stt-benchmark-evals-design.md`

**Goal:** Deliver the first dedicated STT benchmark track: curated STT cases promoted from recorded sessions, a benchmark definition for Soniox plus named Voxtral delay profiles, and one runnable comparison report with corpus WER and latency summaries.

**Architecture:** Keep provider transport and stop semantics in `backend/app/`, keep benchmark orchestration in `evals/`, and add an STT family beside the existing extraction and replay families. Phase 1 owns STT case promotion plus hosted-dataset curation, Phase 2 owns STT benchmark definition plus locking, and Phase 3 owns paced STT execution plus reporting.

**Tech Stack:** Python 3.11+, Logfire hosted datasets, benchmark locks under `evals/locks/`, STT adapters in `backend/app/`, pytest, live validation assets under `tests/live/benchmarks/`

---

## Process Rule

This plan follows:

- `docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md`
- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`

Those documents take precedence over the default superpowers plan-writing
guidance for phase shape, acceptance tests, supporting verification, and
completion rules.

## Hard Gate Rule

- Do not begin Phase 2 until all Phase 1 acceptance tests pass.
- Do not begin Phase 3 until all Phase 2 acceptance tests pass.
- If a phase acceptance test is red, the phase is incomplete.
- Supporting verification is required for confidence, but it does not authorize
  moving to the next phase.

## File Map

| File | Responsibility |
|------|----------------|
| `evals/stt/curation.py` | Pure helper logic for promoting recent recordings into `sessions/golden/` and building hosted STT case payloads |
| `scripts/promote_stt_session.py` | Operator-facing CLI/helper entrypoint for STT case promotion |
| `evals/datasets/stt/stt_transcription_seed_v1.json` | Minimal checked-in bootstrap fixture for the STT dataset family; not a live source of truth |
| `scripts/bootstrap_logfire_hosted_datasets.py` | Shared dataset bootstrap conversion for STT hosted cases |
| `evals/models.py` | STT-aware dataset, lock, entry, and report models |
| `evals/storage.py` | STT lock materialization and lock loading |
| `evals/resolution.py` | STT benchmark entry resolution without extraction prompt assumptions |
| `evals/run.py` | Benchmark lock preparation and STT benchmark execution routing |
| `evals/report.py` | STT benchmark reporting with corpus WER, latency summaries, session settings, and capability notes |
| `evals/cli.py` | CLI exposure for STT benchmark lock/run/report flows |
| `evals/benchmarks/stt_transcription_delay_sweep_v1.yaml` | Committed Soniox plus Voxtral delay benchmark definition |
| `evals/stt/dataset_loader.py` | Load locked STT rows into runnable audio cases |
| `evals/stt/evaluator.py` | Corpus WER normalization and latency calculations |
| `evals/stt/provider_adapters.py` | Benchmark-facing provider constructors with entry-local session settings |
| `evals/stt/runner.py` | Real-time-paced STT benchmark execution |
| `evals/stt/README.md` | Operator guidance for STT curation, locking, running, and reading the report |
| `backend/app/live_eval_env.py` | Live validation gating for STT dataset and benchmark assets |
| `backend/tests/test_stt_dataset_curation.py` | STT curation acceptance and helper verification tests |
| `backend/tests/test_hosted_dataset_bootstrap.py` | Shared bootstrap acceptance coverage updated for STT |
| `backend/tests/test_hosted_dataset_locking.py` | Shared locking acceptance coverage updated for STT |
| `backend/tests/test_stt_benchmark_manifest.py` | STT benchmark-definition acceptance and verification tests |
| `backend/tests/test_stt_dataset_loader.py` | STT dataset loader verification |
| `backend/tests/test_stt_evaluator.py` | STT WER and latency verification |
| `backend/tests/test_stt_benchmark_runner.py` | STT execution acceptance and verification tests |
| `backend/tests/test_stt_benchmark_report.py` | STT report acceptance and verification tests |
| `backend/tests/test_item7_benchmark_cli.py` | Shared benchmark CLI verification when STT lock/report commands change the CLI |
| `backend/tests/test_live_eval_env.py` | Live-validation prerequisite checks for STT assets |
| `tests/live/benchmarks/validate_stt_case_promotion.py` | Live acceptance asset for STT promotion plus hosted dataset case creation |
| `tests/live/benchmarks/validate_stt_delay_sweep_report.py` | Live acceptance asset for the end-to-end STT benchmark report |

## Acceptance Coverage Decisions

- `add` `backend/tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload` for the new STT curation contract.
- `update` `backend/tests/test_hosted_dataset_bootstrap.py::test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases` so shared bootstrap coverage proves STT hosted-case acceptance.
- `add` `tests/live/benchmarks/validate_stt_case_promotion.py` for the live STT promotion contract.
- `add` `backend/tests/test_stt_benchmark_manifest.py::test_stt_benchmark_manifest_accepts_named_delay_profiles` for the STT benchmark-definition contract.
- `update` `backend/tests/test_hosted_dataset_locking.py::test_stt_benchmark_lock_preserves_audio_reference_rows` so shared locking coverage proves STT lock preservation.
- `add` `backend/tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency` for the STT execution contract.
- `add` `backend/tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles` for the STT reporting contract.
- `add` `tests/live/benchmarks/validate_stt_delay_sweep_report.py` for the live end-to-end STT comparison contract.

## Phase 1: Curate STT Dataset

**Behavioral delta:** A chosen recent recording can be promoted into a durable
STT case under `sessions/golden/`, turned into a hosted STT case payload, and
accepted by the shared dataset bootstrap flow without extraction-shaped fields.

### Task 1: Add the STT promotion helper and local STT case curation seam

**Files:**
- Create: `evals/stt/curation.py`
- Create: `scripts/promote_stt_session.py`
- Create: `backend/tests/test_stt_dataset_curation.py`
- Modify: `backend/app/live_eval_env.py`
- Modify: `backend/tests/test_live_eval_env.py`

- [ ] **Step 1: Write the failing local curation acceptance test**

Add `backend/tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload`.

The test should:

- create one fake recent session directory with `audio.pcm`, `result.json`, and
  one provider trace file
- run the pure promotion helper with:
  - a reviewed transcript
  - a target `case-id`
  - a target hosted dataset identifier
- assert:
  - `sessions/golden/<case-id>/audio.pcm` exists
  - the hosted STT case payload points to that repo-relative audio path
  - the hosted STT case payload contains the reviewed transcript and audio
    metadata

- [ ] **Step 2: Run the acceptance test and confirm it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload -v
```

Expected: FAIL because the STT promotion helper does not exist yet.

- [ ] **Step 3: Implement the pure curation helper and the operator entrypoint**

Implement:

- `evals/stt/curation.py` for:
  - recent-session validation
  - default copy into `sessions/golden/<case-id>/`
  - hosted STT case payload construction
  - case-id normalization and transcript validation
- `scripts/promote_stt_session.py` as the thin operator-facing wrapper around
  the pure helper

Implementation rules:

- the helper's durable outputs are `sessions/golden/` and the hosted case
  payload
- do not update a checked-in repo dataset file as part of normal promotion
- keep the reviewed transcript operator-supplied

- [ ] **Step 4: Re-run the local curation acceptance test**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload -v
```

Expected: PASS

### Task 2: Teach the shared hosted-dataset bootstrap flow about STT cases

**Files:**
- Create: `evals/datasets/stt/stt_transcription_seed_v1.json`
- Modify: `scripts/bootstrap_logfire_hosted_datasets.py`
- Modify: `backend/tests/test_hosted_dataset_bootstrap.py`
- Create: `tests/live/benchmarks/validate_stt_case_promotion.py`

- [ ] **Step 1: Write the failing shared bootstrap acceptance update**

Update `backend/tests/test_hosted_dataset_bootstrap.py` with
`test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases`.

The test should assert that one STT row becomes one hosted case with:

- `inputs` carrying the audio reference and audio metadata
- `expected_output.transcript`
- no extraction-style `todos`

- [ ] **Step 2: Run the bootstrap acceptance test and confirm it fails**

Run:

```bash
cd backend && uv run pytest tests/test_hosted_dataset_bootstrap.py::test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases -v
```

Expected: FAIL because bootstrap still assumes extraction-shaped rows.

- [ ] **Step 3: Implement STT bootstrap support and a minimal checked-in STT dataset fixture**

Update:

- `scripts/bootstrap_logfire_hosted_datasets.py` so STT rows convert to hosted
  cases as `audio -> transcript`
- `evals/datasets/stt/stt_transcription_seed_v1.json` as a minimal bootstrap
  fixture for the STT dataset family

Keep this file a bootstrap fixture only, not a second live source of truth.

- [ ] **Step 4: Re-run the shared bootstrap acceptance test**

Run:

```bash
cd backend && uv run pytest tests/test_hosted_dataset_bootstrap.py::test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases -v
```

Expected: PASS

- [ ] **Step 5: Add the live STT promotion acceptance asset**

Create `tests/live/benchmarks/validate_stt_case_promotion.py`.

The asset should:

- check STT promotion prerequisites through `backend/app/live_eval_env.py`
- create or choose one temporary hosted dataset target
- run the promotion flow on one recent session fixture
- assert the hosted case keeps the same case id, audio reference, transcript,
  and metadata
- print `PASS`, `FAIL`, or `WARN`

- [ ] **Step 6: Run the Phase 1 acceptance tests**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload -v
cd backend && uv run pytest tests/test_hosted_dataset_bootstrap.py::test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases -v
cd backend && uv run python ../tests/live/benchmarks/validate_stt_case_promotion.py
```

Expected:

- both pytest acceptance tests pass
- the live asset prints `PASS`, or `WARN` with an explicit credential or
  environment reason

- [ ] **Step 7: Run supporting verification**

Run:

```bash
cd backend && uv run pytest tests/test_live_eval_env.py tests/test_logfire_hosted_datasets.py -v
git diff --check -- evals/stt/curation.py scripts/promote_stt_session.py scripts/bootstrap_logfire_hosted_datasets.py evals/datasets/stt/stt_transcription_seed_v1.json backend/tests/test_stt_dataset_curation.py backend/tests/test_hosted_dataset_bootstrap.py tests/live/benchmarks/validate_stt_case_promotion.py backend/app/live_eval_env.py backend/tests/test_live_eval_env.py
```

Expected: PASS

### Phase 1 checkpoint

- [ ] Confirm all Phase 1 acceptance tests pass before starting Phase 2

## Phase 2: Define STT Benchmark

**Behavioral delta:** A developer can define one STT benchmark on the curated
STT dataset with Soniox plus named Voxtral delay profiles, then prepare that
benchmark for execution as one lock artifact that still refers to the same
curated STT cases.

### Task 3: Generalize benchmark models, resolution, and locking for `dataset_family: stt`

**Files:**
- Modify: `evals/models.py`
- Modify: `evals/storage.py`
- Modify: `evals/resolution.py`
- Modify: `backend/tests/test_hosted_dataset_locking.py`
- Create: `backend/tests/test_stt_benchmark_manifest.py`

- [ ] **Step 1: Write the failing manifest acceptance test**

Create
`backend/tests/test_stt_benchmark_manifest.py::test_stt_benchmark_manifest_accepts_named_delay_profiles`.

The test should load one STT benchmark definition and assert that:

- it is `dataset_family: stt`
- it contains `soniox_baseline` plus the named Voxtral delay profiles
- each Voxtral entry carries an explicit `target_streaming_delay_ms`
- it does not require extraction-style prompt configuration

- [ ] **Step 2: Write the failing locking acceptance update**

Update
`backend/tests/test_hosted_dataset_locking.py::test_stt_benchmark_lock_preserves_audio_reference_rows`
so it exercises the public benchmark lock-preparation path for one STT
benchmark and asserts the resulting lock preserves:

- case ids
- repo-relative audio references
- reviewed transcripts
- metadata

- [ ] **Step 3: Run the Phase 2 acceptance tests and confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_manifest.py::test_stt_benchmark_manifest_accepts_named_delay_profiles -v
cd backend && uv run pytest tests/test_hosted_dataset_locking.py::test_stt_benchmark_lock_preserves_audio_reference_rows -v
```

Expected: FAIL because the benchmark stack still assumes extraction and replay.

- [ ] **Step 4: Implement STT-aware models, lock materialization, and entry resolution**

Update:

- `evals/models.py` so STT dataset rows, resolved configs, and report rows have
  the fields they need without extraction-only assumptions
- `evals/storage.py` so STT hosted cases lock as `audio -> transcript` rows
- `evals/resolution.py` so STT benchmark entries resolve without
  `prompt_version`, and keep session settings under STT entry config

- [ ] **Step 5: Re-run the Phase 2 acceptance tests**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_manifest.py::test_stt_benchmark_manifest_accepts_named_delay_profiles -v
cd backend && uv run pytest tests/test_hosted_dataset_locking.py::test_stt_benchmark_lock_preserves_audio_reference_rows -v
```

Expected: PASS

### Task 4: Add the STT benchmark definition and a lock-only preparation command

**Files:**
- Create: `evals/benchmarks/stt_transcription_delay_sweep_v1.yaml`
- Modify: `evals/run.py`
- Modify: `evals/cli.py`
- Modify: `backend/tests/test_item7_benchmark_cli.py`

- [ ] **Step 1: Add the committed STT benchmark definition**

Create `evals/benchmarks/stt_transcription_delay_sweep_v1.yaml` with:

- `dataset_family: stt`
- `focus: session_profile`
- `headline_metric: corpus_wer`
- `soniox_baseline`
- two or three named Voxtral delay profiles with explicit
  `target_streaming_delay_ms`

- [ ] **Step 2: Add a lock-only benchmark preparation path**

Implement a benchmark lock/preparation command in `evals/run.py` and expose it
through `evals/cli.py` so a developer can prepare the STT benchmark for
execution without also running providers.

- [ ] **Step 3: Add shared CLI verification for the new lock command**

Update `backend/tests/test_item7_benchmark_cli.py` or another shared CLI test
file so the CLI verifies:

- the new lock command exists
- it writes a lock artifact for an STT benchmark
- it does not require extraction-style entry config

This CLI test remains supporting verification because the behavioral contract
for Phase 2 is already covered by the manifest acceptance test plus the public
lock-preparation acceptance test above.

- [ ] **Step 4: Run supporting verification**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_cli.py tests/test_models.py -v
git diff --check -- evals/models.py evals/storage.py evals/resolution.py evals/run.py evals/cli.py evals/benchmarks/stt_transcription_delay_sweep_v1.yaml backend/tests/test_stt_benchmark_manifest.py backend/tests/test_hosted_dataset_locking.py backend/tests/test_item7_benchmark_cli.py
```

Expected: PASS

### Phase 2 checkpoint

- [ ] Confirm all Phase 2 acceptance tests pass before starting Phase 3

## Phase 3: Run STT Comparison

**Behavioral delta:** A developer can run the STT benchmark and get one
comparison report for Soniox and the named Voxtral delay profiles on the same
STT cases, with `corpus_wer`, latency summaries, completed versus failed case
counts, explicit `session_settings`, and provider capability notes.

### Task 5: Implement paced STT benchmark execution

**Files:**
- Create: `evals/stt/dataset_loader.py`
- Create: `evals/stt/evaluator.py`
- Create: `evals/stt/provider_adapters.py`
- Create: `evals/stt/runner.py`
- Modify: `evals/run.py`
- Create: `backend/tests/test_stt_dataset_loader.py`
- Create: `backend/tests/test_stt_evaluator.py`
- Create: `backend/tests/test_stt_benchmark_runner.py`

- [ ] **Step 1: Write the failing STT runner acceptance test**

Create
`backend/tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency`.

The test should:

- run one locked STT benchmark through fake Soniox and Voxtral sessions
- use the real-time pacing contract from the spec
- assert the results include, for the same case ids:
  - transcript text
  - transcript quality metric inputs
  - `first_text_latency_ms`
  - `final_transcript_latency_ms`
  - `final_transcript_source`

- [ ] **Step 2: Run the runner acceptance test and confirm it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency -v
```

Expected: FAIL because no STT runner exists yet.

- [ ] **Step 3: Implement the STT loader, evaluator, provider adapters, and runner**

Implement:

- `evals/stt/dataset_loader.py` to load locked STT audio-reference rows
- `evals/stt/evaluator.py` for:
  - normalized corpus-WER inputs
  - `first_text_latency_ms`
  - `final_transcript_latency_ms`
  - failure accounting
- `evals/stt/provider_adapters.py` for Soniox and Voxtral benchmark session
  construction with entry-local session settings
- `evals/stt/runner.py` for `100 ms` paced chunk sending and immediate
  finalize/end-stream after the last chunk
- `evals/run.py` to dispatch STT benchmark entries through the STT runner

- [ ] **Step 4: Re-run the runner acceptance test**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency -v
```

Expected: PASS

### Task 6: Add STT reporting and the live end-to-end validation

**Files:**
- Modify: `evals/report.py`
- Modify: `backend/app/live_eval_env.py`
- Modify: `backend/tests/test_live_eval_env.py`
- Create: `backend/tests/test_stt_benchmark_report.py`
- Create: `tests/live/benchmarks/validate_stt_delay_sweep_report.py`
- Create: `evals/stt/README.md`

- [ ] **Step 1: Write the failing STT report acceptance test**

Create
`backend/tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles`.

The test should render one multi-entry STT benchmark result and assert the
report shows, for each entry:

- profile name
- `corpus_wer`
- latency summaries
- completed versus failed case counts
- explicit `session_settings`
- provider capability notes

- [ ] **Step 2: Run the report acceptance test and confirm it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles -v
```

Expected: FAIL because generic benchmark reporting does not yet surface STT
summary fields.

- [ ] **Step 3: Implement STT report shaping and live-validation prerequisites**

Update:

- `evals/report.py` so STT reports surface:
  - `corpus_wer`
  - `median_first_text_latency_ms`
  - `median_final_transcript_latency_ms`
  - `p95_final_transcript_latency_ms`
  - completed and failed case counts
  - explicit `session_settings`
  - provider capability notes
- `backend/app/live_eval_env.py` and `backend/tests/test_live_eval_env.py` so
  STT live assets clearly report the Soniox, Mistral, and Logfire prerequisites

- [ ] **Step 4: Re-run the report acceptance test**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles -v
```

Expected: PASS

- [ ] **Step 5: Add the live end-to-end STT report asset**

Create `tests/live/benchmarks/validate_stt_delay_sweep_report.py`.

The asset should:

- check STT benchmark live prerequisites
- prepare or reuse a temporary STT hosted dataset
- prepare the STT benchmark lock
- run the committed STT benchmark
- render the report
- assert the report contains Soniox plus the named Voxtral profiles with:
  - `corpus_wer`
  - latency summaries
  - completed versus failed case counts
  - `session_settings`
  - provider capability notes
- print `PASS`, `FAIL`, or `WARN`

- [ ] **Step 6: Document the operator workflow**

Create `evals/stt/README.md` covering:

- STT case promotion from `sessions/recent/` to `sessions/golden/`
- hosted dataset curation versus benchmark locks
- the `100 ms` paced streaming contract
- `corpus_wer` and latency summary definitions
- how to run the benchmark and read the report

- [ ] **Step 7: Run the Phase 3 acceptance tests**

Run:

```bash
cd backend && uv run pytest tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency -v
cd backend && uv run pytest tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles -v
cd backend && uv run python ../tests/live/benchmarks/validate_stt_delay_sweep_report.py
```

Expected:

- both pytest acceptance tests pass
- the live asset prints `PASS`, or `WARN` with an explicit credential or
  environment reason

- [ ] **Step 8: Run supporting verification**

Run:

```bash
cd backend && uv run pytest tests/test_stt_dataset_loader.py tests/test_stt_evaluator.py tests/test_live_eval_env.py -v
git diff --check -- evals/stt/dataset_loader.py evals/stt/evaluator.py evals/stt/provider_adapters.py evals/stt/runner.py evals/report.py backend/tests/test_stt_dataset_loader.py backend/tests/test_stt_evaluator.py backend/tests/test_stt_benchmark_runner.py backend/tests/test_stt_benchmark_report.py tests/live/benchmarks/validate_stt_delay_sweep_report.py evals/stt/README.md backend/app/live_eval_env.py backend/tests/test_live_eval_env.py
```

Expected: PASS

### Phase 3 checkpoint

- [ ] Confirm all Phase 3 acceptance tests pass before declaring Item 10 complete

## Final Verification Checklist

- [ ] STT case promotion writes `sessions/golden/` and hosted STT case payloads without creating a second live repo dataset source
- [ ] `dataset_family: stt` is supported through bootstrap, lock preparation, execution, and reporting
- [ ] the committed benchmark manifest contains only Soniox plus explicit Voxtral delay entries
- [ ] no committed STT benchmark entry relies on Mistral's undocumented default delay
- [ ] the paced playback contract uses `100 ms` chunks and immediate finalize/end-stream after the last chunk
- [ ] reports surface `corpus_wer`, latency summaries, completed versus failed case counts, `session_settings`, and provider capability notes
- [ ] every phase names exact acceptance tests and commands
