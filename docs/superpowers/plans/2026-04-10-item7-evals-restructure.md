# Item 7 Evals Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move canonical eval datasets, benchmark definitions, benchmark-first CLI flows, and benchmark reporting into a top-level `evals/` area while preserving the existing production extraction path in `backend/app/` and phasing out the old backend-owned benchmarking layout.

**Architecture:** Treat repo-root `evals/` as the new canonical namespace for benchmark definitions, dataset files, public CLI entrypoints, execution planning, and report assembly. During migration, keep the provider-specific extraction and replay task implementations in `backend/evals/*` and bridge packaging with a lightweight CLI bootstrap so `cd backend && uv run ...` still works without a repo-wide Python packaging rewrite. Reuse the current benchmarking work where it helps, but replace the old path-first attached-run model with benchmark-ID-first loading, additive population, and "latest compatible result per entry" reporting. Benchmark definitions stay benchmark-owned; experiment metadata stays benchmark-agnostic; reports reconstruct benchmark state by matching entry definitions against experiment-scoped metadata.

**Tech Stack:** Python 3.13, Pydantic, Pydantic Evals, Logfire, pytest, httpx, PyYAML, existing extraction/replay runners in `backend/evals/*`

**Spec:** `docs/superpowers/specs/2026-04-10-item7-evals-restructure-design.md`

---

## Prerequisites

- Read the full Item 7 spec before editing anything. The benchmark file contract, report semantics, and phase gates are the scope boundary.
- Do not move production extraction code out of `backend/app/`. Item 7 is an eval-ownership refactor, not an app-architecture rewrite.
- Do not solve repo-wide packaging as part of this item. Use a namespace-package bridge plus explicit script bootstrapping where needed.
- Preserve evaluator semantics. The new benchmark flow can change orchestration and ownership, but it must not silently redefine what extraction or replay evaluators mean.
- Keep every phase green before starting the next one. Each phase in this plan has its own gate command and explicit stop condition.

## Public Bootstrap Contract

The public command model should match the spec:

```bash
benchmark list
benchmark show <benchmark_id>
benchmark run <benchmark_id>
benchmark run <benchmark_id> --all
benchmark report <benchmark_id>
```

Because the Python project still roots at `backend/`, the temporary invocation path during migration is:

```bash
cd backend && uv run python ../evals/cli.py benchmark list
```

Keep that bootstrap path in docs until a later item moves Python packaging to repo root. `evals/cli.py` should own whatever minimal `sys.path` bootstrap is needed for direct script execution; test-only bootstrap in `backend/tests/conftest.py` is not enough.

## File Map

### New repo-root eval surface

| File | Responsibility |
|------|----------------|
| `evals/cli.py` | Public benchmark-first CLI entrypoint and bootstrap path |
| `evals/models.py` | Typed dataset, benchmark-definition, benchmark-state, report, and benchmark-run-result models |
| `evals/storage.py` | Load canonical dataset JSON and benchmark YAML by benchmark ID |
| `evals/resolution.py` | Resolve benchmark entries into concrete extraction or replay execution configs |
| `evals/run.py` | Benchmark execution planning, additive population, and delegation into extraction/replay runners |
| `evals/report.py` | Benchmark-state assembly plus human-readable and JSON report output |
| `evals/logfire_query.py` | Logfire query helpers for benchmark-state reporting |
| `evals/datasets/extraction/todo_extraction_v1.json` | Canonical transcript-only extraction dataset |
| `evals/datasets/replay/todo_extraction_replay_v1.json` | Canonical incremental replay dataset |
| `evals/benchmarks/extraction_llm_matrix_v1.yaml` | Canonical extraction benchmark definition with explicit entries |
| `evals/benchmarks/replay_llm_matrix_v1.yaml` | Canonical replay benchmark definition with explicit entries |

### Backend support files to add

| File | Responsibility |
|------|----------------|
| `backend/tests/conftest.py` | Add repo root to `sys.path` before backend so namespace-package imports can see repo-root `evals/` |
| `backend/tests/test_item7_dataset_migration.py` | Phase 1 dataset migration acceptance tests |
| `backend/tests/test_item7_benchmark_definitions.py` | Phase 1 benchmark-definition acceptance tests |
| `backend/tests/test_item7_benchmark_cli.py` | Phase 2 benchmark CLI resolution and planning tests |
| `backend/tests/test_item7_extraction_runner.py` | Phase 2 extraction benchmark runner tests |
| `backend/tests/test_item7_replay_runner.py` | Phase 3 replay benchmark runner and additive population tests |
| `backend/tests/test_item7_benchmark_report.py` | Phase 3 benchmark-state reporting tests |
| `backend/tests/test_item7_logfire_report_integration.py` | Phase 3 live Logfire benchmark-report integration tests |
| `backend/tests/test_item7_benchmark_smoke_integration.py` | Phase 4 end-to-end smoke test for run + report through the new path |

### Existing backend files to modify

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `pyyaml` because benchmark definitions move to YAML |
| `backend/evals/common/experiment_metadata.py` | Preserve the experiment-scoped metadata contract and keep benchmark fields out of tracked run metadata |
| `backend/tests/test_eval_experiment_metadata.py` | Lock the benchmark-agnostic experiment metadata contract so Item 7 does not leak benchmark membership into tracked runs |
| `backend/evals/extraction_quality/run.py` | Expose an entry-config-driven execution path for benchmark entries without requiring legacy registry names |
| `backend/evals/incremental_extraction_quality/run.py` | Mirror the same benchmark-entry execution path for replay |
| `backend/evals/extraction_quality/experiment_configs.py` | Keep legacy registry available during migration, but expose helpers to compare benchmark entries against the legacy source of truth |
| `backend/evals/incremental_extraction_quality/experiment_configs.py` | Keep replay registry alias behavior aligned with the new benchmark-resolution path |
| `backend/evals/extraction_quality/dataset_loader.py` | Keep legacy loader behavior stable while cross-checking canonical top-level datasets |
| `backend/evals/incremental_extraction_quality/dataset_loader.py` | Same cross-check role for replay datasets |
| `backend/evals/extraction_quality/README.md` | Cut over docs to benchmark-first commands and top-level canonical assets |
| `backend/evals/incremental_extraction_quality/README.md` | Same documentation cutover for replay |

