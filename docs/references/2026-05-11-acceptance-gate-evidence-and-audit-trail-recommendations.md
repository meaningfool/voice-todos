# Acceptance Gate Evidence And Audit Trail Recommendations

Date: 2026-05-11

## Purpose

This document proposes a tighter, lower-interpretation flow for acceptance
gates in this repo.

The focus is intentionally narrow:

- changes that can be made in repo-controlled instructions such as `AGENTS.md`
- changes that can be made in the Meanpowers `write-plan` skill

This document does not assume edit access to Superpowers execution skills such
as:

- `executing-plans`
- `verification-before-completion`
- `finishing-a-development-branch`

The goal is not to create a separate acceptance-test layer. The goal is to make
the existing acceptance-gate flow more explicit, more auditable, and less open
to interpretation.

## Why This Exists

The current repo guidance already says many correct things:

- browser-facing work requires live validation
- acceptance tests are the behavioral contract tests named by the spec or plan
- acceptance is a role, not a test layer
- plans should preserve acceptance gates from the spec

Those principles are sound.

The gap is more mechanical than conceptual.

Today, the flow does not reliably force the following:

- every acceptance criterion maps to one exact proving test or command
- the proving command leaves behind enough evidence to reconstruct what was
  actually observed
- the final handoff reports gate results criterion-by-criterion rather than as
  one interpreted overall judgment
- flaky or contradictory acceptance runs are treated as unresolved rather than
  informally rounded into success

That gap matters most for browser smoke flows, CLI smokes, and live validation
commands where:

- the exit code may be the only preserved output
- the command may print only a generic `ok`
- the underlying observed state may not be printed or saved
- a human may remember seeing something and later report that from memory

When that happens, the repo still has “a test,” but it does not have a strong
audit trail.

## Problem Statement

The repo currently has three related failure modes.

### 1. Acceptance Gates Can Be Operationalized Without A Criterion Map

A spec may define an acceptance gate with several criteria, for example:

- app loads from the intended origin
- websocket connects to same-origin `/ws`
- transcript activity appears during the run
- UI returns to idle after stop

A plan may then provide one smoke command for the gate, but without explicitly
mapping which part of the command proves which criterion.

That leaves room for silent drift:

- a criterion may not actually be checked
- a criterion may be checked only indirectly
- a criterion may be weakened while the gate name stays the same

### 2. Passing Commands May Not Preserve Enough Evidence

An acceptance command may exit `0` and print:

```text
browser-ui-smoke: ok
```

That proves the script itself returned success. It does not necessarily preserve
the actual observed state that caused the success decision.

If the script does not also emit or save:

- the actual transcript text
- the actual todo list
- the actual page snapshot
- the actual browser URL and websocket target

then later review becomes much weaker.

### 3. Final Handoffs Can Collapse A Multi-Criterion Gate Into A Narrative

Even when commands are run honestly, the final handoff can still be too
interpretive if it says:

- “the gate passed”
- “same-origin behavior works”
- “browser smoke passed”

without listing:

- the exact command
- the exact pass/fail result
- the exact evidence path
- the criterion-level conditions that were satisfied

That creates avoidable trust gaps.

## Constraints

Any recommendation here needs to respect the repo’s existing testing policy.

### Acceptance Is A Role, Not A Separate Test Layer

The repo should not create a second test taxonomy where “acceptance tests” live
in a new folder just because they are acceptance tests.

The maintained proving surface should remain in its natural technical home:

- `backend/tests/`
- frontend unit or integration tests
- `tests/live/`
- repo-owned smoke scripts
- browser automation scripts

This document does not recommend moving permanent tests into a new
acceptance-only directory.

### Run Artifacts And Permanent Tests Are Different Things

Permanent proving code belongs in the repo’s maintained test surfaces.

Run artifacts are different:

- stdout/stderr captures
- screenshots
- DOM snapshots
- JSON outputs from one local run
- browser traces

Those do not need to be committed as permanent tests. They only need to exist
long enough to support the acceptance claim for the current work.

If the repo wants a standard location for those artifacts, a gitignored
workspace-local path is appropriate.

Conductor already provides `.context/` for this kind of ephemeral collaboration
artifact. That makes it a reasonable default for acceptance run evidence, but
the principle matters more than the exact path. If the repo prefers another
gitignored location, the policy can say so.

