# Item 9 Voxtral Realtime Semantics Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-13-item9-voxtral-realtime-spike-design.md`

**Goal:** Capture real Voxtral realtime traces from prerecorded fixtures and produce a short evidence-backed seam assessment that tells us how to design the future adapter.

**Architecture:** Keep the spike narrow. Put the reusable probe logic in one small backend module, keep the CLI entrypoint in `scripts/`, write raw provider-native JSONL traces into the existing fixture folders, and finish with a short findings note that maps Soniox behaviors to Voxtral evidence. Do not redesign the live path or extraction logic in this item.

**Tech Stack:** Python 3.11+, `mistralai` realtime transcription client, existing fixture audio under `backend/tests/fixtures/`, pytest, markdown docs

---

## Scope

This plan covers exactly four deliverables:

1. Add a small reusable probe helper for Voxtral trace capture and stop-summary logic.
2. Add a CLI script that streams fixture audio to Voxtral and records provider-native events.
3. Run the probe on a small fixture set and commit the raw traces.
4. Write the spike findings note with the seam-mapping table required by the spec.

Out of scope for this plan:

- wiring Voxtral into `/ws`
- designing new extraction triggers
- delay-sensitivity experiments
- dual-delay behavior
- benchmark harness work

---

## File Map

| File | Responsibility |
|------|----------------|
| `backend/app/stt_mistral_probe.py` | Pure spike helpers: fixture resolution, trace envelopes, stop-summary extraction, output-path helpers |
| `backend/tests/test_stt_mistral_probe.py` | Unit tests for trace formatting, stop-summary logic, and fixture/output path resolution |
| `scripts/mistral_realtime_probe.py` | CLI entrypoint that streams fixture audio to Voxtral and writes raw JSONL traces |
| `backend/tests/fixtures/<fixture>/mistral/trace.jsonl` | Provider-native trace artifact for each probed fixture |
| `docs/references/2026-04-13-item9-voxtral-realtime-spike-findings.md` | Short findings note and seam-mapping table |

Notes:

- Keep the helper module small and spike-specific. Do not turn it into the production adapter yet.
- The script should derive fixture audio paths and default output paths automatically so live runs are simple.
- Preserve provider-native payloads in the trace file. Normalized summaries are additive, not replacements.

---

## Task 1: Add probe helpers and deterministic tests

**Files:**
- Create: `backend/app/stt_mistral_probe.py`
- Create: `backend/tests/test_stt_mistral_probe.py`

The helper module should contain only deterministic logic that is worth testing offline:

- resolve a fixture's `audio.pcm` path
- derive a default trace output path under `backend/tests/fixtures/<fixture>/mistral/`
- build one JSONL trace record from an event payload plus local timing metadata
- summarize stop-time transcript authority from an ordered list of recorded events

- [ ] **Step 1: Write the failing tests**

Add `backend/tests/test_stt_mistral_probe.py` with focused cases such as:

```python
def test_default_trace_path_points_into_fixture_mistral_dir():
    ...


def test_build_trace_record_preserves_raw_payload_and_event_type():
    ...


def test_summarize_stop_semantics_compares_last_delta_and_done_text():
    events = [
        {"type": "transcription.text.delta", "text": "Buy milk"},
        {"type": "transcription.done", "text": "Buy milk tomorrow"},
    ]

    summary = summarize_stop_semantics(events)

    assert summary.last_delta_text == "Buy milk"
    assert summary.done_text == "Buy milk tomorrow"
    assert summary.done_differs_from_last_delta is True
```

- [ ] **Step 2: Run the test file to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_mistral_probe.py -v
```

Expected: FAIL because `app.stt_mistral_probe` does not exist yet

- [ ] **Step 3: Implement the minimal helper module**

Create `backend/app/stt_mistral_probe.py` with:

- a `FIXTURES_DIR` rooted at `backend/tests/fixtures`
- `resolve_fixture_audio_path(fixture_name: str) -> Path`
- `default_trace_output_path(fixture_name: str) -> Path`
- `build_trace_record(*, elapsed_ms: int, event_type: str, payload: dict, fixture: str, model: str) -> dict`
- `summarize_stop_semantics(events: list[dict]) -> ...`

Implementation rules:

- keep trace records provider-native
- tolerate unknown event payloads
- treat `transcription.done` as the candidate final source of truth without hard-coding that it is correct
- make the summary say whether `done.text` differs from the last visible text delta

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_stt_mistral_probe.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/stt_mistral_probe.py backend/tests/test_stt_mistral_probe.py
git commit -m "feat: add voxtral spike probe helpers"
```

---

## Task 2: Add the live probe CLI

**Files:**
- Create: `scripts/mistral_realtime_probe.py`
- Modify: `backend/tests/test_stt_mistral_probe.py`

The CLI should be thin and rely on the helper module for deterministic behavior.

Target CLI behavior:

- `--fixture <name>` selects a fixture by directory name
- reads `audio.pcm` from that fixture
- loads `MISTRAL_API_KEY` using existing backend env/config conventions
- streams audio to `voxtral-mini-transcribe-realtime-2602`
- writes one JSON object per provider event to the default fixture trace path
- prints a concise stop summary at the end

- [ ] **Step 1: Add one failing test for the live-run plumbing**

Extend `backend/tests/test_stt_mistral_probe.py` with a case that proves the
runner records the terminal event summary from a fake event stream, for example:

```python
@pytest.mark.asyncio
async def test_record_probe_run_writes_trace_and_returns_stop_summary(tmp_path):
    ...
```