### Legacy backend benchmarking files to demote or delete in Phase 4

| File | Why it should go away or shrink |
|------|---------------------------------|
| `backend/evals/benchmarking/models.py` | Encodes the superseded axis-plus-attachment manifest contract |
| `backend/evals/benchmarking/storage.py` | Only supports the old path-first JSON manifest flow |
| `backend/evals/benchmarking/coverage.py` | Old coverage model is replaced by current benchmark-state assembly |
| `backend/evals/benchmarking/reporting.py` | Old report model does not satisfy Item 7 terminal or JSON output contracts |
| `backend/evals/benchmarking/logfire_query.py` | Query shape needs to move under repo-root `evals/` and expand for current-state selection |
| `backend/evals/benchmarking/suite_adapters.py` | Resolution must become benchmark-entry driven rather than axis-based |
| `backend/evals/benchmarking/run.py` | Either delete it or turn it into a narrow deprecation shim to the new CLI |
| `backend/evals/benchmarks/README.md` | Old manifest docs no longer define the canonical benchmark contract |
| `backend/evals/benchmarks/todo_extraction_model_smoke_v1.json` | Old attached-run smoke manifest should not remain the canonical example |
| `backend/tests/test_benchmark_cli.py` | Tests the superseded path-first CLI |
| `backend/tests/test_benchmark_coverage.py` | Tests the superseded coverage model |
| `backend/tests/test_benchmark_logfire_query.py` | Tests the superseded attached-run query shape |
| `backend/tests/test_benchmark_manifest.py` | Tests the superseded JSON manifest contract |
| `backend/tests/test_benchmark_reporting.py` | Tests the superseded report contract |
| `backend/tests/test_benchmark_suite_adapters.py` | Tests the superseded axis-based coordinate resolver |

### Existing files to reference while implementing

| File | Why it matters |
|------|----------------|
| `backend/app/extract.py` | Production extraction path that benchmark entries must call into |
| `backend/evals/extraction_quality/experiment_configs.py` | Legacy source of truth for existing experiment names and configs; use it to prove benchmark-entry equivalence |
| `backend/evals/incremental_extraction_quality/experiment_configs.py` | Replay suite reuses the extraction registry today |
| `backend/evals/extraction_quality/todo_extraction_v1.json` | Current transcript-only canonical data to migrate |
| `backend/evals/incremental_extraction_quality/todo_extraction_replay_v1.json` | Current replay canonical data to migrate |
| `backend/tests/fixtures/evals/todo_extraction_smoke.json` | Deterministic smoke dataset for local benchmark execution |
| `backend/tests/fixtures/evals/todo_extraction_replay_smoke.json` | Deterministic replay smoke dataset |
| `backend/evals/extraction_quality/results/2026-04-07T11-17-58Z/*.json` | Historical artifacts referenced by the spec's example report output |

---

## Task 1: Introduce the repo-root `evals/` namespace, canonical datasets, and explicit benchmark files

**Files:**
- Create: `evals/models.py`
- Create: `evals/storage.py`
- Create: `evals/resolution.py`
- Create: `evals/datasets/extraction/todo_extraction_v1.json`
- Create: `evals/datasets/replay/todo_extraction_replay_v1.json`
- Create: `evals/benchmarks/extraction_llm_matrix_v1.yaml`
- Create: `evals/benchmarks/replay_llm_matrix_v1.yaml`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_item7_dataset_migration.py`
- Create: `backend/tests/test_item7_benchmark_definitions.py`
- Modify: `backend/pyproject.toml`

This task establishes the new canonical file locations and the typed loaders that read them. Nothing should execute providers yet. The point is to prove that the new top-level assets match the current data and encode the explicit-entry benchmark contract from the spec.

- [ ] **Step 1: Write the failing dataset-migration tests**

Create `backend/tests/test_item7_dataset_migration.py` with focused assertions like:

```python
from pathlib import Path

from evals.storage import load_dataset_definition
from evals.extraction_quality.dataset_loader import load_extraction_quality_dataset
from evals.incremental_extraction_quality.dataset_loader import load_incremental_replay_dataset


def test_extraction_dataset_matches_legacy_case_ids():
    legacy = load_extraction_quality_dataset()
    current = load_dataset_definition(
        Path("../evals/datasets/extraction/todo_extraction_v1.json")
    )

    assert [row.id for row in current.rows] == [case.name for case in legacy.cases]


def test_replay_dataset_matches_legacy_case_ids():
    legacy = load_incremental_replay_dataset()
    current = load_dataset_definition(
        Path("../evals/datasets/replay/todo_extraction_replay_v1.json")
    )

    assert [row.id for row in current.rows] == [case.name for case in legacy.cases]
```

- [ ] **Step 2: Write the failing benchmark-definition tests**

Create `backend/tests/test_item7_benchmark_definitions.py` with contract checks like:

```python
from pathlib import Path

from evals.resolution import resolve_entry_config
from evals.storage import load_benchmark_definition


def test_extraction_benchmark_definition_parses_required_fields():
    benchmark = load_benchmark_definition(
        Path("../evals/benchmarks/extraction_llm_matrix_v1.yaml")
    )

    assert benchmark.benchmark_id == "extraction_llm_matrix_v1"
    assert benchmark.focus == "model"
    assert benchmark.headline_metric == "todo_count_match"
    assert benchmark.repeat >= 1
    assert benchmark.task_retries >= 0
    assert len({entry.id for entry in benchmark.entries}) == len(benchmark.entries)