## Current Broken Or Stale Guidance

At the time of writing, `AGENTS.md` contains stale references:

- the “Specs And Plans” section points to
  `docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md`
- the “Acceptance Tests” section references
  `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`

In this workspace:

- `docs/references/2026-04-13-phased-spec-plan-acceptance-gates.md` is empty
- `docs/references/2026-04-13-acceptance-tests-and-verification-policy.md`
  does not exist

That creates two problems:

- it implies the repo has a definitive reference when it currently does not
- it encourages agents to assume the details exist elsewhere

This should be fixed directly in repo-controlled guidance rather than worked
around informally.

## Design Goal

The repo should define a flow where an agent may report an acceptance gate as
passed only when all of the following are true:

1. the gate’s criteria are mapped to exact proving tests or commands
2. those tests or commands were run fresh
3. every proving test or command exited successfully
4. every required evidence artifact exists
5. the final handoff cites the command outputs and evidence paths directly
6. no contradictory rerun has occurred without being surfaced

This is a mechanistic standard. It is intentionally harder to “round up” into a
success narrative.

## Recommended Repo-Level Changes

The strongest changes available without Superpowers edits are:

- strengthen `AGENTS.md`
- strengthen Meanpowers `write-plan`

Those two surfaces can carry much more of the execution discipline than they do
today because:

- `AGENTS.md` sets repo-wide execution expectations
- `write-plan` controls what a plan must contain
- `executing-plans` already tells agents to follow the plan exactly

If the plan itself requires exact proof mapping and evidence capture, the room
for interpretation becomes smaller even without editing execution skills.

## Recommendation 1: Add An Explicit Acceptance Evidence Policy To AGENTS.md

The repo should add a new section to `AGENTS.md` that defines the acceptance
evidence contract.

The missing policy today is not “run tests.” The missing policy is:

- how acceptance criteria must map to proof surfaces
- what counts as sufficient evidence
- what must be preserved from a run
- how final handoff must report it

### Suggested AGENTS.md Section

The following text is suitable as a starting point.

```md
## Acceptance Evidence

- Every acceptance gate named by the current spec or plan must map to exact
  proving tests or commands. Do not infer gate success from adjacent evidence.
- Every criterion inside an acceptance gate must be covered by at least one
  named proving surface. If a criterion is not explicitly covered, the gate is
  unresolved.
- Acceptance proving commands must leave a durable local audit trail. Preserve
  raw stdout/stderr with `tee` into a gitignored workspace-local path such as
  `.context/acceptance/<item>/...` unless the command already writes an
  equivalent artifact.
- If an acceptance command proves browser-visible or CLI-visible state, it must
  also preserve the observed state in an inspectable form when feasible, such
  as JSON output, screenshots, DOM snapshots, or text captures.
- A smoke script that only prints `ok` is not sufficient acceptance evidence
  when the observed state matters. Update the script first or treat the gate as
  unproven.
- Do not report an acceptance gate as passed unless every mapped proof command
  exits `0` and every required evidence artifact exists.
- If repeated runs disagree, the gate is unresolved, not passed.
- `.context` or another gitignored workspace-local path is for run artifacts
  only. Permanent tests remain in their natural technical harnesses.

## Final Handoff

- For each acceptance gate, report:
  - gate name
  - exact proving command or test
  - pass/fail result
  - evidence artifact path or key output lines
- Do not summarize a gate as passed without those items.
```

### Why This Belongs In AGENTS.md

This guidance belongs in `AGENTS.md` because it is repo policy, not just plan
authoring style.

It answers repo-wide questions such as:

- when is a generic smoke script insufficient
- when does a run need artifact capture
- how should acceptance be reported at handoff
- what happens if reruns disagree

Those questions arise during execution, not just plan writing.

## Recommendation 2: Make Acceptance Coverage Decisions Mandatory In write-plan

Some stronger plans in the repo already use a section called:

- `Acceptance Coverage Decisions`

That pattern should be standardized in the Meanpowers `write-plan` skill.

The key idea is simple:

- acceptance gates define the contract
- acceptance coverage decisions define the proving surface for that contract

Without that section, a plan can still be “good,” but the criterion-to-proof
mapping is easier to lose.

