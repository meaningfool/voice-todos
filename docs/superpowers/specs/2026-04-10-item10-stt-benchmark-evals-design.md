# Item 10 Design: STT Benchmark Evals

Scope: define the first dedicated STT benchmark track after the Item 8 and
Item 9 refactors, using the current `SttSession` seam to compare Soniox against
an explicit Voxtral delay sweep on the same prerecorded audio corpus.

## Why this exists

The original Item 10 draft is now stale in three important ways:

- it assumed local canonical datasets instead of the hosted-dataset plus lock
  model introduced later
- it assumed a broader first provider matrix than the codebase currently
  supports cleanly
- it predated the actual `SttSession` seam and the shipped Voxtral adapter

The repo now has:

- `backend/app/stt.py` with a provider-neutral session contract
- `backend/app/stt_soniox.py` and `backend/app/stt_mistral.py`
- `backend/app/stt_factory.py` for production provider selection
- benchmark locking and hosted-dataset workflows under `evals/`

That means the next useful STT benchmark is narrower and more concrete than the
first draft:

- Soniox stays as the baseline
- Voxtral becomes the comparison target
- the initial variable is `target_streaming_delay_ms`, because that is the
  provider-specific latency control we already know the adapter can pass

## Goals

- compare Soniox and Voxtral on the same locked audio dataset
- start with Soniox plus two or three explicit Voxtral delay settings
- measure transcript quality with WER against human-reviewed reference
  transcripts
- measure speed with at least:
  - time to first emitted transcript text
  - time to authoritative final transcript
- record the provider semantics that matter for interpretation:
  - finalization boundary support
  - endpoint boundary support
  - final transcript source used on stop
  - benchmark entry session settings such as
    `target_streaming_delay_ms`
- keep benchmark orchestration in `evals/` and provider transport logic in
  `backend/app/`
- align the STT benchmark with the hosted-dataset locking contract from
  Item 7.5

## Non-goals

- changing the production `/ws` default provider away from Soniox
- adding Google Chirp to the first committed benchmark matrix
- benchmarking downstream todo extraction quality in this item
- redesigning the transcript UI or extraction policy
- requiring Logfire hosted datasets to store raw audio bytes directly
- relying on Voxtral's undocumented provider default streaming delay for
  committed benchmark comparisons
- collapsing WER and latency into one opaque total score

## Current State Summary

The current repo shape matters for this spec:

- `backend/app/stt.py` defines the app-level STT seam:
  - `SttSession`
  - `SttEvent`
  - `SttCapabilities`
- `backend/app/stt_soniox.py` preserves Soniox's real stop contract:
  - request final transcript via `finalize`
  - end stream separately
  - wait for `<fin>`
- `backend/app/stt_mistral.py` exposes
  `connect_mistral(..., target_streaming_delay_ms: int | None = None)`
  and resolves final transcript readiness on `transcription.done`
- `backend/app/stt_factory.py` is production-oriented and currently does not
  support per-entry benchmark session settings
- `evals/models.py`, `evals/storage.py`, and `evals/hosted_datasets.py` are
  still extraction-shaped in important places:
  - hosted datasets are benchmark-owned
  - lock files live under `evals/locks/`
  - dataset serialization currently assumes extraction-style `todos`
  - benchmark resolution currently assumes prompt-bearing extraction entries

The existing code therefore already proves the transport seam, but not the STT
benchmark contract above it.

## Approved Decisions

### 1. The first benchmark matrix is Soniox plus an explicit Voxtral delay sweep

The initial committed matrix should be:

| Entry ID | Provider | Model | Role |
|---|---|---|---|
| `soniox_baseline` | Soniox | `stt-rt-v4` | Current production baseline |
| `voxtral_delay_150` | Mistral | `voxtral-mini-transcribe-realtime-2602` | Low-delay candidate |
| `voxtral_delay_300` | Mistral | `voxtral-mini-transcribe-realtime-2602` | Mid-delay candidate |
| `voxtral_delay_600` | Mistral | `voxtral-mini-transcribe-realtime-2602` | Higher-delay candidate |

If implementation or live-provider behavior forces the sweep down to two
Voxtral settings instead of three, that is acceptable, but every committed
Voxtral entry must carry an explicit `target_streaming_delay_ms` value.

Do not create a committed benchmark entry that leaves the delay unset and
inherits Mistral's undocumented default. That can be explored in a one-off
probe, but it is not a stable benchmark coordinate.