def test_extraction_entry_matches_legacy_registry_values():
    benchmark = load_benchmark_definition(
        Path("../evals/benchmarks/extraction_llm_matrix_v1.yaml")
    )
    entry = next(entry for entry in benchmark.entries if entry.id == "gemini3_flash_default")
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.provider == "google-gla"
    assert resolved.model_name == "gemini-3-flash-preview"
    assert resolved.prompt_version == "v1"
```

- [ ] **Step 3: Run the Phase 1 tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_item7_dataset_migration.py tests/test_item7_benchmark_definitions.py -v
```

Expected: FAIL because the repo-root `evals/` files, YAML parsing support, and typed loaders do not exist yet.

- [ ] **Step 4: Add the bootstrap and parsing support**

Implement the minimum code to make the tests pass:

```python
# backend/tests/conftest.py
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
```

```python
# evals/models.py
from pydantic import BaseModel, Field


class DatasetRow(BaseModel):
    id: str
    input: dict
    expected_output: list[dict]
    metadata: dict = Field(default_factory=dict)


class DatasetDefinition(BaseModel):
    name: str
    version: str
    rows: list[DatasetRow]


class BenchmarkEntry(BaseModel):
    id: str
    label: str
    config: dict


class BenchmarkDefinition(BaseModel):
    benchmark_id: str
    dataset: str
    focus: str
    headline_metric: str
    repeat: int
    task_retries: int
    max_concurrency: int
    entries: list[BenchmarkEntry]
```

```python
# evals/storage.py
import json
from pathlib import Path

import yaml

from evals.models import BenchmarkDefinition, DatasetDefinition


def load_dataset_definition(path: Path) -> DatasetDefinition:
    return DatasetDefinition.model_validate(json.loads(path.read_text()))


def load_benchmark_definition(path: Path) -> BenchmarkDefinition:
    return BenchmarkDefinition.model_validate(yaml.safe_load(path.read_text()))
```

Also:
- add `pyyaml>=6` to `backend/pyproject.toml`
- copy the existing dataset content into the new top-level JSON files, converting to the spec's `name` / `version` / `rows` shape
- create the initial YAML benchmark files with explicit `entries`, not axis definitions

- [ ] **Step 5: Re-run the Phase 1 gate**

Run:

```bash
cd backend && uv run pytest tests/test_item7_dataset_migration.py tests/test_item7_benchmark_definitions.py -v
```

Expected: PASS with matching row counts, matching row IDs, and benchmark entries that resolve to the same provider/model/prompt values as the legacy registry.

- [ ] **Step 6: Commit the Phase 1 baseline**

```bash
git add \
  backend/pyproject.toml \
  backend/tests/conftest.py \
  backend/tests/test_item7_dataset_migration.py \
  backend/tests/test_item7_benchmark_definitions.py \
  evals/models.py \
  evals/resolution.py \
  evals/storage.py \
  evals/datasets/extraction/todo_extraction_v1.json \
  evals/datasets/replay/todo_extraction_replay_v1.json \
  evals/benchmarks/extraction_llm_matrix_v1.yaml \
  evals/benchmarks/replay_llm_matrix_v1.yaml
git commit -m "feat: add item7 eval datasets and benchmarks"
```

## Task 2: Add benchmark-ID-first discovery, show, and run planning

**Files:**
- Create: `evals/cli.py`
- Modify: `evals/resolution.py`
- Modify: `evals/storage.py`
- Create: `backend/tests/test_item7_benchmark_cli.py`

This task creates the public benchmark-first entrypoint and replaces path-first lookup with benchmark-ID resolution. Keep this task focused on discovery, show output, and selecting which entries would run. Do not assemble reports yet. `evals/cli.py` must be importable before `evals/run.py` and `evals/report.py` exist, so command handlers should use lazy imports or tiny wrapper functions rather than top-level imports of later-task modules.

- [ ] **Step 1: Write the failing CLI tests**

Create `backend/tests/test_item7_benchmark_cli.py` with assertions like:

```python
from types import SimpleNamespace

from evals.cli import main


def test_benchmark_list_prints_known_ids(capsys):
    exit_code = main(["benchmark", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "extraction_llm_matrix_v1" in captured.out
    assert "replay_llm_matrix_v1" in captured.out


def test_benchmark_show_prints_entry_labels_and_config(capsys):
    exit_code = main(["benchmark", "show", "extraction_llm_matrix_v1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Gemini 3 Flash / default" in captured.out
    assert "prompt_version" in captured.out


def test_benchmark_run_defaults_to_missing_entries(monkeypatch):
    planned = []
    monkeypatch.setattr(
        "evals.cli.run_benchmark",
        lambda **kwargs: planned.append(kwargs) or SimpleNamespace(executed_entry_ids=["mistral_small_4_default"]),
    )

    main(["benchmark", "run", "extraction_llm_matrix_v1"])

    assert planned[0]["all_entries"] is False
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_cli.py -v
```

Expected: FAIL because the repo-root CLI and benchmark-ID lookup do not exist yet.

- [ ] **Step 3: Implement the benchmark-first CLI and ID resolution**

Add a parser with the spec's command model:

```python
# evals/cli.py
import argparse
import asyncio

from evals.storage import list_benchmark_ids, load_benchmark_by_id


def run_benchmark(**kwargs):
    from evals.run import run_benchmark as _run_benchmark

    return asyncio.run(_run_benchmark(**kwargs))


def report_benchmark(**kwargs):
    from evals.report import report_benchmark as _report_benchmark

    return _report_benchmark(**kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark-first eval workflows.")
    root = parser.add_subparsers(dest="resource", required=True)
    benchmark = root.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="command", required=True)
    benchmark_sub.add_parser("list")
    show = benchmark_sub.add_parser("show")
    show.add_argument("benchmark_id")
    run = benchmark_sub.add_parser("run")
    run.add_argument("benchmark_id")
    run.add_argument("--all", action="store_true")
    run.add_argument("--dataset-path")
    run.add_argument("--allow-untracked", action="store_true")
    report = benchmark_sub.add_parser("report")
    report.add_argument("benchmark_id")
    report.add_argument("--json", action="store_true")
    return parser
```