### What The Section Should Require

For each acceptance gate criterion, the plan should state:

- whether the proving surface is `add`, `update`, `replace`, or `reuse`
- the exact test, smoke script, or command that proves it
- the exact pass condition
- the exact evidence artifact path if the result is not already self-evident
  from standard test output

This must be criterion-level, not just gate-level, when the gate contains
multiple materially different claims.

### Suggested write-plan Additions

The following text can be added to the `write-plan` skill.

```md
## Acceptance Coverage Decisions

For each acceptance gate and for each criterion inside that gate when needed,
the plan must name:

- whether the proving surface is `add`, `update`, `replace`, or `reuse`
- the exact proving test or command
- the exact pass condition
- the exact evidence artifact path if the proof is not self-evident from normal
  test output

If a criterion does not have a concrete proving surface, stop and notify the
user.
```

### Why This Matters

This requirement prevents several common plan failures:

- a gate with one smoke command that only partially proves the gate
- a browser gate that depends on a script which prints only `ok`
- a live-validation gate with no preserved output
- a criterion that exists in prose but nowhere in test execution

## Recommendation 3: Make Evidence Capture Part Of Gate Execution In write-plan

It is not enough for `Gate Execution` to list commands.

`Gate Execution` should also specify how evidence is preserved.

### Current Weak Pattern

Weak:

```bash
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos
```

This proves only that the script returned some result and printed whatever it
prints by default.

### Stronger Pattern

Stronger:

```bash
mkdir -p .context/acceptance/031
./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos \
  2>&1 | tee .context/acceptance/031/browser_ui_smoke.log
```

If the script also writes screenshots or JSON, those paths should be named in
the plan too.

### Suggested write-plan Addition

```md
## Evidence Capture

`Gate Execution` commands must preserve durable local evidence. Use exact
commands that capture raw stdout/stderr, such as `tee`, unless the proving
command already writes an equivalent artifact.

If the proving command only prints a generic success marker, the plan must
first include work to upgrade that command so it emits or saves the observed
state needed by the gate.
```

### Why Evidence Capture Belongs In The Plan

The plan is where the repo decides:

- what commands prove the gate
- what makes those commands trustworthy enough

If the artifact requirement is absent from the plan, execution can remain too
casual even when the tests are being run.

## Recommendation 4: Add A Required Acceptance Checkpoint To write-plan

The current `write-plan` skill already says:

- acceptance gates from the spec are the completion contract
- each slice should have a checkpoint before the next slice begins

That should be made more explicit and more mechanical.

### Suggested Checkpoint Language

```md
## Acceptance Checkpoint

A slice is not complete until:

- every acceptance proof command has been re-run fresh
- every proof command exits `0`
- every required evidence artifact exists
- no contradictory rerun has occurred without being reported
- the final handoff can cite the exact command and artifact path for each gate
```

### Why This Helps Even Without Editing Execution Skills

This matters because `executing-plans` already instructs agents to:

- follow plan steps exactly
- stop when verification fails repeatedly

If the plan itself contains the stronger checkpoint, the executing agent has
less room to improvise.

## Recommendation 5: Standardize The Final Acceptance Report Shape In AGENTS.md

Repo-level handoff guidance should not stop at:

- “report the exact browser validation command”
- “say whether it passed”

That is too weak for multi-criterion gates.

The final handoff should use a gate matrix shape.

### Suggested Handoff Format

For each acceptance gate:

- gate name
- criterion or covered criteria
- exact proving command or test
- pass/fail
- evidence path or key output lines

If there are multiple commands for one gate, list each one separately.

### Example

```text
Acceptance Gate: Local Cloudflare Same-Origin App Works Through The Real UI

- Criterion: app loads from Cloudflare-served origin
  Command: curl -I http://127.0.0.1:8788/ | tee .context/acceptance/031/root_headers.txt
  Result: PASS
  Evidence: .context/acceptance/031/root_headers.txt

- Criterion: websocket boundary is same-origin /ws
  Command: curl -i http://127.0.0.1:8788/ws | tee .context/acceptance/031/ws_headers.txt
  Result: PASS
  Evidence: .context/acceptance/031/ws_headers.txt

- Criterion: browser smoke completes against fixture path
  Command: ./scripts/browser_ui_smoke.sh http://127.0.0.1:8788 while-speaking-two-todos 2>&1 | tee .context/acceptance/031/browser_ui_smoke.log
  Result: PASS
  Evidence: .context/acceptance/031/browser_ui_smoke.log
```