Google Chirp can return later, but only after this narrower benchmark track is
working and accepted.

### 2. Benchmark entries must own provider session settings

An env var such as `MISTRAL_TARGET_STREAMING_DELAY_MS` may still be a useful
product follow-up, but it is not sufficient for Item 10.

Reason:

- production config gives one global value
- the benchmark needs multiple Voxtral delay values in one matrix

Item 10 therefore needs a benchmark-facing configuration seam that can express
entry-local session settings such as:

- `target_streaming_delay_ms`

Recommended benchmark entry shape:

```yaml
benchmark_id: stt_transcription_delay_sweep_v1
hosted_dataset: <dataset_id>
dataset_family: stt
focus: session_profile
headline_metric: corpus_wer
repeat: 1
task_retries: 0
max_concurrency: 1
entries:
  - id: soniox_baseline
    label: Soniox / stt-rt-v4
    config:
      provider: soniox
      model: stt-rt-v4
      session_settings: {}

  - id: voxtral_delay_300
    label: Voxtral / 300 ms
    config:
      provider: mistral
      model: voxtral-mini-transcribe-realtime-2602
      session_settings:
        target_streaming_delay_ms: 300
```

This is intentionally different from the extraction benchmark entry shape.
STT entries vary on provider session behavior, not prompt version.

### 3. The STT dataset contract is hosted for curation, locked for execution, and audio-by-reference

Item 10 should follow Item 7.5's dataset model:

- the editable dataset is a hosted dataset in Logfire
- the execution input is the local lock artifact under `evals/locks/`

For STT specifically, the dataset row must describe audio by reference rather
than assume raw bytes are embedded in the dataset.

Recommended row shape:

```json
{
  "id": "stop-the-button",
  "input": {
    "audio_fixture_path": "sessions/golden/stop-the-button/audio.pcm",
    "audio_format": "pcm_s16le",
    "sample_rate_hz": 16000,
    "num_channels": 1
  },
  "expected_output": {
    "transcript": "Stop"
  },
  "metadata": {
    "source_fixture": "stop-the-button",
    "reference_source": "human_reviewed",
    "tags": ["short_utterance", "stop_path"]
  }
}
```

Important rules:

- a repo-reviewed seed dataset under `evals/datasets/stt/` is still useful for
  bootstrap, but the hosted dataset becomes the canonical curation surface once
  uploaded
- `sessions/golden/` is the only durable repo audio library for admitted STT
  benchmark cases
- the lock artifact must preserve the STT row contract rather than collapse it
  into extraction-style `todos`
- trying direct audio-byte storage in Logfire is allowed as a small probe, but
  the benchmark must not depend on that working

### 4. STT cases should be promoted from local session captures into tracked golden recordings

The repo already has a local session-recording workflow:

- `sessions/recent/` is the local inbox for newly recorded sessions
- each recorded session currently contains:
  - `audio.pcm`
  - `result.json`
  - one provider trace file such as `soniox.jsonl`

For STT eval curation, these recent sessions should not become the long-term
benchmark source of truth directly.

Instead, the intended promotion flow is:

1. record locally into `sessions/recent/`
2. review the captured recording
3. promote the chosen recording into a tracked repo path under
   `sessions/golden/<case-id>/`
4. define the STT dataset row against that promoted recording using a
   repo-relative audio path
5. write the reviewed reference transcript into the dataset row

Important constraints:

- `sessions/recent/` remains ignored and ephemeral
- `sessions/golden/` is committed and is the durable audio library for STT evals
- provider trace files remain useful evidence and replay material, but they are
  not the canonical STT reference transcript
- the reference transcript for STT evals is the reviewed transcript stored in
  the dataset row

Item 10 should add a helper for this promotion flow. The helper should:

- take:
  - one chosen recording under `sessions/recent/`
  - one reviewed reference transcript supplied by the operator
  - one target `case-id`
  - one target hosted dataset identifier
- copy the chosen recording into `sessions/golden/<case-id>/` by default
- prepare the hosted STT case payload for that promoted recording
- create or update the corresponding hosted dataset case in Logfire

This does not need to hide the human review step. The reviewed reference
transcript is still supplied by the operator. The automation is about turning a
chosen recent recording plus reviewed transcript into the durable local and
hosted STT case shape without hand-editing multiple files.

The helper should not make the repo seed dataset a second live source of truth.
Its durable outputs are:

- the promoted recording under `sessions/golden/`
- the hosted dataset case used for curation