Design the runner so the Mistral event iterator can be injected in tests rather
than requiring live vendor access.

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_stt_mistral_probe.py::test_record_probe_run_writes_trace_and_returns_stop_summary -v
```

Expected: FAIL because the live-run helper does not exist yet

- [ ] **Step 3: Implement the runner and CLI**

Add to `backend/app/stt_mistral_probe.py` a small async runner such as:

- `record_probe_run(...)`

Then create `scripts/mistral_realtime_probe.py` as a thin CLI wrapper that:

- parses `--fixture`
- creates the output directory if needed
- streams the fixture audio in fixed-size chunks
- records every realtime event as JSONL
- exits non-zero on provider errors

Implementation guidance:

- use the provider-native Mistral realtime client directly
- keep the event write path append-only
- record event type names exactly as the provider emits them
- keep timing local and monotonic
- do not normalize events into the app's `SttEvent` contract in this item

- [ ] **Step 4: Run the test file to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/test_stt_mistral_probe.py -v
```

Expected: PASS

- [ ] **Step 5: Smoke-check the CLI help locally**

Run:

```bash
cd backend && uv run python ../scripts/mistral_realtime_probe.py --help
```

Expected: usage text mentioning `--fixture`

- [ ] **Step 6: Commit**

```bash
git add backend/app/stt_mistral_probe.py backend/tests/test_stt_mistral_probe.py scripts/mistral_realtime_probe.py
git commit -m "feat: add voxtral realtime probe cli"
```

---

## Task 3: Capture the raw Voxtral traces

**Files:**
- Create: `backend/tests/fixtures/stop-the-button/mistral/trace.jsonl`
- Create: `backend/tests/fixtures/continuous-speech/mistral/trace.jsonl`
- Create: `backend/tests/fixtures/call-mom-memo-supplier/mistral/trace.jsonl`

This task is the live part of the spike. Keep the fixture set small and
representative.

- [ ] **Step 1: Run the probe for `stop-the-button`**

Run:

```bash
cd backend && uv run python ../scripts/mistral_realtime_probe.py --fixture stop-the-button
```

Expected:

- `backend/tests/fixtures/stop-the-button/mistral/trace.jsonl` exists
- the command prints a stop summary including the last visible text and the
  `transcription.done` text

- [ ] **Step 2: Run the probe for `continuous-speech`**

Run:

```bash
cd backend && uv run python ../scripts/mistral_realtime_probe.py --fixture continuous-speech
```

Expected: trace file written under that fixture's `mistral/` directory

- [ ] **Step 3: Run the probe for `call-mom-memo-supplier`**

Run:

```bash
cd backend && uv run python ../scripts/mistral_realtime_probe.py --fixture call-mom-memo-supplier
```

Expected: trace file written under that fixture's `mistral/` directory

- [ ] **Step 4: Inspect the trace files for the core spike questions**

Check each trace for:

- event types seen in practice
- whether `transcription.segment` appears
- whether `transcription.done.text` differs from the last visible text delta
- whether the provider emits any evidence of correction rather than pure append

Suggested commands:

```bash
rg -n 'transcription\\.' backend/tests/fixtures/*/mistral/trace.jsonl
```

```bash
rg -n 'transcription.segment' backend/tests/fixtures/*/mistral/trace.jsonl
```

- [ ] **Step 5: Commit the raw traces**

```bash
git add backend/tests/fixtures/stop-the-button/mistral/trace.jsonl backend/tests/fixtures/continuous-speech/mistral/trace.jsonl backend/tests/fixtures/call-mom-memo-supplier/mistral/trace.jsonl
git commit -m "test: capture voxtral realtime trace fixtures"
```

---

## Task 4: Write the findings note

**Files:**
- Create: `docs/references/2026-04-13-item9-voxtral-realtime-spike-findings.md`

The findings note should be short. It should answer the spec's questions, not
retell the whole investigation.

- [ ] **Step 1: Draft the findings note from the saved traces**

Include:

- the observed event sequence from connect to completion
- whether `TranscriptionStreamDone.text` appears to be the best stop-time source
  of truth
- whether `transcription.segment` appeared and whether it looks meaningful
- whether the current seam fits as-is, fits with different app logic, is
  unclear, or is unsupported for each important behavior

Required table:

| Behavior | Soniox today | Voxtral evidence | Fit status | Note |
|---|---|---|---|---|

- [ ] **Step 2: Review the note against the spec**

Verify the note answers:

- session lifecycle and stop semantics
- transcript semantics
- seam assessment

Expected: no TODOs, placeholders, or uncategorized behaviors remain

- [ ] **Step 3: Commit**

```bash
git add docs/references/2026-04-13-item9-voxtral-realtime-spike-findings.md
git commit -m "docs: record voxtral spike findings"
```

---

## Final Verification

- [ ] `cd backend && uv run pytest tests/test_stt_mistral_probe.py -v`
- [ ] `cd backend && uv run python ../scripts/mistral_realtime_probe.py --help`
- [ ] Confirm the three trace files exist under `backend/tests/fixtures/*/mistral/`
- [ ] Confirm the findings note includes the seam-mapping table and a stop-path conclusion

---

## Handoff Notes

- This spike should stop once the traces and findings are in place.
- Do not start wiring Voxtral into `/ws` under this plan.
- The next design artifact after execution should be `Item 9.1`, based on the
  saved traces and findings rather than on doc inference.