This is much harder to over-interpret.

## Recommendation 6: Treat “Only Prints ok” As A First-Class Smell

This repo should explicitly recognize the following smell:

- a smoke script is used as acceptance proof
- the smoke script prints only a generic success line
- the observed state matters to the gate

That script should be treated as incomplete acceptance tooling.

There are two acceptable responses:

### Option A: Upgrade The Script

Teach the script to preserve the observed state:

- write transcript text to a JSON file
- write todos to a JSON file
- save one or more screenshots
- print those paths

### Option B: Wrap The Script With Additional Evidence Commands

If the script itself is intentionally minimal, the plan can require follow-up
inspection commands that preserve the state separately.

For example:

- run the smoke
- run `agent-browser eval` to capture the final DOM state
- write that DOM-derived JSON to a local evidence file

### What Should Not Happen

What should not happen is:

- run a script that prints `ok`
- remember seeing the UI in passing
- report the gate as passed later without preserved evidence

## Recommendation 7: Use `.context` Only For Run Evidence, Not For Permanent Tests

The repo should clarify the distinction to avoid policy confusion.

### Correct Use Of `.context`

Appropriate examples:

- `.context/acceptance/031/browser_ui_smoke.log`
- `.context/acceptance/031/during_run.png`
- `.context/acceptance/031/final_state.json`

These are:

- ephemeral
- gitignored
- tied to one execution
- useful for audit and review

### Incorrect Use Of `.context`

Inappropriate examples:

- moving a permanent backend test into `.context`
- creating a second parallel acceptance-test framework there
- storing the only copy of durable test logic there

Permanent tests still belong in the repo’s maintained test surfaces.

### If The Repo Does Not Want `.context`

That is fine. The policy goal is not the exact directory name.

The real requirement is:

- use a workspace-local gitignored artifact path
- standardize it
- require plans and handoffs to reference it

If the repo prefers `tmp/acceptance/` or another ignored path, the principle is
the same.

## Recommendation 8: Distinguish Reliability Assertions From Boundary Assertions In Plans

This is important for acceptance design quality.

Sometimes a gate is trying to prove:

- app boundary shape
- same-origin behavior
- start/stop lifecycle
- live validation transport

Sometimes the underlying runtime also produces outputs whose exact text may be
nondeterministic or model-quality-sensitive.

The plan should make that distinction explicit.

### Good Pattern

The plan says:

- this gate proves app-boundary reliability
- therefore its acceptance assertions are:
  - origin
  - websocket path
  - visible transcript activity
  - at least one todo observed
  - clean return to idle
- exact semantic todo content is supporting verification or belongs to another
  behavioral contract

### Bad Pattern

The plan mixes:

- same-origin boundary proof
- exact model output contract
- general product quality expectations

into one smoke command without naming which part is actually completion
critical.

This matters because otherwise an executor may loosen assertions “to make the
real intent fit,” which is exactly the kind of drift this document tries to
prevent.

## Recommendation 9: Replace Broken Reference Links With Inline Repo Rules Or A Real Reference

Right now, the repo has stale references but no durable local policy document
for acceptance evidence.

The repo should choose one of two approaches:

### Option A: Keep The Rules In AGENTS.md

Pros:

- impossible to miss
- repo-local
- directly enforced in every task

Cons:

- `AGENTS.md` gets longer

### Option B: Create A Real Reference Doc And Link To It

Pros:

- easier to expand over time
- can include examples and rationale

Cons:

- only works if the linked file actually exists and stays maintained

If Option B is chosen, the link target must be real, non-empty, and local to
this workspace.

## Recommendation 10: Prefer Gate Matrices Over Narrative Acceptance Claims

A narrative acceptance claim sounds like:

- “same-origin behavior works”
- “browser smoke passed”
- “the acceptance gate is green”

A gate matrix sounds like:

- Gate 1, Criterion A, Command X, PASS, Evidence Y
- Gate 1, Criterion B, Command Z, PASS, Evidence W