In the same task:
- add `list_benchmark_ids()` and `load_benchmark_by_id()` to `evals/storage.py`
- add `resolve_entry_config()` in `evals/resolution.py` so `show` can print full config and later tasks can share the same logic
- make `benchmark run <id>` call a runner function with `all_entries=False` by default and `True` only when `--all` is present
- let the `report` subcommand exist in the parser now, but keep its implementation behind a lazy wrapper so importing `evals.cli` does not require `evals/report.py` before Task 5

- [ ] **Step 4: Re-run the Phase 2 CLI tests**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_cli.py -v
```

Expected: PASS with benchmark IDs listed, `show` surfacing entry labels plus full configs, and `run` forwarding the missing-only default correctly.

- [ ] **Step 5: Commit the CLI surface**

```bash
git add \
  backend/tests/test_item7_benchmark_cli.py \
  evals/cli.py \
  evals/resolution.py \
  evals/storage.py
git commit -m "feat: add benchmark-first eval cli"
```

## Task 3: Execute transcript-only extraction benchmarks from explicit benchmark entries

**Files:**
- Create: `backend/tests/test_item7_extraction_runner.py`
- Modify: `evals/models.py`
- Modify: `evals/run.py`
- Modify: `evals/resolution.py`
- Modify: `backend/evals/common/experiment_metadata.py`
- Modify: `backend/tests/test_eval_experiment_metadata.py`
- Modify: `backend/evals/extraction_quality/run.py`
- Modify: `backend/evals/extraction_quality/experiment_configs.py`

This task replaces "launch by legacy experiment name" as the primary mechanism. The benchmark runner should accept explicit entry configs from YAML, resolve them into concrete extraction configs, and call the existing production extraction path through the transcript-only eval runner. It must do that without adding benchmark IDs or benchmark entry IDs to tracked experiment metadata.

- [ ] **Step 1: Write the failing extraction benchmark runner tests**

Create `backend/tests/test_item7_extraction_runner.py` with assertions like:

```python
import asyncio
from types import SimpleNamespace

from evals.run import run_benchmark


def test_extraction_entry_resolves_to_legacy_equivalent():
    benchmark = load_benchmark_by_id("extraction_llm_matrix_v1")
    entry = next(entry for entry in benchmark.entries if entry.id == "gemini3_flash_default")
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
    legacy = EXPERIMENTS["gemini3_flash_default"]

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == legacy.provider
    assert resolved.model_name == legacy.extraction_config.model_name
    assert resolved.prompt_version == legacy.extraction_config.prompt_version


def test_extraction_runner_passes_entry_context_without_benchmark_leakage(monkeypatch, tmp_path):
    calls = []

    async def fake_launch(**kwargs):
        calls.append(kwargs)
        return {"entry_id": kwargs["entry"].id}

    monkeypatch.setattr(
        "evals.run.launch_extraction_entry",
        fake_launch,
    )

    asyncio.run(
        run_benchmark(
            benchmark_id="extraction_llm_matrix_v1",
            all_entries=True,
            dataset_path=tmp_path / "dataset.json",
            allow_untracked=True,
        )
    )

    assert calls[0]["entry"].id == "gemini3_flash_default"
    assert "benchmark" not in calls[0]
```

- [ ] **Step 2: Lock the metadata boundary first**

Add assertions to `backend/tests/test_eval_experiment_metadata.py` for the benchmark-agnostic contract:

```python
assert "benchmark_id" not in metadata
assert "benchmark_entry_id" not in metadata
assert metadata["dataset_sha"]
assert metadata["evaluator_contract_sha"]
assert metadata["experiment_id"]
assert metadata["config_fingerprint"]
```

- [ ] **Step 3: Run the extraction-runner tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_item7_extraction_runner.py tests/test_eval_experiment_metadata.py -v
```

Expected: FAIL because the benchmark runner cannot yet launch transcript entries directly from YAML config and the metadata boundary is not yet explicitly protected by tests.

- [ ] **Step 4: Implement explicit-entry extraction execution**

Make these focused changes:

```python
# evals/models.py
class BenchmarkRunResult(BaseModel):
    benchmark_id: str
    executed_entry_ids: list[str] = Field(default_factory=list)
    batch_ids: dict[str, str] = Field(default_factory=dict)
```

```python
# backend/evals/extraction_quality/run.py
async def launch_extraction_entry(
    *,
    entry: BenchmarkEntry,
    resolved_config: ResolvedEntryConfig,
    dataset_path: Path | None,
    repeat: int,
    task_retries: int,
    max_concurrency: int,
    allow_untracked: bool,
) -> dict[str, str]:
    experiment = experiment_definition_from_resolved_config(
        experiment_name_hint=entry.id,
        resolved_config=resolved_config,
    )
    return await launch_experiments_for_definitions(
        experiments=[experiment],
        dataset_path=dataset_path,
        repeat=repeat,
        task_retries=task_retries,
        max_concurrency=max_concurrency,
        allow_untracked=allow_untracked,
    )
```