If the repo later needs a checked-in dataset snapshot, that should be a
separate export or sync step rather than part of the promotion helper's normal
write path.

### 5. Reference transcripts must be human-reviewed, not inherited blindly from `result.json`

The existing fixture transcripts are useful hints, but they are not guaranteed
ground truth. Many of them are provider outputs captured from the current app
behavior.

That is not sufficient for a fair STT benchmark because it would bias the
evaluation toward whichever provider produced the original saved transcript.

Dataset curation rules:

- seed from promoted recordings under `sessions/golden/`
- manually review and correct the reference transcript for every admitted STT
  benchmark case
- do not treat current Soniox output as the canonical truth just because it is
  already in the repo
- exclude fixtures that appear truncated or whose intended spoken text cannot be
  verified yet

Recommended seed set for the first pass is the subset of promoted recordings
that clearly covers:

- very short stop-path speech
- finalization-at-stop behavior
- longer continuous speech
- disfluencies and proper nouns
- multi-item dictation

Examples likely to be useful first:

- `stop-the-button`
- `stop-final-sweep-single-todo`
- `continuous-speech`
- `call-mom-memo-supplier`
- `text-is-captured`
- `while-speaking-two-todos`

Examples to keep out until verified:

- obviously truncated fixture captures
- any fixture whose saved transcript is known to be approximate rather than
  reference-quality

### 6. Item 10 should build on the app STT seam, but not through `/ws`

The benchmark should reuse the provider transport and stop semantics already
captured in:

- `backend/app/stt.py`
- `backend/app/stt_soniox.py`
- `backend/app/stt_mistral.py`

But the benchmark should not drive providers through the browser websocket app.

Reason:

- `/ws` adds browser orchestration and extraction behavior that are not part of
  the STT benchmark objective
- the benchmark needs per-entry provider settings that do not map cleanly onto
  the production settings object

The benchmark runner should therefore:

- load one locked audio case
- open a provider session using the app-level provider seam
- stream the prerecorded PCM audio in deterministic real-time-paced chunks
- timestamp transcript events locally against the first audio sent
- derive the final transcript from the provider's authoritative stop path

The playback contract should be explicit:

- split PCM into fixed-duration chunks, initially `100 ms`
- send one chunk every `100 ms` to simulate live capture pacing
- define `t0` as the send time of the first audio chunk
- define `first_text_latency_ms` as the first transcript-bearing event observed
  after `t0`
- define `final_transcript_latency_ms` as the authoritative final transcript
  readiness event observed after `t0`
- trigger the provider's finalize or end-of-stream path immediately after the
  last paced chunk is sent; do not add extra post-audio delay in the benchmark

This is intended to approximate live STT timing for provider comparison, not to
measure full browser-to-UI latency in production.

This keeps the dependency rule intact:

- `evals` may depend on `backend/app`
- `backend/app` must not depend on `evals`

### 7. The current eval dataset and benchmark models must be generalized for `dataset_family: stt`

The current benchmark stack still assumes extraction and replay in a few key
places:

- `evals/models.DatasetRow.expected_output` is too extraction-shaped
- `evals/storage.lock_from_exported_dataset(...)` currently hard-codes
  extraction-style `todos`
- `evals/resolution.resolve_entry_config(...)` assumes prompt-bearing
  extraction entries

Item 10 should not work around that by distorting STT rows into fake todo
structures.

Instead, the benchmark stack should become family-aware in the places that need
it:

- dataset serialization and hosted-dataset round-tripping
- lock-file materialization
- benchmark entry resolution
- result/report shaping

Extraction and replay can keep their current family-specific conventions, but
STT must be able to express:

- audio reference inputs
- transcript reference outputs
- session-setting-bearing benchmark entries

### 8. Reporting must make quality, speed, and session settings legible side by side

Per-case STT results should include at least:

- `reference_transcript`
- `predicted_transcript`
- `word_error_rate`
- `first_text_latency_ms`
- `final_transcript_latency_ms`
- `final_transcript_source`
- `session_settings`
- provider capability notes
- status and failure detail when a case did not complete

Metric rules:

- compute transcript quality as corpus WER over normalized text, not as a plain
  average of per-case WER values
- normalize reference and predicted text by lowercasing, collapsing repeated
  whitespace, and stripping punctuation-only differences before WER
- do not add number-word normalization in the first committed version; treat
  `"2"` and `"two"` as different tokens until that rule is intentionally added
- treat `first_text_latency_ms` as the first transcript-bearing event regardless
  of whether the provider calls it provisional or final
