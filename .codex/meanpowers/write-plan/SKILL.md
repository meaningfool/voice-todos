---
name: write-plan
description: Use when triggered by the user. Helps writing a spec for a multi-step task, before touching code
---

# Writing Plans

## Input

- `write-plan` receives a `spec` as input
- That spec provides: `slices` and`acceptance-criteria`, and design decisions made during `write-spec` (and possibly the `shaping`) phases.

## Output
`write-plan` writes comprehensive implementation plans assuming the engineer that will do the implementation has zero context for our codebase and questionable taste.

`write-plan` does 2 things:
1. Translates acceptance criteria into acceptance tests that can be run automatically.
2. Maps out the work for each slice and divides it into tasks

Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the write-plan skill to create the implementation plan."

## File Management

```
docs/
└── meanpowers/
    ├── inbox/
    │   ├── INB-0002.md
    │   └── INB-0003.md
    └── 01_item-name/
        ├── INB-0001.md
        ├── 010_spike_spike-name.md
        ├── 010_shaping_item-name.md
        ├── 011_spec_title-of-the-spec.md
        ├── 011_plan_title-of-the-corresponding-spec.md
        ├── 012_spec_title-of-the-2nd-spec.md
        └── 012_plan_title-of-the-2nd-spec.md
```

A plan document:
- Lives in a `work-item` folder, which has an index and a name (example: `01_item-name` has index `01`)
- Always matches a `spec` document. 
- Has the same name as it's matching spec document, except for `plan` replacing `spec`: `[index]_spec_[title of the spec].md` translates into `[index]_plan_[title of the spec].md`

**If the plan follows a spec:** read and understand the spec and the shaping document if there is one. Gather context as you need.

**If you are not provided a spec to start from:** ask which spec you should start from. You ABSOLUTELY CANNOT start working on a plan without a matching spec.

## Plan creation principles

### General principles

- Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.
- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

### Tasks

- Each `task` should produce self-contained changes that make sense independently.
- Each `task` must be identified as either `refactoring` or `behavioral change`. A single task can't mix both.

### Acceptance tests

- `Acceptance test`: the concrete automated proof that an acceptance criterion is met.
- `Verification test`: Any unit, integration, replay, seam, helper, or regression test that improves implementation confidence.

Acceptance is orthogonal to the test pyramid.

An acceptance test may live at different sizes or layers depending on what is required to prove the behavior:

- a backend unit test
- a backend integration test
- a CLI-driven integration test
- a browser-driven end-to-end test
- a frontend test
- a non-pytest automated live validation named explicitly in the spec or plan

The test should live where it naturally belongs technically.Acceptance status does not determine placement. Technical ownership and the best execution harness determine placement.

### Good Acceptance Tests

Good acceptance tests are:

**Behavior-oriented:** They prove the intended behavior, not the implementation structure.

**Smallest realistic proof:** They are the smallest tests that still prove the behavior credibly.

**Durable:** They remain useful as part of the regression surface after the phase lands.

**Runnable:** They have concrete inputs, concrete execution steps, and concrete expected outcomes.

**Non-duplicative:** They should not create an "acceptance copy" of a test if an existing test already provides the smallest realistic proof of the behavior.

Acceptance tests are not:
- implementation task lists
- helper-level checks that do not prove user-visible or externally meaningful
  behavior
- purely structural assertions
- implementation-detail assertions
- broad regression sweeps unless the phase's behavioral delta is itself broad

### Preventing acceptance tests combinatorial explosion

Avoid combinatorial explosion by choosing the smallest durable proof surface that still captures the real contract:

- keep an existing broad acceptance test when it already proves the behavioral contract that matters
- prefer narrower acceptance or verification coverage for new seams, integrations, or adapters when the broad behavior is already covered
- split an acceptance test when one broad proof is no longer the clearest or most maintainable way to represent the behavior
- use one-off supporting verification when needed to validate a specific combination without permanently expanding the acceptance surface

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Slice header

```markdown
## [Slice Name]

**Goal:** [Description of the expected system behavioural change]

**Acceptance criteria:** [List of acceptance criteria inherited from the spec]

**Acceptance tests:**
- [Plain English description of what is being proven] — `pytest tests/path/test_file.py::test_name -v`
- [Plain English description of what is being proven] — `pytest tests/path/test_file.py::test_name -v`

**Verification tests:**
- [Plain English description of what is being verified] — `pytest tests/path/test_file.py::test_name -v`
- [Plain English description of what is being verified] — `pytest tests/path/test_file.py::test_name -v`

IMPORTANT: you cannot move on to the next slice unless you have first proven that all acceptance tests pass. A failure to prove MUST be considered as a proof of failure.

---
```


## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Adversarial Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. Run an adversarial self-review using the following checklist:

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search your plan for red flags — any of the patterns from the "No Placeholders" section above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved. Two execution options:"**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints for review