The second form is more mechanical and better aligned with the repo’s goal of
low-interpretation completion.

This should be encouraged in both:

- plan structure
- final task handoff

## Recommendation 11: Allow Probabilistic End-To-End Acceptance When The Real Delegated Behavior Is Inherently Noisy

Not every acceptance gate should be forced into a deterministic lower-level
simulation.

For some work items, the right delegated behavior is genuinely end-to-end:

- real browser
- real app boundary
- real websocket transport
- real fixture audio
- real STT path
- real extraction path
- real UI rendering and stop behavior

When that is the behavior the human partner actually cares about, replacing it
with a fake replay may improve determinism while weakening the claim.

That is not always the right trade.

### When Probabilistic End-To-End Acceptance Is Appropriate

Probabilistic end-to-end acceptance is appropriate when all of the following are
true:

- the goal of the item is primarily end-user-visible reliability rather than
  lower-level algorithmic correctness
- the delegated behavior crosses a boundary that humans would naturally test
  end-to-end
- the underlying runtime includes components that are noisy, heuristic, or
  model-dependent
- a deterministic simulation would materially reduce confidence in the actual
  delegated path

Examples:

- realtime STT plus extraction plus browser UI
- live benchmark smoke against an external provider
- workflow automation across a browser plus a remote service

### What Probabilistic End-To-End Acceptance Does Not Mean

It does not mean:

- “one green run is good enough”
- “if it passed once, report it as working”
- “if the output looked plausible, count that as success”
- “skip preserved evidence because the test is noisy anyway”

Probabilistic acceptance still needs an explicit contract.

### Recommended Shape

For noisy but important end-to-end paths, the acceptance contract should define:

- the exact real path that must be exercised
- the exact stable assertions that the app, boundary, or workflow owns
- the number of runs required
- the threshold for success
- the evidence that must be preserved for every run

### Recommended Pass Rule

Instead of:

- one run must pass

use a pass rule such as:

- run `N` times
- acceptance passes if at least `M` runs pass
- preserve evidence for all `N` runs
- report both the success count and the failure modes

Typical examples:

- `3 of 3` for a path expected to be very stable
- `4 of 5` for a noisy end-to-end smoke with some model variance
- `8 of 10` for a more exploratory confidence gate

The important part is that the threshold is stated in advance by the plan, not
improvised after the run.

### How To Report Probabilistic Acceptance

A proper handoff for probabilistic acceptance should say:

- exact command used for each run
- total runs attempted
- total passes
- total failures
- summary of failure types
- evidence path for each run

Example:

```text
Acceptance Gate: Real E2E Cloudflare Voice Session Smoke

- Pass Rule: 4 of 5 runs must pass
- Result: 4 of 5 passed

Run 1: PASS
  Evidence: .context/acceptance/031/run-1/

Run 2: PASS
  Evidence: .context/acceptance/031/run-2/

Run 3: FAIL
  Failure mode: no todo observed before stop
  Evidence: .context/acceptance/031/run-3/

Run 4: PASS
  Evidence: .context/acceptance/031/run-4/

Run 5: PASS
  Evidence: .context/acceptance/031/run-5/
```

That is still an acceptance gate. It is just honest about the nature of the
signal.

## Recommendation 12: Separate App-Owned Assertions From Model-Owned Assertions Inside A Real End-To-End Test

The main way to reduce flakiness without abandoning end-to-end testing is not
to fake more of the stack. It is to narrow the assertions to the parts of the
behavior the current item actually owns.

### App-Owned Assertions

These are good acceptance assertions for a browser-facing realtime app:

- the page loads from the intended origin
- the websocket path is the intended same-origin path
- the session starts
- transcript activity becomes visible
- at least one todo-like result becomes visible, if that is part of the user
  flow contract
- stop completes
- the UI returns to the intended idle or post-session state
- no fatal warning or setup error is shown

These are generally app or integration owned.

### Model-Owned Assertions

These are often poor acceptance assertions for an app-boundary item:

- exact transcript wording
- exact todo wording
- exact extraction schema payload
- exact semantic interpretation of a spoken sentence

These are usually affected by:

- model variance
- provider changes
- prompt changes
- threshold tuning
- pacing differences

They may still matter, but they should usually be proved in one of these ways:

- model evals
- extraction contract tests
- supporting verification
- separate quality gates

### Why This Distinction Matters

A real end-to-end test can stay real end-to-end while still focusing on
app-owned invariants.

That means the repo does not have to choose between:

- fake deterministic tests
- flaky model-sensitive acceptance

There is a third option:

- real end-to-end path
- stable app-owned assertions
- noisy model-quality checks moved elsewhere or treated separately

## Recommendation 13: Distinguish Hard Failures From Soft Quality Failures

For noisy end-to-end acceptance, the proving script or test should classify
failure types rather than returning one undifferentiated red state.

### Hard Failures

Hard failures should almost always fail the acceptance run immediately:

- page fails to load
- websocket fails to connect
- browser shows microphone or setup failure when the flow should avoid it
- transcript never appears
- UI never reaches the active recording state
- stop never completes
- UI does not return to the expected idle or post-session state

These are app or transport failures.

### Soft Quality Failures

Soft quality failures are different:

- todo wording differs
- transcript wording differs
- second todo is missing even though transcript and lifecycle are otherwise
  healthy
- category or due-date extraction is missing

These can still matter, but for many app-boundary items they should not be
treated as proof that the app boundary itself is broken.

### Recommended Treatment

The acceptance script should report both:

- `hard_failure`
- `quality_warning`

That lets one command support two distinct purposes:

- acceptance of the app path
- diagnosis of model/output quality drift

The plan can then decide which one is completion-blocking for the current item.

## Recommendation 14: Repair Existing Flaky Tests By Narrowing Their Contract, Not By Carrying Them Forever As Ambiguous Smokes

The repo should not drag flaky tests around indefinitely.

But “fixing” them does not always mean deleting them or making them fake.

It often means rewriting the test contract so the test proves one coherent
thing.

### Repair Pattern A: Keep The Real Path, Reduce The Assertion Surface

Current weak pattern:

- one end-to-end browser smoke
- audio fixture streamed through the real runtime
- exact or semi-exact todo text asserted
- exact or semi-exact transcript text asserted
- script prints only `ok`

Recommended repair:

- keep the same real browser and real audio path
- assert only app-owned invariants
- preserve the observed transcript and todos as run evidence
- treat semantic correctness as a secondary output, not a completion condition

### Repair Pattern B: Add Run Multiplicity To Noisy Acceptance

Current weak pattern:

- one run
- one pass implies success

Recommended repair:

- run `N` times
- preserve evidence for all runs
- define `M of N` threshold in advance
- report failure modes explicitly

### Repair Pattern C: Split One Ambiguous Smoke Into One Acceptance Surface And One Quality Surface

This does not mean splitting the underlying implementation into fake unit
fragments.

It means one real script may expose two profiles:

- `acceptance`
  - uses the real end-to-end path
  - asserts only stable app-owned outcomes
- `quality`
  - uses the same real path
  - records transcript and todo quality drift
  - may be advisory or belong to a different work item

That can be one script with two modes, not necessarily two different tools.

## Existing Test Surface: Recommended Repair For The Current Browser Smoke

The current `scripts/browser_ui_smoke.sh` shape is a good example of a script
that should be repaired rather than trusted as-is.

At the time of writing, the script:

- opens the real browser path
- uses the fixture audio URL path
- waits for specific user-visible text such as `Buy oat milk`
- extracts final todo and transcript text
- asserts semantic content in the output
- prints only a generic success marker at the end

That creates two different kinds of flakiness:

- model/output flakiness
- audit/evidence weakness

### Recommended Changes To The Current Browser Smoke

#### 1. Keep It Real End-To-End

Do not replace the browser smoke with a fake websocket replay if the purpose of
the item is to validate the real delegated browser-to-runtime path.

Keep:

- real browser
- real fixture audio
- real `/ws`
- real STT path
- real extraction path
- real UI stop flow

#### 2. Change The Acceptance Assertions

The acceptance profile should assert:

- the page loaded from the intended host
- the start button is present before the run
- the session enters the active state after `Start Session`
- transcript text becomes non-empty during the run or by stop
- at least one todo card appears during the run or by stop
- `Finish Session` completes
- the UI returns to the start or idle state
- no `Microphone setup failed.` or equivalent fatal warning appears

The acceptance profile should not require:

- exact transcript wording
- exact todo wording
- exact presence of a specific second todo such as a budget item

Those belong to a quality-oriented proof surface, not to the app-boundary gate.

#### 3. Preserve Structured Output For Every Run

The smoke should write a result bundle per run, for example:

- command log
- initial snapshot
- during-run snapshot
- final snapshot
- extracted transcript text
- extracted todo list
- final pass/fail classification
- failure type if any

Whether this is emitted as JSON, text, screenshots, or a mix depends on the
tooling, but it should exist.

#### 4. Add Explicit Failure Classification

For example:

- `load_failure`
- `ws_failure`
- `no_transcript`
- `no_todo`
- `stop_failure`
- `fatal_warning`
- `quality_warning`

That makes reruns useful instead of noisy and opaque.

#### 5. Add Repeated-Run Mode

The script should support:

- one run for debugging
- `N` runs for acceptance confidence

The repeated-run mode should:

- create one evidence directory per run
- produce an aggregate summary
- exit non-zero only when the declared pass threshold is missed

### Suggested Future Shape For The Browser Smoke

One practical direction is:

- `scripts/browser_ui_smoke.sh --profile acceptance --runs 5 --min-pass 4`
- `scripts/browser_ui_smoke.sh --profile quality --runs 1`

Where:

- `acceptance` focuses on app-owned invariants
- `quality` records exact transcript and todo outputs for diagnosis

This preserves a real end-to-end path while preventing one script from carrying
two incompatible jobs.

## Existing Test Surface: Recommended Repair For Audio-Fixture Runtime Smokes

Direct websocket or runtime smokes that send real fixture audio should also be
reviewed under the same lens.

If their current purpose is:

- transport and lifecycle proof

then their assertions should focus on:

- session start
- transcript activity
- stop completion
- terminal message shape

If their current purpose is:

- model or extraction correctness

then they should be named and reported as quality or eval surfaces rather than
app acceptance.

The important part is that one test should not silently prove both at once
unless the plan explicitly says so and the noise level is acceptable.

## Existing Test Surface: Stable Selectors And UI-Owned Signals

One practical way to reduce browser-smoke flakiness without weakening the
end-to-end path is to improve what the UI exposes for testing.

The UI can provide stable app-owned signals such as:

- explicit `data-testid` markers for key controls and states
- explicit state text for idle, connecting, recording, and extracting
- a dedicated warning banner region
- a dedicated transcript region
- a dedicated todo-list region

This is often better than scraping generic text from broad selectors such as:

- all `article p`
- full `document.body.innerText`

Those broader selectors make the smoke more fragile and less precise than it
needs to be.

Stable selectors do not make the test less end-to-end. They make the signal
clearer.

For the current voice-session UI, concrete examples of good stable selectors
include:

- `data-testid="voice-app-shell"`
- `data-testid="session-dock"` with `data-status`
- `data-testid="session-toggle"`
- `data-testid="listening-indicator"`
- `data-testid="todo-feed"`
- `data-testid="todo-card-title"`
- `data-testid="warning-card"`
- `data-testid="session-details"`
- `data-testid="session-transcript"`

Those selectors are owned by the UI structure and state model. They are more
stable than scraping generic text from broad page regions.

## Existing Test Surface: When To Delete Instead Of Repair

A flaky test should be deleted or replaced if:

- it no longer proves a current behavioral contract
- it duplicates a better proving surface
- its result cannot be made interpretable even with narrowed assertions and
  evidence capture
- its failure modes are so broad that the test does not guide action

A flaky test should be repaired and kept if:

- it exercises a real delegated path that humans care about
- it proves something not otherwise covered
- its contract can be narrowed to stable app-owned or workflow-owned outcomes
- its evidence can be made auditable

## Decision Rule For Future Plans

When a new browser or live acceptance surface is proposed, the plan should
explicitly decide which of these it is:

### Type A: Deterministic Contract Test

- expected to be stable run-to-run
- exact output is part of the contract

### Type B: Probabilistic End-To-End Acceptance Test

- exercises the real delegated path
- uses repeated runs and thresholding
- asserts stable end-user-visible outcomes

### Type C: Quality Or Eval Surface

- captures model or heuristic quality
- may use exact expected outputs
- should not be confused with app-boundary acceptance unless the spec says so