- keep `final_transcript_latency_ms` separate from `first_text_latency_ms`
  rather than collapsing them
- report failures explicitly and exclude failed cases from latency aggregates
  while showing per-entry completed-case counts alongside the aggregates

The benchmark report should show:

- headline `corpus_wer`
- `median_first_text_latency_ms`
- `median_final_transcript_latency_ms`
- `p95_final_transcript_latency_ms`
- the explicit delay value for each Voxtral entry
- completed-case counts and failed-case counts for each entry
- stale and missing-entry state through the existing benchmark model

Do not hide delay configuration or capability differences in footnotes.

## Phased Rollout

This item should be phased around behavioral deltas, not implementation chunks.
The next phase must not begin until the current phase's acceptance criteria are
implemented and verified.

### Phase 1: Curate STT Dataset

Objective:

- make curated STT cases first-class dataset cases in the shared benchmark
  system

Behavioral delta:

- a chosen recent recording can be promoted into a first-class STT case in one
  automated flow
- that flow creates the durable `sessions/golden/` recording and the shared
  STT dataset case shape
- the shared dataset flow preserves that STT case shape through curation and
  dataset bootstrap

Non-goals:

- defining STT benchmark entries
- running STT provider comparisons

Acceptance criteria:

- A developer can run one promotion flow on a chosen recent recording and
  create a named STT case under `sessions/golden/`.
- That STT case contains an audio reference, audio format metadata, and a
  reviewed reference transcript.
- The same promotion flow can create or update the corresponding hosted dataset
  case for STT curation.
- The shared dataset flow accepts that STT case without forcing
  extraction-shaped fields or provider-specific transcript semantics into the
  case definition.

Acceptance tests:

- `add`
  `backend/tests/test_stt_dataset_curation.py::test_promote_recent_session_creates_golden_case_and_hosted_case_payload`
  to start from one recorded session under `sessions/recent/`, run the
  promotion helper with a reviewed transcript, and assert that:
  - `sessions/golden/<case-id>/audio.pcm` exists
  - the hosted case payload points to that repo-relative audio path
  - the hosted case payload stores the reviewed transcript and audio metadata
- `update`
  `backend/tests/test_hosted_dataset_bootstrap.py::test_bootstrap_converts_stt_audio_reference_rows_to_logfire_cases`
  to bootstrap one promoted STT case and assert the hosted dataset payload keeps
  the `audio -> transcript` shape without extraction-style `todos`
- `add` `tests/live/benchmarks/validate_stt_case_promotion.py`
  to run the promotion flow against a real hosted dataset target and assert the
  resulting hosted case keeps the same case id, audio reference, transcript,
  and metadata

Supporting verification:

- serializer and model tests for `dataset_family: stt`
- bootstrap-script tests for STT row conversion
- lower-level helper tests for transcript validation and case-id normalization

Phase boundary rule:

- do not define or execute an STT benchmark until the shared dataset flow
  accepts curated STT cases cleanly

### Phase 2: Define STT Benchmark

Objective:

- make the shared benchmark system accept the intended Soniox-versus-Voxtral
  benchmark definition

Behavioral delta:

- a benchmark can be declared on the curated STT dataset
- benchmark entries can name STT provider profiles rather than extraction
  prompt variants
- the full intended Voxtral delay sweep is represented explicitly in the
  benchmark definition
- benchmark-owned locking now preserves the STT case unchanged when the
  benchmark is prepared for execution

Non-goals:

- executing the benchmark
- reporting benchmark results

Acceptance criteria:

- A developer can define one STT benchmark on the curated STT dataset with
  `soniox_baseline` and the named Voxtral delay profiles.
- A developer can prepare that benchmark for execution and get one lock
  artifact that still refers to the same curated STT cases.

Acceptance tests:

- `add`
  `backend/tests/test_stt_benchmark_manifest.py::test_stt_benchmark_manifest_accepts_named_delay_profiles`
  to load one STT benchmark definition and assert that:
  - it contains `soniox_baseline` plus the named Voxtral delay profiles
  - each Voxtral entry carries an explicit `target_streaming_delay_ms`
  - the manifest resolves as `dataset_family: stt` rather than an
    extraction-style benchmark
- `update`
  `backend/tests/test_hosted_dataset_locking.py::test_stt_benchmark_lock_preserves_audio_reference_rows`
  to build a lock artifact from the curated STT dataset and assert it preserves
  the same case ids, audio references, reviewed transcripts, and metadata
  across locking

