# Item 11 Design: Extraction And Replay Dataset Curation

Scope: improve the current count-only transcript-to-todo dataset and the
current count-only replay dataset so the existing benchmarks are more useful
for model comparison.

## Why this exists

The current extraction dataset is too small and too easy for
`todo_count_match`. It does not put enough pressure on the benchmark's current
scoring contract.

This item keeps both benchmarks narrow on purpose. The goal is not to design
new evaluators yet. The goal is to make the current count benchmarks worth
running.

## Goals

- remove the outdated repo-local dataset curation workflow
- keep the hosted Logfire dataset as the curation source of truth
- keep the local benchmark lock as the only benchmark-owned local dataset artifact
- expand the current extraction dataset to roughly 20-30 curated cases
- expand the current replay dataset beyond the current four lightweight cases
- stress actionability boundary and todo boundarying
- include noisier and denser transcript shapes that make count extraction harder
- add replay cases where misleading partial transcripts can corrupt the final count
- keep the existing benchmark metric, runner, and experiment matrix
- rerun the current extraction and replay benchmarks against the improved datasets

## Non-goals

- changing benchmark behavior, metrics, or stale/rebase semantics
- incremental benchmark expansion in this item
- schema simplification
- title, due date, assignee, or category evaluators
- replacing `todo_count_match`
- changing the extraction prompt or model matrix
- changing `final_todo_count_match`

## Phase 1: Hosted Dataset Source Of Truth Refactor

### Objective

Remove the outdated repo-local dataset curation path so the benchmark contract
is simply `hosted dataset -> local benchmark lock`, without changing benchmark
behavior.

### Behavioral delta

Before this phase, the repo still carries local canonical dataset JSONs, backend
mirror JSONs, a bootstrap sync script, and tests tied to that workflow. After
this phase, benchmark execution still behaves the same, but the accepted data
contract is:

- hosted Logfire dataset for curation
- local lock file for benchmark execution
- fixtures for smoke and parser verification

### Non-goals

- changing benchmark outputs or evaluator logic
- changing the extraction or replay datasets themselves
- changing the benchmark runner stale-detection behavior
- changing prompt, model, or matrix configuration

### Acceptance gates

1. A normal benchmark run using a benchmark's `hosted_dataset` still succeeds
   through the CLI, writes or reuses the benchmark lock under
   `evals/locks/<benchmark_id>.json`, and can be reported afterward.
2. Extraction and replay smoke runs still work with explicit fixture-based
   `--dataset-path` overrides, proving the runners no longer depend on repo
   dataset files for verification.
3. The repo-local canonical datasets, backend mirror datasets, bootstrap sync
   script, and migration/bootstrap tests are removed or replaced so they are no
   longer part of the benchmark contract.
4. The existing benchmark definitions are renamed to the approved benchmark
   names:
   - `todo_extraction_bench_v1`
   - `todo_replay_bench_v1`
   and the CLI, docs, and lock/report references use those names consistently.

### Supporting verification

- `backend/tests/test_item7_benchmark_cli.py`
- `backend/tests/test_item7_benchmark_smoke_integration.py`
- `backend/tests/test_extraction_runner.py`
- `backend/tests/test_incremental_extraction_runner.py`
- fixture-based parser tests replacing the current dataset-loader and migration
  tests

### Phase boundary rule

Do not start extraction dataset curation until this refactor lands and the
benchmark contract is hosted dataset plus local lock only.

## Phase 2: Curated Count Benchmark

### Objective

Replace the current lightweight extraction dataset with a curated count-only
dataset that gives the benchmark meaningful discriminatory power.

### Behavioral delta

Before this item, the extraction benchmark runs on a tiny, mostly saturated
dataset. After this item, the same benchmark runs on a curated dataset with
roughly 20-30 cases covering the intended count failure modes.

### Non-goals

- changing the hosted dataset plus lock workflow from Phase 1
- expanding replay coverage in this phase
- adding field-level evaluators or schema changes
- changing prompt, model, or matrix configuration

### Dataset decisions

- keep the benchmark transcript-only
- keep the metric `todo_count_match`
- target 20-30 cases
- use tags only as curation metadata, not as separate metrics
- remove the current `stop` control-utterance case
- prefer slightly noisy or mixed-signal transcripts over dry toy examples

### Dimensions in scope

Primary dimensions:

- actionability boundary
- todo boundarying

Difficulty modifiers:

- ASR noise
- dense transcript structure
- mixed signal / filler / commentary
- correction, cancellation, and duplicate mentions

### Dataset shape

The curated set should include:

- clear single-todo positives
- clear multi-todo positives
- clear no-todo negatives
- borderline actionability cases
- over-splitting traps
- under-splitting traps
- correction / cancellation cases
- duplicate / repeated-task cases
- noisier ASR-style cases
- longer integration-style cases that combine multiple risks

Recommended metadata tags:

- `negative`
- `borderline_actionability`
- `duplicate`
- `cancel`
- `correction`
- `merge_instruction`
- `over_split_risk`
- `under_split_risk`
- `asr_noise`
- `dense_structure`
- `mixed_signal`
- `past_vs_new`
- `delegation`

### Acceptance gates

1. The hosted extraction dataset is updated to the curated 20-30 case set with
   the approved case mix, metadata tags, and expected counts.
2. The existing extraction benchmark definition
   `todo_extraction_bench_v1` is run against the updated hosted dataset,
   creating the local lock on first run or refreshing it on a rebase run.
3. The extraction benchmark report reflects the updated dataset state.

### Supporting verification

- `backend/tests/test_item7_benchmark_cli.py`
- `backend/tests/test_item7_benchmark_smoke_integration.py`
- fixture-based extraction parser tests if loader code changes
- extraction runner tests using explicit dataset fixtures or lock-shaped fixtures
  if runner code changes

### Phase boundary rule

Do not start incremental benchmark expansion, schema changes, or focused field
evaluators until this curated count benchmark has been populated and rerun.

## Phase 3: Curated Replay Count Benchmark

### Objective

Replace the current replay dataset with a curated replay set that stresses
recovery from misleading partial transcripts while keeping the final-count-only
metric.

### Behavioral delta

Before this phase, the replay benchmark runs on four light cases, including a
single-step case that barely exercises replay behavior. After this phase, the
same benchmark runs on a curated replay dataset with realistic multi-step cuts,
more noise, and explicit recovery pressure.

### Non-goals

- changing the hosted dataset plus lock workflow from Phase 1
- revisiting extraction dataset curation from Phase 2
- adding step-level evaluators or field-level judges
- changing prompt, model, or matrix configuration

### Dataset decisions

- keep the replay benchmark count-only with `final_todo_count_match`
- replace the current replay rows rather than keep them as seeds
- keep the core vs stretch distinction
- prefer realistic cumulative transcript snapshots over synthetic fragments
- avoid mid-word cuts in the replay dataset design
- use longer, noisier steps that better reflect endpointing and threshold-driven
  extraction checkpoints

### Dimensions in scope

Replay-specific dimensions:

- recovery from misleading partial transcripts
- late emergence of additional todos
- duplicate recovery
- merge recovery
- cancellation / removal recovery

Difficulty modifiers:

- ASR noise
- dense transcript structure
- mixed signal / filler / commentary
- recap-driven repetition

### Approved replay seed set

Core cases:

- `email-lunch-dentist-incomplete`
  - final count: `2`
  - steps:
    1. `Okay, I need to email Sarah about lunch, and then I need to, um,`
    2. `Okay, I need to email Sarah about lunch, and then I need to, um, book the dentist sometime tomorrow, but not first thing,`
    3. `Okay, I need to email Sarah about lunch, and then I need to, um, book the dentist sometime tomorrow, but not first thing, that's the other thing I keep forgetting.`
- `buy-bread-merge`
  - final count: `1`
  - steps:
    1. `I need to buy milk, and I need to buy, um,`
    2. `I need to buy milk, and I need to buy, um, bread for tomorrow, but actually that's`
    3. `I need to buy milk, and I need to buy, um, bread for tomorrow, but actually that's one grocery run, not two separate things.`
- `invoice-cancel`
  - final count: `0`
  - steps:
    1. `I should send Lena the invoice tonight, um, before I forget,`
    2. `I should send Lena the invoice tonight, um, before I forget, although actually no,`
    3. `I should send Lena the invoice tonight, um, before I forget, although actually no, don't send it yet because the numbers are still wrong.`
- `goat-to-oat-correction`
  - final count: `1`
  - steps:
    1. `I need to pick up goat milk for Sarah tonight, um,`
    2. `I need to pick up goat milk for Sarah tonight, um, no, sorry, not goat milk,`
    3. `I need to pick up goat milk for Sarah tonight, um, no, sorry, not goat milk, oat milk, because she's vegan.`
- `god-milk-asr-context`
  - final count: `1`
  - steps:
    1. `I need to pick up god milk for Sarah tonight, um,`
    2. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick,`
    3. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick, and the oat one from the organic store is the one she can have.`