Many current ambiguities come from one test informally trying to be all three
at once.

## Concrete write-plan Revision Outline

If the repo wants to edit the Meanpowers `write-plan` skill, the minimum useful
changes are:

### Add A New Section

Add after `Acceptance Gates And Supporting Verification`:

```md
## Acceptance Coverage Decisions

For each acceptance gate, and for each individual criterion when needed, name:
- whether the proving surface is `add`, `update`, `replace`, or `reuse`
- the exact proving test or command
- the exact pass condition
- the exact evidence artifact path when standard test output is not sufficient

If a criterion does not map to a concrete proving surface, stop and notify the
user.
```

### Strengthen Gate Execution

Add:

```md
## Evidence Capture

`Gate Execution` commands must preserve durable local evidence. Use exact
commands that capture stdout/stderr and any required browser or CLI state. If a
command only prints a generic success marker, the plan must include work to
upgrade it or add companion evidence-capture commands before the gate can be
considered operationalized.
```

### Strengthen The Self-Review Checklist

Add checklist items:

- every gate criterion maps to one or more exact proving surfaces
- every proving surface has a concrete pass condition
- every proving surface has a named evidence output when normal test output is
  not enough
- no gate depends on an `ok`-only smoke script when observed state matters

## Concrete AGENTS.md Revision Outline

If the repo wants to edit `AGENTS.md`, the minimum useful changes are:

### Replace The Broken References

Remove or replace the stale links under:

- `## Specs And Plans`
- `## Acceptance Tests`

If those concepts still matter, either inline the rules or point to a live
reference doc in this workspace.

### Add Acceptance Evidence Rules

Add a new section with:

- criterion-to-proof mapping
- evidence capture requirement
- rerun disagreement rule
- final handoff matrix requirement

### Strengthen Live Validation Reporting

The current wording says:

- report the exact browser validation command or script you ran and whether it
  passed

That should be strengthened to:

- report the exact browser validation command
- report the pass/fail result
- report where the captured output and observed-state artifacts were written

## Migration Approach

The repo does not need to solve this everywhere at once.

A practical rollout could be:

### Step 1

Fix `AGENTS.md`:

- remove broken links
- add acceptance evidence rules

### Step 2

Update `write-plan`:

- require `Acceptance Coverage Decisions`
- require evidence capture in `Gate Execution`

### Step 3

Apply the stronger plan shape to new or edited plans only.

This keeps the migration small while still improving future work.

### Step 4

As smoke scripts are touched for real work items, upgrade them to preserve:

- stdout/stderr logs
- browser state snapshots
- structured result data where useful

The repo does not need to rewrite every historical smoke script immediately.

## Anti-Patterns To Explicitly Ban

If the repo wants the flow to become more mechanistic, the following should be
called out directly as forbidden or unacceptable.

### Anti-Pattern 1: Gate Pass By Adjacent Inference

Example:

- the websocket smoke passed
- therefore the browser gate probably passed too

This is invalid unless the browser gate explicitly maps to that proving
surface.

### Anti-Pattern 2: Gate Pass By Memory

Example:

- the smoke script only printed `ok`
- the agent remembers seeing the correct UI state
- the final handoff reports that remembered state as if it were preserved

This is invalid.

### Anti-Pattern 3: Gate Pass With Missing Criterion Coverage

Example:

- the gate requires origin, websocket path, visible activity, and idle reset
- the proving command only checks visible activity

This is invalid even if the command exits `0`.

### Anti-Pattern 4: Gate Pass Despite Contradictory Reruns

Example:

- first run passed
- second run failed
- final report treats the gate as passed because success happened once

This is invalid. The gate is unresolved.

## Final Recommendation

The repo does not need a new testing philosophy. It already has the right
philosophy:

- acceptance is a behavioral contract
- keep tests in their natural harness
- distinguish acceptance from supporting verification

What it needs is a tighter mechanical flow around those ideas.

The most leverage available without Superpowers edits is:

- strengthen `AGENTS.md`
- strengthen `write-plan`

Those two changes can make future acceptance work much less interpretive by
requiring:

- exact criterion-to-proof mapping
- exact pass conditions
- preserved run evidence
- explicit handoff reporting

That is the recommended direction.
