---
name: write-spec
description: Use when triggered by the user. Helps writing a spec for a multi-step work item, before touching code
---

# Writing Specs

## Overview

Write comprehensive spec assuming that this is the only document the engineering manager will have access to to understand what they have to do. Assume the engineering manager does not know about the users and has questionable taste. They will likely mess up anything that is left to them to interprete.

The goal of the spec is to provide the engineering manager with a sequence of behavioural changes that are unambiguously defined through `acceptance criteria` that the engineer will be able to test autonomously to confirm that they have achieved what was expected and move on to the next change. Or course-correct if the criteria are not satisfied. 

A spec captures the work that needs to be done, as well as the decisions that have been made with regards to how things will be implemented.

**Announce at start:** "I'm using the write-spec skill to create the specification."

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

A spec document:
- Lives in a `work-item` folder, which has an index and a name (example: `01_item-name` has index `01`)
- Has its own index that concatenates the `work-item` index (example in `011_spec_title-of-the-spec.md`, `011` is made of `01`, the index of the `work-item` followed by `1`, the index of the spec)
- The index of the spec is incremented by 1 if specs already exist in the work-item folder. 1 otherwise.
- The name of the spec is `[index]_spec_[title of the spec].md`


**If the spec follows a shaping session:** (i.e. if a shaping document already exists in the work item folder)
- Create a new spec within the same work-item folder as the shaping session document.

**If the spec is an iteration on an existing work-item:**
- Create the new spec in the work-item folder

**If the spec is initiated by an `inbox`item:**
- Create a new `work-item` folder
- Move the inbox item in that folder
- Create a new spec in that folder

**If the spec is initiated directly from a conversation or document:**
- Create a new `work-item` folder
- Create a new spec in that folder

## Core Principle

- `slices`: unless the work is pure refactoring, slices are strictly vertical slices, meaning they encode an observable change in the system's behaviour, and are demoable in the UI.
- `sub-slices`: slices can be further divided into smaller slices as long as they are vertical slices as well.
- `acceptance criteria`: human-readable verifiable condition that the intended behavioral change is complete.
- `acceptance tests`: concrete tests that need to be run against the system to verify an acceptance criterion.

### Acceptance Criteria And Acceptance Tests

**Acceptance criteria and acceptance tests:** they serve different purposes and should be written differently: 
- Acceptance criteria define the human judgment of done.
- Acceptance tests provide the exact minimal scenarios that implement an acceptance criterion's intent.

**Slice->(Sub-Slice->)Acceptance Criteria->Acceptance Tests:**
- A slice may have multiple acceptance criteria. More than 3 acceptance criteria though is usually a signal that the slice is too large or mixes multiple behavioral changes.
- An acceptance criterion may be verified by a combination of multiple acceptantce tests. More than 3 may reveal an overly broad acceptance criterion to begin with.

### Good and Bad Acceptance Criteria

#### Gooad Acceptance Criteria
Good acceptance criteria are:

- `Slice-specific`: they specifically characterize the behavioral change of their slice. They do not describe unrelated system behaviours.
- `Human-readable`: they are easy for a reviewer to read and use as an alignment tool.
- `Externally meaningful`: they describe observable outputs, user-visible behavior, protocol behavior, or state transitions.
- `Minimal`: they are only numerous enough to define the slice's contract.

Good practices:
- Starts from a clear actor and a clear action
- Names the concrete thing that comes out of the system
  - examples: `get a report`, `writes audio.pcm`, `is visible from another worktree`
- Says what happens in plain words without requiring knowledge of the internals
- States the new behavior positively. Contrasts it with the current baseline if that provides additional clarity.
- Uses details only when they define the scope in a meaningful way

#### Bad Acceptance Criteria
- Says what the system `accepts`, `maps`, `preserves`, or `is`, instead of saying what happens
- Talks about hidden machinery instead of the thing the actor does or gets
- Describes a judgment in someone's head instead of a system output. Examples: `can understand`, `legible`, `readable`
- Uses vague scope words that are not defined in the sentence. Examples: `minimal`, `control plan`, `interface contract` 
- Uses made-up and undefined system elements. Example: `shared benchmark system` (what is that?)
- Uses passive phrasing that hides who is acting. Examples: `a benchmark can be declared`, `a recording can be added`
- States what is no longer true instead of stating the new behavior positively. Example: `no longer assumes`
- Concerns itself with implementation details the actor does not care about directly

Acceptance criteria and acceptance tests are not:
- implementation task lists
- helper-level checks that do not prove user-visible or externally meaningful
  behavior
- purely structural assertions
- implementation-detail assertions
- broad regression sweeps unless the phase's behavioral delta is itself broad

## Process

If the spec follows a shaping session you can skip step 1, and proceed to step 2 directly.

### 1-Define the target

**Understanding the baseline:**
- Reframe the user intention as a set of changes with regards to a baseline. 
- Read the docs, code, commit history, to establish what the baseline is from 3 angles: the internals of the system, how the system behave, and what the actors / journeys that rely on those behaviours are.

**Clarifying the expected change:**
- Ask questions to clarify the baseline or the intended change. Don't guess. Any gap, or any hint at the possibility of a gap in the articulations or progression should trigger a question and/or a reframe+validation
- Only one question per message - if a topic needs more exploration, break it into multiple questions

**Designing the target:**
- Think of multiple approaches, repeatedly. What trade-offs do they reveal?
- Present options and the corresponding tradeoff conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the change:**
- Once you believe most design decisions have been made, present the design
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

**Design for isolation and clarity:**
- Break the system into smaller units that each have one clear purpose, communicate through well-defined interfaces, and can be understood and tested independently
- For each unit, you should be able to answer: what does it do, how do you use it, and what does it depend on?
- Can someone understand what a unit does without reading its internals? Can you change the internals without breaking consumers? If not, the boundaries need work.
- Smaller, well-bounded units are also easier for you to work with - you reason better about code you can hold in context at once, and your edits are more reliable when files are focused. When a file grows large, that's often a signal that it's doing too much.

### 2-Define the slices

Repeatedly slice up the work for going from the baseline to the target: 
- **Vertical slices:** unless the whole spec is about a refactoring, all slices should result in an observable behavioural change. The change should be demo-able.
- **Acceptance criteria:** all slices should have acceptance criteria and acceptance tests.