- `past-then-live`
  - final count: `1`
  - steps:
    1. `I already emailed the landlord about the leak, and now I just need to, um,`
    2. `I already emailed the landlord about the leak, and now I just need to, um, call the plumber tomorrow,`
    3. `I already emailed the landlord about the leak, and now I just need to, um, call the plumber tomorrow, because it's still dripping under the sink.`

Stretch cases:

- `testing-then-agenda`
  - final count: `1`
  - steps:
    1. `Okay, I'm mostly testing this thing again, because I want to see if it catches the whole transcript when I kind of ramble,`
    2. `Okay, I'm mostly testing this thing again, because I want to see if it catches the whole transcript when I kind of ramble, and talk about reminders and tasks and all that,`
    3. `Okay, I'm mostly testing this thing again, because I want to see if it catches the whole transcript when I kind of ramble, and talk about reminders and tasks and all that, which is what I was doing earlier too,`
    4. `Okay, I'm mostly testing this thing again, because I want to see if it catches the whole transcript when I kind of ramble, and talk about reminders and tasks and all that, which is what I was doing earlier too, but anyway I do need to rewrite the agenda for tomorrow,`
    5. `Okay, I'm mostly testing this thing again, because I want to see if it catches the whole transcript when I kind of ramble, and talk about reminders and tasks and all that, which is what I was doing earlier too, but anyway I do need to rewrite the agenda for tomorrow, that's the one real thing I actually have to do.`
- `supplier-memo-recap`
  - final count: `2`
  - steps:
    1. `I need JC to call the supplier and make sure the catering is arranged, um,`
    2. `I need JC to call the supplier and make sure the catering is arranged, um, and I need to finish the memo by Friday,`
    3. `I need JC to call the supplier and make sure the catering is arranged, um, and I need to finish the memo by Friday, and I'm mostly just thinking out loud because there are too many moving pieces right now,`
    4. `I need JC to call the supplier and make sure the catering is arranged, um, and I need to finish the memo by Friday, and I'm mostly just thinking out loud because there are too many moving pieces right now, and people keep changing the plan,`
    5. `I need JC to call the supplier and make sure the catering is arranged, um, and I need to finish the memo by Friday, and I'm mostly just thinking out loud because there are too many moving pieces right now, and people keep changing the plan, but anyway, let me recap, I need JC`
    6. `I need JC to call the supplier and make sure the catering is arranged, um, and I need to finish the memo by Friday, and I'm mostly just thinking out loud because there are too many moving pieces right now, and people keep changing the plan, but anyway, let me recap, I need JC to call the supplier, and I need to finish the memo by Friday.`
- `cancel-one-keep-one`
  - final count: `1`
  - steps:
    1. `Call Anna tomorrow, and send the invoice to Lena, um,`
    2. `Call Anna tomorrow, and send the invoice to Lena, um, the invoice definitely has to go out tonight,`
    3. `Call Anna tomorrow, and send the invoice to Lena, um, the invoice definitely has to go out tonight, but on Anna I'm not totally sure yet,`
    4. `Call Anna tomorrow, and send the invoice to Lena, um, the invoice definitely has to go out tonight, but on Anna I'm not totally sure yet, actually never mind on Anna,`
    5. `Call Anna tomorrow, and send the invoice to Lena, um, the invoice definitely has to go out tonight, but on Anna I'm not totally sure yet, actually never mind on Anna, but do send the invoice to Lena tonight.`
- `call-marc-duplicate-ramble`
  - final count: `1`
  - steps:
    1. `I need to call Marc about the quote tomorrow, um,`
    2. `I need to call Marc about the quote tomorrow, um, and I was also going over the notes from that meeting in my head,`
    3. `I need to call Marc about the quote tomorrow, um, and I was also going over the notes from that meeting in my head, because honestly that whole meeting was confusing and people kept talking over each other,`
    4. `I need to call Marc about the quote tomorrow, um, and I was also going over the notes from that meeting in my head, because honestly that whole meeting was confusing and people kept talking over each other, so I keep feeling like I'm forgetting something, and yeah, don't let me forget to call Marc,`
    5. `I need to call Marc about the quote tomorrow, um, and I was also going over the notes from that meeting in my head, because honestly that whole meeting was confusing and people kept talking over each other, so I keep feeling like I'm forgetting something, and yeah, don't let me forget to call Marc, that's the main follow-up.`
- `god-milk-plus-second-task`
  - final count: `2`
  - steps:
    1. `I need to pick up god milk for Sarah tonight, um,`
    2. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick,`
    3. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick, and after that I need to text Marc about the quote,`
    4. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick, and after that I need to text Marc about the quote, and yeah, the oat one from the organic store,`
    5. `I need to pick up god milk for Sarah tonight, um, because regular milk makes her sick, and after that I need to text Marc about the quote, and yeah, the oat one from the organic store, that's what I meant.`

