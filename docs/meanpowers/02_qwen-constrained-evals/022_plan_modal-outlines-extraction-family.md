# Add Managed Modal/Outlines Extraction Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Spec:** [022_spec_modal-outlines-extraction-family.md](/Users/josselinperrus/conductor/workspaces/voice-todos/douala/docs/meanpowers/02_qwen-constrained-evals/022_spec_modal-outlines-extraction-family.md)

**Goal:** Extend the merged DeepInfra benchmark baseline with a third managed `modal-outlines` family, while keeping the `021` two-family DeepInfra contract intact.

**Architecture:** Preserve the existing `implementation.family` benchmark identity seam from `021`, add four managed entries plus stable `session` specs, inject runtime OpenAI-compatible transport only at benchmark launch time, and make `evals/run.py` own managed lease open, warmup, reuse, and teardown.

**Tech Stack:** Python 3.14, pydantic, pydantic_ai, OpenAI-compatible chat transport, Modal CLI launcher, YAML benchmark definitions, pytest, `uv`, benchmark CLI.

## File Map

- Modify `evals/benchmarks/todo_extraction_bench_v1.yaml`
  Add the four `modal_outlines_qwen35_*` managed entries while preserving the eight merged DeepInfra entries.

- Modify `evals/models.py`
  Add a stable managed session config model and extend resolved benchmark config with managed session data.

- Modify `evals/resolution.py`
  Parse `session` for managed entries and make stable session config participate in benchmark identity without replacing `implementation.family`.

- Create `evals/managed_sessions.py`
  Encapsulate managed Modal lease startup, readiness parsing, warmup, and teardown.

- Modify `evals/run.py`
  Partition managed entries, group them by stable session spec plus model, open one lease per group, inject the lease into extraction launches, and always close it.

- Modify `backend/app/model_providers.py`
  Add a generic runtime OpenAI-compatible base-url path for managed benchmark transports.

- Modify `backend/app/extract.py`
  Add runtime transport override fields to `ExtractionConfig`, preserve the merged DeepInfra family logic, and add the managed native structured-output path.

- Modify `backend/evals/extraction_quality/experiment_configs.py`
  Carry managed family/runtime config through synthetic experiment creation without reopening the legacy registry cleanup question.

- Modify `backend/evals/extraction_quality/run.py`
  Inject managed lease transport into benchmark-launched extraction experiments.

- Modify `scripts/qwen_sglang_outlines_smoke.py`
  Turn the existing Modal spike into a reusable benchmark launcher surface that can either smoke-test or serve a managed lease.

- Modify `backend/tests/test_benchmark_definitions.py`
- Modify `backend/tests/test_benchmark_extraction_runner.py`
- Modify `backend/tests/test_benchmark_report.py`
- Modify `backend/tests/test_extract.py`
- Modify `backend/tests/test_extraction_runner.py`
  Add focused coverage for managed benchmark identity, launcher behavior, transport injection, lifecycle ordering, and cleanup.

## Acceptance Gates From Spec

## Acceptance Gate: The Extraction Benchmark Surfaces The Three-Family Qwen Comparison

Why this gate matters:
This slice is not real until the benchmark visibly contains the managed family as the third lane beside the two merged DeepInfra lanes.

Criteria:

- `benchmark show` contains all twelve Qwen comparison entries:
  - `deepinfra_qwen35_0_8b_output_tool`
  - `deepinfra_qwen35_2b_output_tool`
  - `deepinfra_qwen35_4b_output_tool`
  - `deepinfra_qwen35_9b_output_tool`
  - `deepinfra_qwen35_0_8b_provider_json_schema`
  - `deepinfra_qwen35_2b_provider_json_schema`
  - `deepinfra_qwen35_4b_provider_json_schema`
  - `deepinfra_qwen35_9b_provider_json_schema`
  - `modal_outlines_qwen35_0_8b`
  - `modal_outlines_qwen35_2b`
  - `modal_outlines_qwen35_4b`
  - `modal_outlines_qwen35_9b`
- Each managed entry reports:
  - `provider: managed-openai`
  - `config.implementation.family = "modal-outlines"`
  - a stable `session` block with `stack`, `host`, `gpu`, and `context_window`
