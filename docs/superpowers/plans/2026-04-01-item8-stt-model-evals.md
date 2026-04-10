# Item 8: STT Model Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-01-item8-stt-model-evals-design.md`

**Goal:** Add a repeatable, config-driven STT eval harness so we can compare Soniox, Google Cloud Speech-to-Text `chirp_3`, and Voxtral on the same recorded audio fixtures using WER and speed as the main outputs.

**Architecture:** Keep the production `/ws` path focused on Soniox for now. Build a dedicated `stt_quality` eval suite under `backend/evals/` with one stable manifest file, one fixture loader, one transcript-metrics module, one provider-capability map, one provider-adapter module, one experiment-config module, and one runner module. The runner should replay saved PCM fixtures through each provider path, compute WER plus timing metrics, and record capability differences explicitly instead of pretending every provider has the same endpointing or finalization signals.

**Tech Stack:** FastAPI backend code, websockets, Google Cloud Speech-to-Text, Soniox realtime STT, Mistral realtime transcription APIs, pytest, Logfire, recorded PCM fixtures

**References:** `backend/app/ws.py`, `backend/app/config.py`, `backend/app/transcript_accumulator.py`, `backend/tests/test_replay.py`, `backend/tests/test_soniox_integration.py`, `backend/tests/fixtures/`, `docs/references/soniox.md`, `docs/references/eval-models-and-stacks.md`

---

## Scope

This plan covers exactly five deliverables:

1. Add an eval-only settings surface for non-Soniox STT providers.
2. Create and maintain a dedicated STT fixture manifest asset.
3. Implement a provider capability map plus deterministic WER and timing metrics for STT runs.
4. Add a config-driven STT runner with provider adapters and named experiment configs.
5. Document how to run and compare STT experiments locally.

Out of scope for this plan:

- swapping the production `/ws` endpoint off Soniox
- downstream todo extraction scoring
- browser microphone end-to-end testing
- automatic fixture capture from live sessions
- conversational voice-agent evals
- deciding the final deployment stack

---

## Eval Strategy

We will treat this as a replay-driven dedicated-STT eval, not an end-to-end pipeline eval.

- Input: recorded PCM fixture audio plus deterministic audio metadata
- Output: final transcript, WER, timing metrics, provider capability notes, and provider status
- Ground truth: a stable dedicated STT manifest plus existing audio assets
- Initial seed material: `backend/tests/fixtures/*/audio.pcm`, `result.json`, and optional `soniox.jsonl` for Soniox-only debugging
- First candidate matrix:
  - `soniox_baseline` -> `stt-rt-v4`
  - `google_chirp3` -> `chirp_3`
  - `voxtral_realtime` -> `voxtral-mini-transcribe-realtime-2602`
- Initial reporting dimensions:
  - `word_error_rate`
  - explicit `reference_transcript` and `predicted_transcript`
  - `final_latency_ms`
  - `first_partial_latency_ms` where available
  - provider capability flags for endpointing / manual finalization / partial text
  - provider/runtime status for skipped or failed runs
- Later reporting dimensions:
  - CER if WER alone proves insufficient
  - end-to-end stack comparisons with the extraction eval harness

The initial goal is not to produce one master score. It is to create a stable harness that lets us compare transcript quality and speed on the same cases while documenting feature mismatches honestly.

---

## Design Gates

These two design gates are now resolved for the first implementation pass:

### Design Gate 1 - Dedicated STT fixture manifest

Decision:

- create one dedicated STT manifest file: `backend/evals/stt_quality/stt_fixture_manifest_v1.json`
- make that file the canonical source for eval runs
- treat `backend/tests/fixtures/*` as seed material plus raw assets, not the long-term manifest itself
- keep the manifest format as JSON so it stays easy to review in git
- keep the scope narrow: replay recorded audio to transcript outputs only for v1
- include per-case audio path, audio format, sample rate, channel count, expected transcript, source fixture, and tags
- keep `soniox.jsonl` out of the canonical manifest unless a later revision needs baseline event replays explicitly

### Design Gate 2 - Reporting strategy

Decision:

- use `word_error_rate` as the first transcript-quality metric
- report `reference_transcript` and `predicted_transcript` alongside WER
- track `final_latency_ms` as the primary speed metric
- track `first_partial_latency_ms` only when the provider exposes partial transcript events
- record provider capability flags for endpointing, manual finalization, partial text, and final transcript markers
- do not use an LLM judge
- do not collapse WER and latency into one total score in v1

This keeps the first STT harness explainable: it answers "how accurate was the final transcript, how fast did it arrive, and what streaming features did the provider actually expose?"

---

## File Map

### Backend - New files

| File | Responsibility |
|------|----------------|
| `backend/evals/stt_quality/stt_fixture_manifest_v1.json` | Dedicated stable manifest file for STT-quality experiments; canonical source for eval runs |
| `backend/evals/stt_quality/fixture_loader.py` | Load the STT manifest into deterministic eval cases with audio metadata and reference transcript |
| `backend/evals/stt_quality/transcript_metrics.py` | Compute WER and deterministic timing result fields |
| `backend/evals/stt_quality/provider_capabilities.py` | Static capability map for endpointing, manual finalization, partial text, and final transcript markers |
| `backend/evals/stt_quality/provider_adapters.py` | Provider-specific replay adapters normalized behind one common STT result interface |
| `backend/evals/stt_quality/experiment_configs.py` | Named experiment-config registry for Soniox, Google Chirp 3, and Voxtral runs |
| `backend/evals/stt_quality/run.py` | CLI runner for STT-quality experiment configs and repeated replay runs |
| `backend/evals/stt_quality/README.md` | Short usage guide for running this STT eval suite and comparing outputs |
| `backend/tests/test_stt_fixture_loader.py` | Focused tests for the STT manifest schema and loader behavior |
| `backend/tests/test_stt_transcript_metrics.py` | Deterministic tests for WER and timing metric construction |
| `backend/tests/test_stt_experiment_configs.py` | Smoke-level tests for the STT experiment registry and skip logic |

### Backend - Modified files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add optional settings for Google Cloud STT and Mistral auth needed by the STT eval runner |
| `backend/tests/test_config.py` | Add tests for the new optional STT-eval settings without changing production requirements |

### Backend - Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/app/ws.py` | Defines the current Soniox websocket config, finalize ordering, and PCM assumptions |
| `backend/app/transcript_accumulator.py` | Encodes current `<fin>` and `<end>` semantics that STT timing/debugging should align with |
| `backend/tests/test_replay.py` | Provides the current Soniox replay baseline and transcript reference behavior |
| `backend/tests/test_soniox_integration.py` | Shows the current realtime pacing and finalize sequence against the live Soniox API |
| `backend/tests/fixtures/*` | Existing recorded audio fixtures and reference transcripts for the seed corpus |

---

## Task 1: Add STT eval provider settings

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_config.py`

The current settings surface only covers Soniox and the existing Gemini extraction path. The STT eval runner needs a safe place to read non-production provider keys without turning those providers into mandatory startup requirements.

- [ ] **Step 1: Add failing tests for optional STT provider settings**

Extend `backend/tests/test_config.py` with focused tests that prove:

1. the existing Soniox + Gemini env still loads unchanged
2. optional STT-eval settings such as `MISTRAL_API_KEY` and `GOOGLE_CLOUD_PROJECT_ID` default to `None`
3. those optional keys load when present without becoming required for app startup

Suggested cases:

```python
def test_settings_default_optional_stt_eval_keys_to_none():
    ...

def test_settings_loads_optional_stt_eval_keys():
    ...
```

- [ ] **Step 2: Run config tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_config.py -v`

Expected: FAIL because the settings model does not yet expose the optional STT-eval provider keys

- [ ] **Step 3: Add optional STT-eval provider settings**

Update `backend/app/config.py` so the eval harness can read provider keys without changing the current production requirements.

Recommended shape:

```python
class Settings(BaseSettings):
    soniox_api_key: str
    gemini_api_key: str
    google_cloud_project_id: str | None = None
    mistral_api_key: str | None = None
    record_sessions: bool = False
    soniox_stop_timeout_seconds: float = 30.0
```

Implementation guidance:

- keep `soniox_api_key` and `gemini_api_key` required exactly as they are today
- add only the optional fields needed by the STT eval runner
- rely on Google ADC / service-account auth for Chirp 3 instead of trying to reuse `GEMINI_API_KEY`
- avoid coupling these new settings to production websocket startup logic

- [ ] **Step 4: Run config tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit the settings update**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add optional stt eval provider settings"
```

---

## Task 2: Create the dedicated STT fixture manifest

**Files:**
- Add: `backend/evals/stt_quality/stt_fixture_manifest_v1.json`
- Add: `backend/evals/stt_quality/fixture_loader.py`
- Add: `backend/tests/test_stt_fixture_loader.py`

The current fixtures already give us audio, transcript references, and Soniox event captures. The design decision for v1 is to create one dedicated JSON manifest file for STT evals, seeded from those fixtures but maintained independently from the fixture directory layout.

- [x] **Step 1: Resolve the STT manifest design**

Resolved manifest decisions:

- manifest file name: `stt_fixture_manifest_v1.json`
- manifest path: `backend/evals/stt_quality/stt_fixture_manifest_v1.json`
- serialized format: JSON
- scope: STT-specific replay evaluation in v1
- source of truth: this manifest file, not direct directory scanning
- seed source: existing `backend/tests/fixtures/*`
- new cases should be added by editing the manifest directly after the initial seed import

Expected output of this step:

- a documented manifest decision
- a stable asset path and naming convention
- a case schema we agree to support

- [ ] **Step 2: Write a failing loader test**

Add `backend/tests/test_stt_fixture_loader.py` with a focused test that proves the loader reads a stable JSON manifest and resolves known fixtures correctly.

Suggested case:

```python
def test_load_manifest_returns_known_fixture_cases():
    ...
```

- [ ] **Step 3: Run the loader test to verify it fails**

Run: `cd backend && uv run pytest tests/test_stt_fixture_loader.py -v`

Expected: FAIL because the manifest and loader do not exist yet

- [ ] **Step 4: Create the first dedicated STT manifest and loader**

Create the dedicated asset from the existing fixtures and implement a loader in `backend/evals/stt_quality/fixture_loader.py`.

Recommended case shape:

```json
{
  "dataset": "stt_fixture_manifest_v1",
  "version": 1,
  "cases": [
    {
      "id": "stop-the-button",
      "audio_path": "backend/tests/fixtures/stop-the-button/audio.pcm",
      "audio_format": "pcm_s16le",
      "sample_rate_hz": 16000,
      "num_channels": 1,
      "reference_transcript": "Stop the button.",
      "source_fixture": "stop-the-button",
      "tags": ["short_utterance", "finalization"]
    }
  ]
}
```

Implementation guidance:

- keep the manifest human-reviewable in git
- preserve no-todo and noisy-speech cases
- keep the schema stable enough that later experiment runs do not require rewriting it
- keep `soniox.jsonl` outside the canonical manifest fields for now

- [ ] **Step 5: Run the loader test to verify it passes**

Run: `cd backend && uv run pytest tests/test_stt_fixture_loader.py -v`

Expected: PASS

- [ ] **Step 6: Commit the manifest and loader**

```bash
git add backend/evals/stt_quality/stt_fixture_manifest_v1.json backend/evals/stt_quality/fixture_loader.py backend/tests/test_stt_fixture_loader.py
git commit -m "feat: add dedicated stt eval manifest"
```

---

## Task 3: Implement provider capability mapping plus WER and timing metrics

**Files:**
- Add: `backend/evals/stt_quality/transcript_metrics.py`
- Add: `backend/evals/stt_quality/provider_capabilities.py`
- Add: `backend/tests/test_stt_transcript_metrics.py`

The first STT eval pass should stay deterministic and easy to read. We want WER plus speed, with provider capability differences recorded explicitly rather than hidden in one generic adapter contract.

- [ ] **Step 1: Write failing tests for transcript normalization and metrics**

Add `backend/tests/test_stt_transcript_metrics.py` with focused tests that prove:

1. WER is zero for identical transcripts
2. WER reflects word-level insertions, deletions, and substitutions
3. timing fields preserve `None` when a provider does not expose partials
4. provider capability records remain separate from transcript metrics

Suggested cases:

```python
def test_word_error_rate_is_zero_for_identical_transcripts():
    ...

def test_build_transcript_metrics_reports_wer_and_latencies():
    ...
```

- [ ] **Step 2: Run the metric tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_stt_transcript_metrics.py -v`

Expected: FAIL because the metric module does not exist yet

- [ ] **Step 3: Implement the transcript metric module**

Add `backend/evals/stt_quality/transcript_metrics.py` and `backend/evals/stt_quality/provider_capabilities.py`.

Recommended shape:

```python
def word_error_rate(reference: str, hypothesis: str) -> float:
    ...

def build_transcript_metrics(
    *,
    reference_transcript: str,
    predicted_transcript: str,
    first_partial_latency_ms: float | None,
    final_latency_ms: float | None,
    capability_flags: dict[str, bool | str | None],
) -> dict[str, object]:
    ...
```

Implementation guidance:

- compute WER deterministically in repo code
- include raw reference/predicted transcripts in the output record
- keep capability mapping separate from metric computation
- keep the result shape generic enough for all providers

- [ ] **Step 4: Run the metric tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_stt_transcript_metrics.py -v`

Expected: PASS

- [ ] **Step 5: Commit the metric module**

```bash
git add backend/evals/stt_quality/transcript_metrics.py backend/evals/stt_quality/provider_capabilities.py backend/tests/test_stt_transcript_metrics.py
git commit -m "feat: add stt transcript metrics"
```

---

## Task 4: Add provider adapters and a config-driven STT runner

**Files:**
- Add: `backend/evals/stt_quality/provider_adapters.py`
- Add: `backend/evals/stt_quality/experiment_configs.py`
- Add: `backend/evals/stt_quality/run.py`
- Add: `backend/tests/test_stt_experiment_configs.py`

This is the heart of the STT workflow. The runner should accept named experiment configs, replay the same audio fixtures through each provider adapter, and report comparable transcript and timing outputs without touching production websocket code.

- [ ] **Step 1: Write a minimal registry smoke test**

Add `backend/tests/test_stt_experiment_configs.py` or an equivalent `--list-experiments` smoke check that proves the experiment registry exposes the expected first matrix.

Suggested behavior:

```bash
cd backend && uv run python evals/stt_quality/run.py --list-experiments
```

Expected output includes:

- `soniox_baseline`
- `google_chirp3`
- `voxtral_realtime`

- [ ] **Step 2: Implement named STT experiment configs**

Define a small registry in `backend/evals/stt_quality/experiment_configs.py`.

Recommended shape:

```python
@dataclass(frozen=True)
class SttExperimentConfig:
    provider: str
    model_name: str
    transport: str
    required_env_vars: tuple[str, ...]
    replay_chunk_size_bytes: int = 3200
    replay_delay_seconds: float = 0.1


EXPERIMENTS = {
    "soniox_baseline": SttExperimentConfig(...),
    "google_chirp3": SttExperimentConfig(...),
    "voxtral_realtime": SttExperimentConfig(...),
}
```

Implementation guidance:

- keep the registry generic enough to add later STT candidates without rewriting the runner
- include the required env-var set for clean skip behavior
- record whether the provider is streaming websocket STT or API-based streaming recognition
- keep replay pacing configurable but deterministic by default

- [ ] **Step 3: Implement provider adapters with one shared result shape**

Add `backend/evals/stt_quality/provider_adapters.py`.

Recommended adapter protocol:

```python
class SttAdapter(Protocol):
    async def transcribe_fixture(
        self,
        case: SttFixtureCase,
        config: SttExperimentConfig,
    ) -> SttRunResult:
        ...
```

Implementation guidance:

- normalize all providers into one `SttRunResult` shape with transcript, timing fields, capability flags, status, and raw metadata
- keep Soniox adapter behavior aligned with the current finalize -> wait -> end ordering described in `backend/app/ws.py` and `docs/references/soniox.md`
- stream PCM in realtime-style chunks for providers that expect live audio input
- map Google Chirp 3 through Cloud Speech-to-Text streaming recognition rather than the Gemini Live API
- skip experiments with missing provider keys and print a clear reason instead of crashing

- [ ] **Step 4: Wire the runner and reporting flow**

Add `backend/evals/stt_quality/run.py` that:

- loads the manifest once
- runs one or many named experiments against the selected cases
- uses `transcript_metrics.py` plus `provider_capabilities.py` to build per-case result records
- prints comparable per-case summaries
- attaches provider/model metadata to Logfire when configured

Recommended CLI flags:

- `--experiment <name>` (repeatable)
- `--all`
- `--case <id>` (repeatable)
- `--repeat <n>`
- `--list-experiments`
- `--max-concurrency <n>`

Important behavior:

- keep default concurrency conservative for realtime providers
- continue past single-case provider failures and mark them explicitly
- avoid coupling the runner to the browser websocket path

- [ ] **Step 5: Run the first smoke checks**

Run:

```bash
cd backend && uv run python evals/stt_quality/run.py --list-experiments
cd backend && uv run python evals/stt_quality/run.py --experiment soniox_baseline --case stop-the-button --repeat 2
```

Expected:

- the experiment list prints the four named configs
- the Soniox baseline can replay the chosen fixture and produce a structured result record
- providers without keys are skipped clearly rather than crashing

- [ ] **Step 6: Commit the STT runner**

```bash
git add backend/evals/stt_quality/provider_adapters.py backend/evals/stt_quality/experiment_configs.py backend/evals/stt_quality/run.py backend/tests/test_stt_experiment_configs.py
git commit -m "feat: add config-driven stt eval runner"
```

---

## Task 5: Document the STT experiment workflow

**Files:**
- Add: `backend/evals/stt_quality/README.md`

The goal is to make STT trials easy to repeat. A teammate should be able to list experiments, run a subset of fixtures, and compare transcript/timing outputs without reading the implementation first.

- [ ] **Step 1: Write the README**

Document:

1. what this STT eval harness measures
2. what it does not measure
3. how the STT fixture manifest is structured and maintained
4. how to list experiments
5. how to run one experiment against one case
6. how to run the whole matrix
7. how to interpret WER, latency, and capability fields
8. how to add a new STT provider config safely

Include example commands:

```bash
cd backend && uv run python evals/stt_quality/run.py --list-experiments
cd backend && uv run python evals/stt_quality/run.py --experiment soniox_baseline --case stop-the-button
cd backend && uv run python evals/stt_quality/run.py --all --repeat 3 --max-concurrency 1
```

- [ ] **Step 2: Add caveats and guardrails**

Document the main traps explicitly:

- the manifest is canonical, but the raw audio still lives under `backend/tests/fixtures/`
- Soniox finalize ordering matters and should remain the adapter reference behavior
- WER and final latency are the primary metrics; capability flags explain what is or is not comparable across providers
- providers expose different timing signals, so missing partial metrics should be represented explicitly rather than guessed
- STT eval results are decision support, not rollout automation

- [ ] **Step 3: Commit the docs**

```bash
git add backend/evals/stt_quality/README.md
git commit -m "docs: add stt eval workflow guide"
```

---

## Validation Checklist

- [ ] optional STT-eval provider settings load without changing the current production requirements
- [ ] the STT manifest decision is documented and implemented as a stable repo asset
- [ ] WER and timing metrics are deterministic and provider-agnostic
- [ ] provider capability differences are recorded explicitly
- [ ] the runner can compare multiple STT configs without code edits
- [ ] skipped experiments are reported clearly when provider keys are missing
- [ ] transcript quality and latency remain separate outputs
- [ ] no production websocket changes are required to switch STT eval experiments

---

## Recommended First Execution Order

1. Add the optional STT-eval provider settings.
2. Create the manifest and fixture loader from the existing audio fixtures.
3. Implement the capability map plus WER and timing metrics.
4. Build the experiment registry and validate the Soniox baseline first.
5. Add the Chirp 3 and Voxtral adapters and compare outputs on the same seed cases.

---

## Open Questions To Revisit After The First STT Eval Run

- Is WER sufficient, or do we need CER or per-language scoring next?
- Which providers expose timing signals that are comparable enough for the same report layout?
- Do we need a second STT-focused fixture wave for accents, correction-heavy speech, or longer continuous dictation?
- When are both the STT and extraction eval tracks stable enough to justify end-to-end stack comparisons?