### Acceptance gates

1. The hosted replay dataset is updated to the approved curated replay case set
   with realistic multi-step snapshots and the core/stretch coverage defined in
   this spec.
2. The existing replay benchmark definition `todo_replay_bench_v1` is run
   against the updated hosted dataset, creating the local lock on first run or
   refreshing it on a rebase run.
3. The replay benchmark report reflects the updated replay dataset state.

### Supporting verification

- `backend/tests/test_item7_benchmark_cli.py`
- `backend/tests/test_item7_benchmark_smoke_integration.py`
- fixture-based replay parser tests if loader code changes
- replay runner tests using explicit dataset fixtures or lock-shaped fixtures if
  runner code changes

### Phase boundary rule

Do not start benchmark report case-enrichment changes, schema changes, or
focused field evaluators until this curated replay count benchmark has been
populated and rerun.

## Phase 4: Benchmark Report Case Enrichment

### Objective

Make the benchmark report surface case-level enrichment that already exists in
Logfire, instead of dropping back to empty case-level fields.

### Behavioral delta

Baseline:

- a live benchmark report can show the correct selected run and headline metric
- but case-level fields still come back empty even when Logfire has the case
  spans for that run

New behavior:

- the same live benchmark state keeps the same selected run and headline metric
- and the report now shows the case-level enrichment that was previously empty

### Non-goals

- changing benchmark selection logic
- changing headline metrics or report shape
- introducing `Retry-After` handling in this phase
- introducing `min_timestamp` / `max_timestamp` filtering in this phase
- switching the report path to MCP
- changing the extraction or replay datasets themselves

### Acceptance gates

1. On a live `todo_extraction_bench_v1` JSON report for the same benchmark
   state as the baseline, the selected run IDs and headline metric values stay
   the same, while case-level enrichment that was previously empty is now
   populated where Logfire already has that data.
2. Existing benchmark report tests are updated or extended to cover this
   output-level behavior.

For this phase, inability to prove the baseline-vs-after report comparison
counts as failure, not partial success.

### Supporting verification

- `backend/tests/test_item7_logfire_query.py`
- `backend/tests/test_item7_benchmark_report.py`
- `docs/references/2026-04-16-logfire-query-api-notes.md`

### Phase boundary rule

The next item must not begin until this report-enrichment phase passes.

## Phase 5: Persistent Benchmark Reports

### Objective

Make benchmark reports durable benchmark-owned artifacts instead of ad hoc
stdout captures or `.context` proof files.

### Behavioral delta

Baseline:

- `benchmark report <benchmark_id>` assembles the current report and prints it
- any saved report JSON is only whatever the operator manually redirected to a
  temporary path
- there is no stable benchmark-owned report artifact on disk

New behavior:

- each benchmark has a durable report file at
  `evals/reports/<benchmark_id>.json`
- invoking `benchmark report <benchmark_id>` ensures that file exists and
  returns the same report content
- if the benchmark state is unchanged, the existing stored report is reused
  rather than recomputed and rewritten
- if the benchmark state has changed, the report is recomputed and the stored
  file is overwritten with the new current benchmark state

For this phase, benchmark state means the benchmark-owned inputs and selection
result that determine the user-visible report, including:

- benchmark entry set
- active lock / hosted dataset state exposed in the report header
- selected run IDs per entry

### Non-goals

- changing the report schema
- changing the current benchmark-selection semantics
- introducing historical report versioning
- storing scratch proof artifacts in `.context` as benchmark outputs

### Acceptance gates

1. `benchmark report todo_extraction_bench_v1 --json` produces a durable report
   file at `evals/reports/todo_extraction_bench_v1.json`.
2. On a second invocation against the same unchanged benchmark state, that same
   report file is reused rather than rewritten.
3. If the benchmark state changes, the next `benchmark report` invocation
   refreshes `evals/reports/<benchmark_id>.json` so the stored file again
   matches the current benchmark state.
4. Existing tests are updated or extended to cover:
   - file creation when no stored report exists
   - reuse when benchmark state is unchanged
   - refresh when benchmark state has changed

For this phase, inability to prove file creation, reuse, or refresh counts as
failure.

### Supporting verification

- `backend/tests/test_item7_benchmark_report.py`
- `backend/tests/test_item7_logfire_report_integration.py`

### Phase boundary rule

The next item must not begin until durable benchmark-owned report persistence
passes these gates.