```python
# evals/run.py
from evals.models import BenchmarkRunResult
from evals.resolution import build_entry_query_selector


async def run_benchmark(*, benchmark_id: str, all_entries: bool, dataset_path: Path | None = None, allow_untracked: bool):
    benchmark = load_benchmark_by_id(benchmark_id)
    state = load_current_benchmark_state(benchmark)
    entries = selected_entries(
        benchmark=benchmark,
        current_state=state,
        all_entries=all_entries,
    )
    batch_ids: dict[str, str] = {}
    for entry in entries:
        resolved = resolve_entry_config(benchmark=benchmark, entry=entry)
        if resolved.suite == "extraction_quality":
            result = await launch_extraction_entry(
                entry=entry,
                resolved_config=resolved,
                dataset_path=dataset_path,
                allow_untracked=allow_untracked,
            )
            if result.get("batch_id"):
                batch_ids[entry.id] = result["batch_id"]
    return BenchmarkRunResult(
        benchmark_id=benchmark.benchmark_id,
        executed_entry_ids=[entry.id for entry in entries],
        batch_ids=batch_ids,
    )
```

Important constraints:
- keep `backend/app/extract.py` as the task implementation
- allow direct config-driven execution even when no legacy experiment name exists
- keep benchmark-entry matching logic in one place: `evals/resolution.py`
- still compare benchmark entries to the legacy registry in tests for current shared entries

- [ ] **Step 5: Re-run the Phase 2 extraction gate**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_cli.py tests/test_item7_extraction_runner.py tests/test_eval_experiment_metadata.py -v
```

Expected: PASS with benchmark entry configs resolving cleanly, extraction launches passing entry context without benchmark membership metadata, and no live provider dependency in the tests.

- [ ] **Step 6: Commit the extraction runner cut-in**

```bash
git add \
  backend/evals/common/experiment_metadata.py \
  backend/evals/extraction_quality/experiment_configs.py \
  backend/evals/extraction_quality/run.py \
  backend/tests/test_eval_experiment_metadata.py \
  backend/tests/test_item7_extraction_runner.py \
  evals/models.py \
  evals/resolution.py \
  evals/run.py
git commit -m "feat: run extraction benchmarks from item7 entries"
```

## Task 4: Extend the new benchmark runner to replay and additive population

**Files:**
- Create: `backend/tests/test_item7_replay_runner.py`
- Modify: `evals/run.py`
- Modify: `evals/resolution.py`
- Modify: `backend/evals/incremental_extraction_quality/run.py`
- Modify: `backend/evals/incremental_extraction_quality/experiment_configs.py`

This task teaches the new benchmark runner how to execute replay datasets through the same benchmark contract and how to skip already populated entries by default, while keeping replay runs benchmark-agnostic in Logfire.

- [ ] **Step 1: Write the failing replay-runner tests**

Create `backend/tests/test_item7_replay_runner.py` with assertions like:

```python
import asyncio
from types import SimpleNamespace

from evals.run import run_benchmark


def test_replay_entry_uses_incremental_suite():
    benchmark = load_benchmark_by_id("replay_llm_matrix_v1")
    entry = benchmark.entries[0]
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "incremental_extraction_quality"
    assert resolved.dataset_family == "replay"


def test_default_run_skips_already_populated_entries(monkeypatch):
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(
            current_entry_ids={"gemini3_flash_default"},
        ),
    )
    launched = []
    async def fake_launch(**kwargs):
        launched.append(kwargs["entry"].id)

    monkeypatch.setattr(
        "evals.run.launch_replay_entry",
        fake_launch,
    )

    asyncio.run(
        run_benchmark(
            benchmark_id="replay_llm_matrix_v1",
            all_entries=False,
            dataset_path=None,
            allow_untracked=True,
        )
    )

    assert "gemini3_flash_default" not in launched


def test_all_flag_forces_full_replay_rerun(monkeypatch):
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(
            current_entry_ids={entry.id for entry in benchmark.entries},
        ),
    )
    launched = []
    async def fake_launch(**kwargs):
        launched.append(kwargs["entry"].id)

    monkeypatch.setattr(
        "evals.run.launch_replay_entry",
        fake_launch,
    )

    asyncio.run(
        run_benchmark(
            benchmark_id="replay_llm_matrix_v1",
            all_entries=True,
            dataset_path=None,
            allow_untracked=True,
        )
    )

    assert launched
```

- [ ] **Step 2: Run the replay-runner tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_item7_replay_runner.py -v
```

Expected: FAIL because the new runner does not yet branch by dataset family or consult current benchmark state before planning launches.

- [ ] **Step 3: Implement replay execution and additive population**

Add:

```python
# backend/evals/incremental_extraction_quality/run.py
async def launch_replay_entry(
    *,
    entry: BenchmarkEntry,
    resolved_config: ResolvedEntryConfig,
    dataset_path: Path | None,
    repeat: int,
    task_retries: int,
    max_concurrency: int,
    allow_untracked: bool,
) -> dict[str, str]:
    experiment = experiment_definition_from_resolved_config(
        experiment_name_hint=entry.id,
        resolved_config=resolved_config,
    )
    return await launch_experiments_for_definitions(
        experiments=[experiment],
        dataset_path=dataset_path,
        repeat=repeat,
        task_retries=task_retries,
        max_concurrency=max_concurrency,
        allow_untracked=allow_untracked,
    )
```

Update `evals/run.py` so it:
- infers extraction vs replay from the loaded benchmark dataset path or row shape
- asks a state helper which entries are already populated
- skips populated entries unless `all_entries=True`
- delegates replay rows to the incremental runner while preserving the prior-todo threading semantics already covered by existing replay tests

Keep the planner deterministic:
- no live provider calls in the tests
- no live Logfire requirement for missing-entry planning
- reuse the same `build_entry_query_selector()` helper that reporting will use
  later so execution planning and reporting share one compatibility contract
- keep the runner contract explicit: `run_benchmark()` returns a
  `BenchmarkRunResult` with executed entry IDs plus any tracked batch IDs, and
  the CLI prints a concise execution summary from that object rather than
  depending on implicit launcher return shapes

- [ ] **Step 4: Re-run the Phase 3 replay gate**

Run:

```bash
cd backend && uv run pytest tests/test_item7_replay_runner.py -v
```

Expected: PASS with replay entries resolved correctly, default runs skipping populated entries, and `--all` forcing rerun planning.

- [ ] **Step 5: Commit the replay runner support**

```bash
git add \
  backend/evals/incremental_extraction_quality/experiment_configs.py \
  backend/evals/incremental_extraction_quality/run.py \
  backend/tests/test_item7_replay_runner.py \
  evals/resolution.py \
  evals/run.py
git commit -m "feat: support replay benchmarks and additive population"
```

## Task 5: Assemble current benchmark state and expose the Item 7 report contract

**Files:**
- Create: `evals/logfire_query.py`
- Modify: `evals/models.py`
- Modify: `evals/report.py`
- Modify: `evals/cli.py`
- Create: `backend/tests/test_item7_benchmark_report.py`
- Create: `backend/tests/test_item7_logfire_report_integration.py`

This task replaces the old "attached runs only" report semantics with the Item 7 contract: one stable benchmark, one current entry state per benchmark entry, missing entries shown explicitly, and older runs retained as history rather than treated as the primary user-facing concept. Report assembly must reconstruct benchmark state from benchmark definitions plus experiment-scoped metadata, not from benchmark-tagged experiment records. The same selector contract used to decide compatibility for a benchmark entry should be reused here rather than reinvented in a second helper.

- [ ] **Step 1: Write the failing local report tests**

Create `backend/tests/test_item7_benchmark_report.py` with assertions like:

```python
from evals.report import build_benchmark_report


def test_report_marks_missing_entries_instead_of_omitting_them():
    report = build_benchmark_report(
        benchmark_id="extraction_llm_matrix_v1",
        query_client=FakeBenchmarkQueryClient(rows=[]),
    )
    assert "deepinfra_qwen35_9b_default" in report.missing_entry_ids


def test_report_uses_latest_compatible_result_per_entry():
    report = build_benchmark_report(
        benchmark_id="extraction_llm_matrix_v1",
        query_client=FakeBenchmarkQueryClient(rows=HISTORY_ROWS),
    )
    entry = next(row for row in report.entries if row.entry_id == "gemini3_flash_default")
    assert entry.status == "current"
    assert entry.selected_run_id == "run-newer-compatible"


def test_terminal_report_contains_failures_and_slowest_cases_sections():
    rendered = render_terminal_report(
        build_benchmark_report(
            benchmark_id="extraction_llm_matrix_v1",
            query_client=FakeBenchmarkQueryClient(rows=HISTORY_ROWS),
        )
    )
    assert "Failures" in rendered
    assert "Slowest Cases" in rendered
```

- [ ] **Step 2: Write the failing live Logfire integration test**

Create `backend/tests/test_item7_logfire_report_integration.py` so it only runs when the dedicated dev-project env vars are present:

```python
import pytest

from evals.report import build_benchmark_report


pytestmark = pytest.mark.skipif(
    not os.getenv("LOGFIRE_READ_TOKEN") or not os.getenv("LOGFIRE_PROJECT_NAME"),
    reason="requires dedicated Logfire dev project",
)
```

The integration test should:
- query a dedicated dev project
- fetch real tracked benchmark runs
- assert that the selected current result for each populated entry is the latest compatible one

- [ ] **Step 3: Run the local report tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_report.py -v
```

Expected: FAIL because report assembly and rendering do not yet understand benchmark-state selection, missing entries, or the new terminal output contract.

- [ ] **Step 4: Implement report assembly and rendering**

Model the report around entry state, not attached-run membership:

```python
# evals/models.py
class BenchmarkEntryState(BaseModel):
    entry_id: str
    label: str
    status: Literal["current", "missing"]
    selected_run_id: str | None = None
    selected_timestamp: datetime | None = None
    headline_metric: str | None = None
    completed_case_count: int = 0
    failure_count: int = 0
    average_case_duration_s: float | None = None
    max_case_duration_s: float | None = None
    cost_usd: float | None = None
    config: dict
```

```python
# evals/report.py
def build_benchmark_report(*, benchmark_id: str, query_client: LogfireQueryClient | None = None) -> BenchmarkReport:
    benchmark = load_benchmark_by_id(benchmark_id)
    history = query_client.fetch_candidate_runs(
        selectors=[
            build_entry_query_selector(benchmark=benchmark, entry=entry)
            for entry in benchmark.entries
        ]
    )
    current_states = select_latest_compatible_results(benchmark, history)
    return BenchmarkReport(
        benchmark_id=benchmark.benchmark_id,
        focus=benchmark.focus,
        headline_metric=benchmark.headline_metric,
        entries=current_states,
        missing_entry_ids=[state.entry_id for state in current_states if state.status == "missing"],
    )
```

```python
# evals/logfire_query.py
def fetch_candidate_runs(self, selectors: list[EntryQuerySelector]) -> list[dict[str, Any]]:
    # query by experiment-scoped compatibility fields derived from benchmark
    # entries; do not query by benchmark_id because tracked runs are
    # benchmark-agnostic
    sql = build_candidate_runs_query(selectors)
    payload = self._run_query(sql)
    return normalize_benchmark_rows(payload)
```

Also make `benchmark report <id>` support:
- default terminal output
- `--json` machine-readable output with full entry configs and history references
- and keep the matching contract explicit in code so a benchmark report can be
  rebuilt from benchmark definitions plus experiment metadata alone
- do not expect untracked smoke runs to appear in the report; benchmark state is
  built from tracked execution history only

- [ ] **Step 5: Re-run the local report gate**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_report.py -v
```

Expected: PASS with terminal summaries, explicit missing entries, latest-compatible selection, and JSON output containing full configs plus compatibility metadata.

- [ ] **Step 6: Run the live Logfire gate**

Run:

