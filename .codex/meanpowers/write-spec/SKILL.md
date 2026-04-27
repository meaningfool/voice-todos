---
name: write-spec
description: Use when triggered by the user. Helps writing a spec for a multi-step work item, before touching code
---

# Writing Specs

## Input
`write-spec` receives a scope as input. That scope may come from:
- A conversation or document
- A shaping session to which the user would point

If the user points to a shaping session, make sure to clarify which slices or sub-slices from that session should be considered as the input scope. 

## Output
`write-spec` writes comprehensive specs assuming that the engineering manager in charge of processing them does not know about the users, their needs, and does not have access to the Product Manager. They will likely mess up anything that is left to them to interprete.

`write-spec` does 2 things: 
1. Specify what the target system and its behaviour are and what changes need to be made to the current system. 
2. Slice the work into a sequence of `vertical slices`, unambiguously defined through `acceptance criteria`. 
3. Capture decisions made with regards to the system design

Note if the input is from a shaping session:
- The work has already be sliced. But the slices provided are non-binding. 
- Similarly the system design was decided on a much larger scope. The decisions made during the shaping session should be considered as a starting point, and should not be changed silently. But the `write-spec` process is the opportunity to identify gaps, or challenge assumptions that may have been missed during the shaping session.
- Shaping sessions have multi-level sub-slicing to enable for slicing large scopes. `specs` have a single level: slices cannot be sub-sliced for clarity. 

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


## Core Principles

- `slices`: unless the work is pure refactoring, slices are strictly vertical slices, meaning they encode an observable change in the system's behaviour, and are demoable in the UI.
- `acceptance criteria`: human-readable verifiable condition that the intended behavioral change is complete.

### Good Acceptance Criteria
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

### Bad Acceptance Criteria
- Says what the system `accepts`, `maps`, `preserves`, or `is`, instead of saying what happens
- Talks about hidden machinery instead of the thing the actor does or gets
- Describes a judgment in someone's head instead of a system output. Examples: `can understand`, `legible`, `readable`
- Uses vague scope words that are not defined in the sentence. Examples: `minimal`, `control plan`, `interface contract` 
- Uses passive phrasing that hides who is acting. Examples: `a benchmark can be declared`, `a recording can be added`
- States what is no longer true instead of stating the new behavior positively. Example: `no longer assumes`
- Concerns itself with implementation details the actor does not care about directly


## Process

If the spec follows a shaping session you can skip step 1, and proceed to step 2 directly.

### 1-Define the target

**Understanding the changes:**
- Baseline: read the docs, code, commit history to understand how the system works and behave in the vicinity of the required changes.
- Scope: reframe the required changes with regards to a baseline:
```
CHANGE {i}
Baseline: {1-2 short sentences}
Target: {1-2 short sentences}
Intent: {1 sentence}
-------
```
- Note: these are the starting point. The best break-down for the expected changes may change during the next phase. 

**Designing the target:**
- Interview the user relentlessly about every aspect of this scope until you reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.
- Ask the questions one at a time.
- Think of multiple approaches, repeatedly. What trade-offs do they reveal?
- Present options and the corresponding tradeoff conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why
- If a question can be answered by exploring the codebase, explore the codebase instead.

**Presenting the target:**
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

**Explore slicing options:**
- Slice vertically into slices way, way smaller than you otherwise would. Like, 10x smaller.
- When a small behavioural change still requires a significant amount of change in the system (e.g. adding a mobile native app), you may create intermediate slices that are mostly technical, as long as those slices produce a demoable output (e.g. a first slice with a mobile app that displays "Hello World", followed by slices integrating the UI and the data by chunks up to the point where it is actually usable)

**Define sequencing options:**
- Identify 2-3 ways to sequence the slices.
- Present to the user with the tradeoff for each option, and your recommandation.

**Define acceptance criteria:** 
- For each slice, define 1 or multiple acceptance criteria

**Present to the user:**
- Present each slice with its acceptance criteria

**Write the spec:**
- Use the template `references/spec-document-template.md`

### 3-Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved."**
**Next step: use write-plan to write the implementation plan. Say "ok" or "yes" to proceed.**

**If go ahead:**
- **REQUIRED SUB-SKILL:** Use meanpowers:write-plan