Supporting verification:

- resolution tests for `dataset_family: stt`
- benchmark model tests for STT entry config shape
- validation tests for explicit `target_streaming_delay_ms` mapping

Phase boundary rule:

- do not treat STT as an executable benchmark family until the shared benchmark
  system accepts the STT benchmark definition and its explicit delay profiles

### Phase 3: Run STT Comparison

Objective:

- execute the STT benchmark and produce a readable Soniox-versus-Voxtral
  comparison

Behavioral delta:

- the shared benchmark flow can run the STT benchmark on the curated STT cases
- one benchmark result compares Soniox against the named Voxtral delay profiles
- the comparison makes transcript quality and latency legible enough to judge
  the tradeoff

Non-goals:

- Google Chirp support
- automatic binary-audio hosting in Logfire
- product rollout decisions

Acceptance criteria:

- A developer can run the STT benchmark and get one comparison report for
  Soniox and the named Voxtral delay profiles on the same STT cases.
- That report shows, for each entry, the profile name, `corpus_wer`, the
  latency summaries, completed versus failed case counts, the explicit
  `session_settings`, and provider capability notes.

Acceptance tests:

- `add`
  `backend/tests/test_stt_benchmark_runner.py::test_stt_benchmark_run_records_transcript_quality_and_latency`
  to run one locked STT benchmark through fake Soniox and Voxtral sessions and
  assert the result records comparable per-entry outputs for the same case ids,
  including transcript text, quality metric, and latency fields
- `add`
  `backend/tests/test_stt_benchmark_report.py::test_stt_benchmark_report_surfaces_delay_profiles`
  to render a multi-entry STT benchmark result and assert the report shows each
  entry's profile name, `corpus_wer`, latency summaries, and completed versus
  failed case counts, plus the explicit `session_settings` and provider
  capability notes, in one comparison view
- `add` `tests/live/benchmarks/validate_stt_delay_sweep_report.py`
  to run the committed STT benchmark end to end and assert the produced report
  includes Soniox plus the named Voxtral profiles with `corpus_wer`,
  latency summaries, completed versus failed case counts, explicit
  `session_settings`, and provider capability notes

Supporting verification:

- WER unit tests
- event-timing tests
- provider-capability mapping tests
- live-eval environment tests updated for Soniox and Mistral credential checks

Phase boundary rule:

- do not widen the provider set or benchmark objective until the shared
  benchmark flow can run the STT comparison and report it readably

## Explicit Acceptance-Test Decisions

To keep the acceptance surface small and current, Item 10 should make these
explicit decisions instead of adding ad hoc tests:

- `update` hosted-dataset bootstrap coverage so curated STT cases are accepted
  by the shared dataset flow without a duplicate acceptance copy
- `add` one acceptance test for promoting a chosen recent recording into a
  durable `sessions/golden/` STT case plus hosted-case payload
- `add` one live acceptance asset for creating or updating the corresponding
  hosted dataset case from that same promotion flow
- `add` one acceptance test for accepting an STT benchmark definition with
  explicit Voxtral delay profiles
- `update` hosted-dataset locking coverage so benchmark-owned locking preserves
  curated STT cases unchanged
- `add` one acceptance test for running the STT comparison and producing
  readable results
- `add` live validation assets for the same three behaviors under
  `tests/live/benchmarks/`
- `update` existing benchmark-model and hosted-dataset verification tests where
  they currently assume extraction-only row shapes

The acceptance tests should be named by behavior, not by item number or phase
number.

## Expected Next Deliverables

- refresh the Item 10 implementation plan so it matches this three-phase scope
- add the STT dataset seed and hosted-dataset bootstrap path
- add the STT benchmark runner and report flow
- add the delay-sweep benchmark definition

## References

- `docs/superpowers/specs/2026-04-10-item7-evals-restructure-design.md`
- `docs/superpowers/specs/2026-04-13-item7.5-logfire-hosted-dataset-locking-design.md`
- `docs/superpowers/specs/2026-04-10-item8-stt-provider-abstraction-design.md`
- `docs/superpowers/specs/2026-04-13-item9.1-voxtral-adapter-design.md`
- `docs/references/2026-04-13-item9-voxtral-realtime-spike-findings.md`
- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
- `docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md`
- `backend/app/stt.py`
- `backend/app/stt_soniox.py`
- `backend/app/stt_mistral.py`
- `evals/models.py`
- `evals/storage.py`
- `evals/resolution.py`