- At least one managed canary run appears in benchmark reporting as `current` with:
  - `selected_run_id`
  - `selected_timestamp`
  - `total_case_count > 0`

Proof:

- Update the benchmark definition to include the four managed entries without changing the eight merged DeepInfra ids.
- Run:

```bash
cd backend && uv run python ../evals/cli.py benchmark show todo_extraction_bench_v1
```

- Run a managed canary through the benchmark path.
- Generate:

```bash
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json
```

- Verify from the show/report output that:
  - all twelve Qwen entries are present
  - the four managed entries report `provider: managed-openai`
  - the four managed entries report `config.implementation.family = "modal-outlines"`
  - at least one managed entry is `current` with non-zero case counts

Expected evidence:

- the exact `benchmark show` command used
- the exact managed canary command used
- the exact `benchmark report --json` command used
- extracted report assertions showing:
  - presence of the twelve Qwen entry ids
  - managed family metadata on the four managed entries
  - one `current` managed canary with non-zero case counts

## Acceptance Gate: Managed Modal Benchmark Runs Are Warm And Cleaned Up

Why this gate matters:
Shaping `V3` is not only about adding four config entries. The managed runtime must be safe to use for benchmarking and must not contaminate measurements with startup latency or leaked servers.

Criteria:

- Running the managed Modal entries through the benchmark path produces `current` benchmark results for all four managed entries with non-zero case counts.
- The benchmark runtime measures managed cases against a warmed endpoint, not a cold-start request.
- After a managed benchmark run completes or fails, no managed benchmark server remains running locally.

Proof:

- Add focused benchmark-runner acceptance tests that prove:
  - warmup happens before managed entry execution
  - teardown runs after success
  - teardown runs after failure
- Run the managed family through the benchmark path.
- Generate the benchmark JSON report and verify all four managed entries are `current` with non-zero case counts.
- After the run, check that no `modal run scripts/qwen_sglang_outlines_smoke.py --mode serve` process remains.

Expected evidence:

- the exact focused acceptance test command(s) used
- the exact managed benchmark command used
- the exact post-run process-check command used
- extracted output showing:
  - focused lifecycle acceptance tests passed
  - all four managed entries are `current` with non-zero case counts
  - no managed benchmark server process remains

## Gate Execution

Run this only after the implementation tasks below pass their supporting verification.

1. Preflight live-run prerequisites:

```bash
cd backend && uv run python - <<'PY'
from app.backend_env import read_backend_env_var
from app.logfire_setup import has_logfire_write_credentials

assert read_backend_env_var("DEEPINFRA_API_KEY"), "Missing DEEPINFRA_API_KEY"
assert has_logfire_write_credentials(), "Missing Logfire write credentials"
print("DeepInfra and Logfire credentials present")
PY
```

2. Prove the three-family surface:

```bash
cd backend && uv run python ../evals/cli.py benchmark show todo_extraction_bench_v1 > ../.context/022_benchmark_show.txt
cd backend && uv run python - <<'PY' > ../.context/022_benchmark_show_assertions.txt
from evals.storage import load_benchmark_by_id

benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
entry_ids = {entry.id for entry in benchmark.entries}
expected = {
    "deepinfra_qwen35_0_8b_output_tool",
    "deepinfra_qwen35_2b_output_tool",
    "deepinfra_qwen35_4b_output_tool",
    "deepinfra_qwen35_9b_output_tool",
    "deepinfra_qwen35_0_8b_provider_json_schema",
    "deepinfra_qwen35_2b_provider_json_schema",
    "deepinfra_qwen35_4b_provider_json_schema",
    "deepinfra_qwen35_9b_provider_json_schema",
    "modal_outlines_qwen35_0_8b",
    "modal_outlines_qwen35_2b",
    "modal_outlines_qwen35_4b",
    "modal_outlines_qwen35_9b",
}
assert expected <= entry_ids, sorted(expected - entry_ids)
print("Three-family benchmark surface present")
PY
```

3. Run one managed canary and capture the report:

```bash
cd backend && PYTHONPATH=.. uv run python - <<'PY'
import asyncio
from evals.storage import load_benchmark_by_id
from evals.resolution import resolve_entry_config
from evals.run import ensure_benchmark_dataset_path, open_managed_session, close_managed_session, _launch_resolved_entry

BENCHMARK_ID = "todo_extraction_bench_v1"
ENTRY_ID = "modal_outlines_qwen35_4b"

async def main():
    benchmark = load_benchmark_by_id(BENCHMARK_ID)
    entry = next(e for e in benchmark.entries if e.id == ENTRY_ID)
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
    dataset_path = ensure_benchmark_dataset_path(BENCHMARK_ID)
    lease = await open_managed_session(resolved_config=resolved)
    try:
        result = await _launch_resolved_entry(
            entry=entry,
            resolved=resolved,
            dataset_path=dataset_path,
            repeat=benchmark.repeat,
            task_retries=benchmark.task_retries,
            max_concurrency=benchmark.max_concurrency,
            allow_untracked=True,
            managed_lease=lease,
        )
        print(result)
    finally:
        await close_managed_session(lease)

asyncio.run(main())
PY
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json > ../.context/022_benchmark_report_canary.json
```

4. Assert the canary gate result:

```bash
cd backend && uv run python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("../.context/022_benchmark_report_canary.json").read_text())
entries = {entry["entry_id"]: entry for entry in report["entries"]}

modal_ids = {
    "modal_outlines_qwen35_0_8b",
    "modal_outlines_qwen35_2b",
    "modal_outlines_qwen35_4b",
    "modal_outlines_qwen35_9b",
}

for entry_id in modal_ids:
    entry = entries[entry_id]
    assert entry["config"]["provider"] == "managed-openai", entry_id
    assert entry["config"]["implementation"]["family"] == "modal-outlines", entry_id
    assert set(entry["config"]["session"]) == {
        "stack",
        "host",
        "gpu",
        "context_window",
    }, entry_id

canary = entries["modal_outlines_qwen35_4b"]
assert canary["status"] == "current"
assert canary["selected_run_id"]
assert canary["selected_timestamp"]
assert canary["total_case_count"] > 0
print("Gate 1 assertions passed")
PY
```

5. Run focused lifecycle acceptance tests:

```bash
cd backend && uv run pytest \
  tests/test_benchmark_extraction_runner.py::test_run_benchmark_warms_managed_entries_before_execution \
  tests/test_benchmark_extraction_runner.py::test_run_benchmark_tears_down_managed_lease_on_group_failure \
  tests/test_benchmark_extraction_runner.py::test_run_benchmark_keeps_only_one_managed_lease_active \
  -v
```

6. Run the full managed family and capture the final report:

```bash
cd backend && uv run python ../evals/cli.py benchmark run todo_extraction_bench_v1 --all --allow-untracked
cd backend && uv run python ../evals/cli.py benchmark report todo_extraction_bench_v1 --json > ../.context/022_benchmark_report_full.json
```

7. Assert the four managed entries and cleanup:

```bash
cd backend && uv run python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("../.context/022_benchmark_report_full.json").read_text())
entries = {entry["entry_id"]: entry for entry in report["entries"]}
for entry_id in (
    "modal_outlines_qwen35_0_8b",
    "modal_outlines_qwen35_2b",
    "modal_outlines_qwen35_4b",
    "modal_outlines_qwen35_9b",
):
    entry = entries[entry_id]
    assert entry["status"] == "current", entry_id
    assert entry["selected_run_id"], entry_id
    assert entry["total_case_count"] > 0, entry_id
print("Gate 2 report assertions passed")
PY
pgrep -af "modal run scripts/qwen_sglang_outlines_smoke.py --mode serve" || true
```

Expected: the Python assertion prints success and the `pgrep` command prints nothing.

## Supporting Verification

- Benchmark contract and managed-session resolution:

```bash
cd backend && uv run pytest \
  tests/test_benchmark_definitions.py \
  tests/test_benchmark_extraction_runner.py::test_managed_modal_entry_resolves_runtime_contract \
  -q
```

- Transport injection and extraction family selection:

```bash
cd backend && uv run pytest \
  tests/test_extract.py \
  tests/test_extraction_runner.py \
  -q
```

- Managed launcher behavior:

```bash
cd backend && uv run pytest \
  tests/test_benchmark_extraction_runner.py::test_managed_session_launcher_reads_ready_payload \
  tests/test_benchmark_extraction_runner.py::test_managed_session_launcher_terminates_process_on_close \
  -q
```

- Report and metadata regression:

```bash
cd backend && uv run pytest \
  tests/test_benchmark_report.py \
  tests/test_eval_experiment_metadata.py \
  -q
```

## Tasks

### Task 1.1: Add the managed benchmark contract on top of merged 021

**Purpose:**
Keep the eight DeepInfra entries intact and add the four managed `modal-outlines` entries plus stable managed session config parsing.

**Files:**
- Modify: `evals/benchmarks/todo_extraction_bench_v1.yaml`
- Modify: `evals/models.py`
- Modify: `evals/resolution.py`
- Test: `backend/tests/test_benchmark_definitions.py`
- Test: `backend/tests/test_benchmark_extraction_runner.py`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Surfaces The Three-Family Qwen Comparison

- [ ] Write failing tests for the four managed entry ids, `implementation.family = "modal-outlines"`, and parsed `session` config.
- [ ] Run the focused benchmark-definition tests and confirm they fail for missing managed family support.
- [ ] Implement the benchmark YAML additions and resolved managed-session model.
- [ ] Re-run the focused benchmark-definition tests until they pass.

### Task 1.2: Add runtime transport override and managed family extraction path

**Purpose:**
Let benchmark-launched extraction runs talk to an injected OpenAI-compatible endpoint while preserving the merged DeepInfra family behavior.

**Files:**
- Modify: `backend/app/model_providers.py`
- Modify: `backend/app/extract.py`
- Modify: `backend/evals/extraction_quality/experiment_configs.py`
- Modify: `backend/evals/extraction_quality/run.py`
- Test: `backend/tests/test_extract.py`
- Test: `backend/tests/test_extraction_runner.py`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Surfaces The Three-Family Qwen Comparison
- Supporting Verification: transport injection and extraction family selection

- [ ] Write failing tests for runtime `base_url` injection, managed native output mode, and managed launch transport propagation.
- [ ] Run the focused extraction tests and confirm they fail.
- [ ] Implement the minimal runtime transport override and managed-family branching while preserving the merged DeepInfra `implementation_family` behavior.
- [ ] Re-run the focused extraction tests until they pass.

### Task 2.1: Implement managed session launcher and lifecycle orchestration

**Purpose:**
Make the benchmark runtime able to open, warm, reuse, and tear down managed Modal leases safely.

**Files:**
- Create: `evals/managed_sessions.py`
- Modify: `evals/run.py`
- Modify: `scripts/qwen_sglang_outlines_smoke.py`
- Test: `backend/tests/test_benchmark_extraction_runner.py`

**Supports:**
- Acceptance Gate: Managed Modal Benchmark Runs Are Warm And Cleaned Up

- [ ] Write failing tests for readiness parsing, warmup-before-execution ordering, teardown on failure, and one-live-lease behavior.
- [ ] Run the focused lifecycle tests and confirm they fail.
- [ ] Implement the managed lease launcher and benchmark grouping/orchestration.
- [ ] Re-run the focused lifecycle tests until they pass.

### Task 2.2: Update report/metadata regression coverage and execute the gates

**Purpose:**
Prove the managed family appears cleanly in reports and finish the live benchmark evidence for both acceptance gates.

**Files:**
- Modify: `backend/tests/test_benchmark_report.py`
- Modify: `backend/tests/test_eval_experiment_metadata.py`
- Modify: `evals/reports/todo_extraction_bench_v1.json`
- Modify: `evals/reports/todo_extraction_bench_v1.html`

**Supports:**
- Acceptance Gate: The Extraction Benchmark Surfaces The Three-Family Qwen Comparison
- Acceptance Gate: Managed Modal Benchmark Runs Are Warm And Cleaned Up

- [ ] Add or update report/metadata regression tests for the third family.
- [ ] Run the focused report/metadata tests until they pass.
- [ ] Execute the gate commands in `Gate Execution`.
- [ ] Save the benchmark artifacts and record the exact evidence required by both gates.

REQUIRED HANDOFF: superpowers:executing-plans
OPTIONAL HANDOFF: superpowers:subagent-driven-development