```bash
cd backend && uv run pytest tests/test_item7_logfire_report_integration.py -v
```

Expected: PASS against the dedicated Logfire dev project, or SKIP only when the required dev-project credentials are intentionally absent in the current environment.

- [ ] **Step 7: Commit the report layer**

```bash
git add \
  backend/tests/test_item7_benchmark_report.py \
  backend/tests/test_item7_logfire_report_integration.py \
  evals/cli.py \
  evals/logfire_query.py \
  evals/models.py \
  evals/report.py
git commit -m "feat: add item7 benchmark reporting"
```

## Task 6: Cut over docs, demote legacy backend benchmarking, and validate the full new flow

**Files:**
- Create: `backend/tests/test_item7_benchmark_smoke_integration.py`
- Modify: `backend/evals/extraction_quality/README.md`
- Modify: `backend/evals/incremental_extraction_quality/README.md`
- Modify or Delete: `backend/evals/benchmarking/run.py`
- Delete: `backend/evals/benchmarking/models.py`
- Delete: `backend/evals/benchmarking/storage.py`
- Delete: `backend/evals/benchmarking/coverage.py`
- Delete: `backend/evals/benchmarking/reporting.py`
- Delete: `backend/evals/benchmarking/logfire_query.py`
- Delete: `backend/evals/benchmarking/suite_adapters.py`
- Delete or Replace: `backend/evals/benchmarks/README.md`
- Delete: `backend/evals/benchmarks/todo_extraction_model_smoke_v1.json`
- Delete: `backend/tests/test_benchmark_cli.py`
- Delete: `backend/tests/test_benchmark_coverage.py`
- Delete: `backend/tests/test_benchmark_logfire_query.py`
- Delete: `backend/tests/test_benchmark_manifest.py`
- Delete: `backend/tests/test_benchmark_reporting.py`
- Delete: `backend/tests/test_benchmark_suite_adapters.py`

This task finishes the ownership shift. The new top-level `evals/` area becomes primary, old benchmark docs/tests stop encoding the wrong contract, and any retained legacy entrypoint becomes an intentional compatibility shim rather than a shadow system. The end-to-end `benchmark run ...` plus `benchmark report ...` smoke path is a live dev-environment check in this item, not a deterministic offline subprocess test. Do not introduce a broad fake-provider or dependency-injected execution architecture just to make that public CLI smoke path run locally without real providers.

- [ ] **Step 1: Write the failing compatibility test and the gated live smoke check**

Create `backend/tests/test_item7_benchmark_smoke_integration.py` with coverage for:

```python
def test_cli_bootstrap_list_works_without_live_providers():
    result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "list",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "extraction_llm_matrix_v1" in result.stdout


@pytest.mark.skipif(
    not os.getenv("ITEM7_ENABLE_LIVE_SMOKE")
    or not os.getenv("LOGFIRE_TOKEN")
    or not os.getenv("LOGFIRE_READ_TOKEN")
    or not os.getenv("LOGFIRE_PROJECT_NAME"),
    reason="requires dedicated Logfire dev project",
)
def test_tracked_benchmark_run_then_report_state():
    tracked_run_result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "run",
            "extraction_llm_matrix_v1",
            "--dataset-path",
            "tests/fixtures/evals/todo_extraction_smoke.json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert tracked_run_result.returncode == 0

    report_result = subprocess.run(
        [
            sys.executable,
            "../evals/cli.py",
            "benchmark",
            "report",
            "extraction_llm_matrix_v1",
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert report_result.returncode == 0
    assert '"benchmark_id": "extraction_llm_matrix_v1"' in report_result.stdout
    assert '"entries"' in report_result.stdout


def test_legacy_benchmark_entrypoint_is_a_shim_or_intentional_deprecation():
    result = subprocess.run(
        [sys.executable, "evals/benchmarking/run.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in {0, 1}
    assert "benchmark" in (result.stdout + result.stderr).lower()
```

The compatibility assertion should accept one of two outcomes:
- the old `backend/evals/benchmarking/run.py` delegates to the new CLI
- or it exits with a clear deprecation message pointing to `../evals/cli.py benchmark ...`

The live smoke check is intentionally gated behind real dev-project credentials:
- it also requires explicit opt-in via `ITEM7_ENABLE_LIVE_SMOKE=1` so the local
  deterministic gate cannot become live accidentally when credentials are present
- it is allowed to hit real providers
- it is allowed to populate tracked benchmark state in a dedicated dev project
- it is not required to pass in the always-green deterministic local gate

- [ ] **Step 2: Run the compatibility test target to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_item7_benchmark_smoke_integration.py -v
```

Expected: FAIL because the CLI bootstrap and legacy-entrypoint compatibility behavior are not fully wired yet. The live tracked run-to-report smoke path will still be present in the file, but it should SKIP unless the dedicated dev-project credentials are available.

- [ ] **Step 3: Cut over documentation and remove the old benchmark contract**

Make these changes:
- rewrite both eval READMEs around repo-root canonical datasets, repo-root benchmark files, and `python ../evals/cli.py benchmark ...`
- either delete `backend/evals/benchmarking/run.py` or replace it with a tiny shim:

```python
raise SystemExit(
    "Deprecated: use `cd backend && uv run python ../evals/cli.py benchmark ...`."
)
```

- delete the rest of the old benchmarking modules and obsolete tests once the new replacements are green
- remove the old JSON benchmark example so the repo has only one benchmark contract
- do not add a test-only fake provider backend or a broad dependency-injected execution layer solely to make the public CLI smoke path run offline in Item 7

- [ ] **Step 4: Run the full local Item 7 gate**

Run:

```bash
cd backend && uv run pytest \
  tests/test_item7_dataset_migration.py \
  tests/test_item7_benchmark_definitions.py \
  tests/test_item7_benchmark_cli.py \
  tests/test_item7_extraction_runner.py \
  tests/test_eval_experiment_metadata.py \
  tests/test_item7_replay_runner.py \
  tests/test_item7_benchmark_report.py \
  tests/test_item7_benchmark_smoke_integration.py -v
```

Expected: PASS with the repo-root `evals/` flow as the only canonical benchmark path, the local deterministic compatibility checks green, and the live smoke test skipped unless both the explicit opt-in flag and the dev-project credentials are present.

- [ ] **Step 5: Run the final live Logfire gate**

Run:

```bash
cd backend && ITEM7_ENABLE_LIVE_SMOKE=1 uv run pytest \
  tests/test_item7_logfire_report_integration.py \
  tests/test_item7_benchmark_smoke_integration.py -v
```

Expected: PASS against the dedicated Logfire dev project, including the live run-then-report smoke path with real provider execution where needed.

- [ ] **Step 6: Commit the cutover**

```bash
git add docs/superpowers/plans/2026-04-10-item7-evals-restructure.md
git add \
  backend/evals/extraction_quality/README.md \
  backend/evals/incremental_extraction_quality/README.md \
  backend/tests/test_item7_benchmark_smoke_integration.py \
  evals
git rm \
  backend/evals/benchmarking/models.py \
  backend/evals/benchmarking/storage.py \
  backend/evals/benchmarking/coverage.py \
  backend/evals/benchmarking/reporting.py \
  backend/evals/benchmarking/logfire_query.py \
  backend/evals/benchmarking/suite_adapters.py \
  backend/evals/benchmarks/todo_extraction_model_smoke_v1.json \
  backend/tests/test_benchmark_cli.py \
  backend/tests/test_benchmark_coverage.py \
  backend/tests/test_benchmark_logfire_query.py \
  backend/tests/test_benchmark_manifest.py \
  backend/tests/test_benchmark_reporting.py \
  backend/tests/test_benchmark_suite_adapters.py
git commit -m "refactor: cut over evals to item7 benchmark layout"
```

---

## Verification Summary

Use these gates exactly. Do not skip ahead.

### Phase 1 gate

```bash
cd backend && uv run pytest tests/test_item7_dataset_migration.py tests/test_item7_benchmark_definitions.py -v
```

### Phase 2 gate

```bash
cd backend && uv run pytest tests/test_item7_benchmark_cli.py tests/test_item7_extraction_runner.py tests/test_eval_experiment_metadata.py -v
```

### Phase 3 local gate

```bash
cd backend && uv run pytest tests/test_item7_replay_runner.py tests/test_item7_benchmark_report.py tests/test_eval_experiment_metadata.py -v
```

### Phase 3 live Logfire gate

```bash
cd backend && uv run pytest tests/test_item7_logfire_report_integration.py -v
```

### Phase 4 full local gate

```bash
cd backend && uv run pytest \
  tests/test_item7_dataset_migration.py \
  tests/test_item7_benchmark_definitions.py \
  tests/test_item7_benchmark_cli.py \
  tests/test_item7_extraction_runner.py \
  tests/test_eval_experiment_metadata.py \
  tests/test_item7_replay_runner.py \
  tests/test_item7_benchmark_report.py \
  tests/test_item7_benchmark_smoke_integration.py -v
```

### Phase 4 live gate

```bash
cd backend && ITEM7_ENABLE_LIVE_SMOKE=1 uv run pytest \
  tests/test_item7_logfire_report_integration.py \
  tests/test_item7_benchmark_smoke_integration.py -v
```

## Manual Validation

After the automated gates pass, run these operator checks.

Local deterministic checks:

1. `cd backend && uv run python ../evals/cli.py benchmark list`
   Expected: both `extraction_llm_matrix_v1` and `replay_llm_matrix_v1` appear.
2. `cd backend && uv run python ../evals/cli.py benchmark show extraction_llm_matrix_v1`
   Expected: each entry prints a human-readable label plus the full config block.

Live dev-environment checks:

3. Ensure `LOGFIRE_TOKEN`, `LOGFIRE_READ_TOKEN`, and `LOGFIRE_PROJECT_NAME` point to the dedicated dev project, and ensure real provider credentials for the benchmark entries are available in the environment.
4. `cd backend && ITEM7_ENABLE_LIVE_SMOKE=1 uv run python ../evals/cli.py benchmark run extraction_llm_matrix_v1 --dataset-path tests/fixtures/evals/todo_extraction_smoke.json`
   Expected: tracked run succeeds against the dev environment, launches only missing entries by default, and prints a run summary or batch identifier.
5. `cd backend && uv run python ../evals/cli.py benchmark report extraction_llm_matrix_v1`
   Expected: terminal output shows the benchmark header, population summary, row-per-entry summary, `Failures`, and `Slowest Cases` based on tracked history.
6. `cd backend && uv run python ../evals/cli.py benchmark report extraction_llm_matrix_v1 --json`
   Expected: JSON includes benchmark metadata, compatibility metadata, current entry states, missing entry IDs, and full configs.
7. Optional additive-population check: rerun `cd backend && uv run python ../evals/cli.py benchmark run extraction_llm_matrix_v1 --dataset-path tests/fixtures/evals/todo_extraction_smoke.json`
   Expected: entries already populated by the prior tracked run are skipped unless `--all` is added.

## Risks To Watch

- Namespace-package import order can silently flip if `backend/tests/conftest.py` or CLI bootstrap logic is incomplete. Keep import-path tests simple and explicit.
- YAML benchmark definitions add a new parser dependency. Add `pyyaml` in the same commit as the loader so CI does not fail halfway through the migration.
- Report compatibility selection is the hardest behavioral change. Keep the compatibility fingerprint logic in one helper and test it directly.
- Do not let the legacy benchmarking files linger as second sources of truth. Once the new path is green, either delete them or reduce them to obvious deprecation shims.
