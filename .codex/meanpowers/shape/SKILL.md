---
name: shape
description: Use when the user invokes it 
---

# Shaping

## Overview

The `shape` skill is inspired by Ryan Singer's methodology with my own tweaks. It posits that the understanding of a problem co-evolves with the exploration of solutions. 

In the context of Meanpowers, the `shape` skill provides a process to better define large and/or loosely scoped changes.

## Core concepts

**Shape:** 
- A software product is a `system` that interacts / is interacted with by `actors`. 
- It is constituted of `components`: components that communicate only with other components are part of the system "internals". Components that are exposed to the outside world are part of the system "interface". 
- A `shape` is a specific version of the system.

**System behaviour:**
- A system receives input through its `inbound ports` and reacts through its `outbound ports`.
- The system `behaviour` is the set of its observable reactions given a specific input and internal state.
- A change to the system may result in a change in its behaviour.
- A change in the system's behaviour requires a change to the system.

**Actors' journeys:**
-  A `journey` is a sequence of interactions an actor has with the system in order to achieve a specific outcome.
- A change to the system behaviour may result in a change to one or multiple journeys.
- A change in a journey requires a change to the system. 

**Requirements:**
- The `system designer` knows the actors and its own constraints and objectives. 
- Based on that knowledge, the system designer identifies `requirements` that, if met by the system, are expected to better serve the actors and/or the system designer's objectives. 
- The `requirements` are expectations that can be expressed with regards to the system itself and its components, as well as what the actors' journeys should be.

**Shaping:**
- `shaping` is the process of converging towards the set of requirements and a matching shape. It happens through the co-evolution of requirements and shapes.
- Shaping is the result of a discovery and negociation process flowing from requirements to shapes and from shapes to requirements. 
- Requirements get refined, dropped or added, calling for new shapes to be explored. 
- Contrasting potential shapes surfaces new constraints, expectations and tradeoffs calling for requirements refinements.

**Slicing:**
- Given a target `shape`, that is a set of changes to the current system, `slicing` is the process of identifying `vertical slices`
- A vertical slice is a subset of system changes that produce an observable change of the system behaviour. A vertical slice can be demoed.
- A horizontal slice is a slice that contains only changes to system internals producing no system behaviour change.
- Horizontal slices are ok in a single case: when breaking down a system refactoring.

## File management

```
docs/
└── meanpowers/
    ├── inbox/
    │   ├── item-1.md
    │   ├── item-2.md
    │   └── item-3.md
    └── 01_item-name/
        ├── spec_01-01.md
        ├── plan_01.md
        ├── spike_spike-name.md
        └── shaping_item-name.md
```


## Running of a shaping session

### 1-Start a session

- The `shape` skill expects an item from the `inbox`as a starting point. 
- If the user invokes the `shape` in the middle of a conversation suggest they use the `capture` skill first. If they decline, use the conversation as the starting point.

### 2-Create a shaping document

- Create a name for the new item folder to be created in the `docs/meanpowers` folder. Use the next available increment, and propose a name based on the input.
- Validate the name with the user
- Create the folder
- Create a `shaping_{name of the item folder}.md` within the item folder.

### 3-Establish the baseline

- Read files and code to establish what the baseline in the vicinity of the changes expected. Answer the following questions:
- What specific actors' journeys will be impacted? What are those journeys right now?
- What specific system behaviours will be impacted? What system behaviours do we observe right now?
- What parts of the system will be impacted? How do they work right now?

### 4-Generate a first version

- Based on the input and the baseline propose a first version of the requirements list.
- Generate a first list of shapes
- Suggest what you see as the best next action
- Submit to the user

### 5-Iterate

**Principles**

We have 3 facets to look from: journeys, shapes, requirements. Refining, adding, refactoring any of those lists impact the other 2. 

Iterating is about: 
- Generating alternative versions on one facet
- Identify what they look like on the other facets
- Contrast between versions (including the current one) to surface ne tradeoffs.

**Steps**

- Process the user feedback and/or take a next action.
- Present the result to the user, and suggest 2 next action options (see section about possible actions).
- Iterate.

### 6-Confirm the final shape

- Once the process has converged, present once again the requirements, the shape and the journeys
- Demand confirmation to move to the next step

### 7-Slice the shape

- Create vertical slices from the final shape
- Present the journeys first in terms of system behaviour change implemented in each slice. Second in terms of what changes to the system/components would happen.
- Iterate with the user 

Considerations:
- As a general rule, try to generate the smallest vertical slices. 
- When a small behavioural change still requires a significant amount of change in the shape (e.g. adding a mobile native app), you may create intermediate slices that are mostly technical, as long as those slices produce a demoable output (e.g. a first slice with a mobile app that displays "Hello World", followed by slices integrating the UI and the data by chunks up to the point where it is actually usable)

### 8-Confirm the final slicing

- Once the slicing has converged, present the slicing once again
- Demand confirmation to move to the next step

### 9-Document

## Possible actions

**Refine a shape or component**

When a shape has underspecified components.
- Generate multiple options.
- If they involve new techs, ALWAYS search & read its documentation to test your assumptions

**Generate alternatives shapes**

Here are ideas on directions to explore:

- What are radically different system architectures that we could think of?  
- Remove components altogether: what happens then? What's the simplest way to get back to a functioning shape? 
- What are sources of complexity? How can we remove them?
- Are we using our libraries and other vendors to their best? Search the doc and identify ways we could better leverage them.

**Generate alternative journeys**

- Shift responsibilities between the system and the actor: make the system do more or less than it does.
- What would the simplest journey you can imagine that would still fulfil the actor's expected outome.

**Evolve the requirements list**

- Gather new requirements from the user feedback. 
- Generate hypotheses about adjacent requirements
- ALWAYS confirm with the user

**Spike**

A spike is an investigation task to learn how the existing system works and what concrete steps are needed to implement a component. Use spikes when there's uncertainty about mechanics or feasibility.

**Challenge the baseline**

- When a shaping sessions takes an existing system as a starting point, we tend to sliently enforce a non-regression principle. 
- However a significant part of the system design is the result of accident rather than enlighted choices. 
- Moreover, what used to be true when it was designed might not be true anymore.

To challenge the baseline:
- Identify silent requirements inherited from the baseline, with regards to the journeys and the system.
- What happens if we drop them? What is really necessary? 
- What silent tradeoffs are being surfaced? Is there any other possible option than "keep" or "remove"?

**Adversarial review of your assumptions**

Review the journeys / the system behaviours, the requirements, and the shapes:
- What are gaps that are silently filled by assumptions? 
- What intrinsic knowledge do you rely on to make specific assertions? 

**Slice**

Slicing is done at least once at the end of the shaping. 

But slicing a shape forces to consider intermediate / partial states, which may provide new ideas.

**Other**

Other ideation techniques:
- Inversion: "What if we did the opposite?"
- Constraint removal: "What if budget/time/tech weren't factors?"
- Audience shift: "What if this were for [different actor]?"
- Combination: "What if we merged this with [adjacent idea]?"
- Simplification: "What's the version that's 10x simpler?"
- 10x version: "What would this look like at massive scale?"
- Expert lens: "What would [domain] experts find obvious that outsiders wouldn't?"

## Spikes

A spike is an investigation task to learn how the existing system works and what concrete steps are needed to implement a component. Use spikes when there's uncertainty about mechanics or feasibility.

### File Management

**Always create spikes in their own file** (e.g.,`spike_[topic].md`). Spikes are standalone investigation documents that may be shared or worked on independently from the shaping doc.

### Purpose

- Learn how the existing system works in the relevant area
- Identify **what we would need to do** to achieve a result
- Enable informed decisions about whether to proceed
- Not about effort — effort is implicit in the steps themselves
- **Investigate before proposing** — discover what already exists; you may find the system already satisfies requirements

### Structure

```markdown
## [Component] Spike: [Title]

### Context
Why we need this investigation. What problem we're solving.

### Goal
What we're trying to learn or identify.

### Questions

| # | Question |
|---|----------|
| **X1-Q1** | Specific question about mechanics |
| **X1-Q2** | Another specific question |

### Acceptance
Spike is complete when all questions are answered and we can describe [the understanding we'll have].
```

### Acceptance Guidelines

Acceptance describes the **information/understanding** we'll have, not a conclusion or decision:

- ✅ "...we can describe how users set their language and where non-English titles appear"
- ✅ "...we can describe the steps to implement [component]"
- ❌ "...we can answer whether this is a blocker" (that's a decision, not information)
- ❌ "...we can decide if we should proceed" (decision comes after the spike)

The spike gathers information; decisions are made afterward based on that information.

### Question Guidelines

Good spike questions ask about mechanics:
- "Where is the [X] logic?"
- "What changes are needed to [achieve Y]?"
- "How do we [perform Z]?"
- "Are there constraints that affect [approach]?"

Avoid:
- Effort estimates ("How long will this take?")
- Vague questions ("Is this hard?")
- Yes/no questions that don't reveal mechanics


## Notation

### R: Requirements
A numbered set defining the problem space.

- **R0, R1, R2...** are members of the requirements set
- Requirements are negotiated collaboratively - not filled in automatically
- Track status: Core goal, Undecided, Leaning yes/no, Must-have, Nice-to-have, Out
- Requirements extracted from fit checks should be made standalone (not dependent on any specific shape)
- **R states what's needed, not what's satisfied** — satisfaction is always shown in a fit check (R × S)
- **Chunking policy:** Never have more than 9 top-level requirements. When R exceeds 9, group related requirements into chunks with sub-requirements (R3.1, R3.2, etc.) so the top level stays at 9 or fewer. This keeps the requirements scannable and forces meaningful grouping.

### S: Shapes (Solution Options)
Letters represent mutually exclusive solution approaches.

- **A, B, C...** are top-level shape options (you pick one)
- **C1, C2, C3...** are components/parts of Shape C (they combine)
- **C3-A, C3-B, C3-C...** are alternative approaches to component C3 (you pick one)

### Shape Titles
Give shapes a short descriptive title that characterizes the approach. Display the title when showing the shape:

```markdown
## E: Modify CUR in place to follow S-CUR

| Part | Mechanism |
|------|-----------|
| E1 | ... |
```

Good titles capture the essence of the approach in a few words:
- ✅ "E: Modify CUR in place to follow S-CUR"
- ✅ "C: Two data sources with hybrid pagination"
- ❌ "E: The solution" (too vague)
- ❌ "E: Add search to widget-grid by swapping..." (too long)

### Notation Hierarchy

| Level | Notation | Meaning | Relationship |
|-------|----------|---------|--------------|
| Requirements | R0, R1, R2... | Problem constraints | Members of set R |
| Shapes | A, B, C... | Solution options | Pick one from S |
| Components | C1, C2, C3... | Parts of a shape | Combine within shape |
| Alternatives | C3-A, C3-B... | Approaches to a component | Pick one per component |


## Shape Parts

### Flagged Unknown (⚠️)

A mechanism can be described at a high level without being concretely understood. The **Flag** column tracks this:

| Part | Mechanism | Flag |
|------|-----------|:----:|
| **F1** | Create widget (component, def, register) | |
| **F2** | Magic authentication handler | ⚠️ |

- **Empty** = mechanism is understood — we know concretely how to build it
- **⚠️** = flagged unknown — we've described WHAT but don't yet know HOW

**Why flagged unknowns fail the fit check:**

1. **✅ is a claim of knowledge** — it means "we know how this shape satisfies this requirement"
2. **Satisfaction requires a mechanism** — some part that concretely delivers the requirement
3. **A flag means we don't know how** — we've described what we want, not how to build it
4. **You can't claim what you don't know** — therefore it must be ❌

Fit check is always binary — ✅ or ❌ only. There is no third state. A flagged unknown is a failure until resolved.

This distinguishes "we have a sketch" from "we actually know how to do this." Early shapes (A, B, C) often have many flagged parts — that's fine for exploration. But a selected shape should have no flags (all ❌ resolved), or explicit spikes to resolve them.

### Parts Must Be Mechanisms

Shape parts describe what we BUILD or CHANGE — not intentions or constraints:

- ✅ "Route `childType === 'letter'` to `typesenseService.rawSearch()`" (mechanism)
- ❌ "Types unchanged" (constraint — belongs in R)

### Avoid Tautologies Between R and S

**R** states the need/constraint (what outcome). **S** describes the mechanism (how to achieve it). If they say the same thing, the shape part isn't adding information.

- ❌ R17: "Admins can bulk request members to sign" + C6.3: "Admin can bulk request members to sign"
- ✅ R17: "Admins can bring existing members into waiver tracking" + C6.3: "Bulk request UI with member filters, creates WaiverRequests in batch"

The requirement describes the capability needed. The shape part describes the concrete mechanism that provides it. If you find yourself copying text from R into S, stop — the shape part should add specificity about *how*.

### Parts Should Be Vertical Slices

Avoid horizontal layers like "Data model" that group all tables together. Instead, co-locate data models with the features they support:

- ❌ **B4: Data model** — Waivers table, WaiverSignatures table, WaiverRequests table
- ✅ **B1: Signing handler** — includes WaiverSignatures table + handler logic
- ✅ **B5: Request tracking** — includes WaiverRequests table + tracking logic

Each part should be a vertical slice containing the mechanism AND the data it needs.

### Extract Shared Logic

When the same logic appears in multiple parts, extract it as a standalone part that others reference:

- ❌ Duplicating "Signing handler: create WaiverSignature + set boolean" in B1 and B2
- ✅ Extract as **B1: Signing handler**, then B2 and B3 say "→ calls B1"

```markdown
| **B1** | **Signing handler** |
| B1.1 | WaiverSignatures table: memberId, waiverId, signedAt |
| B1.2 | Handler: create WaiverSignature + set member.waiverUpToDate = true |
| **B2** | **Self-serve signing** |
| B2 | Self-serve purchase: click to sign inline → calls B1 |
| **B3** | **POS signing via email** |
| B3.1 | POS purchase: send waiver email |
| B3.2 | Passwordless link to sign → calls B1 |
```

### Hierarchical Notation

Start with flat notation (E1, E2, E3...). Only introduce hierarchy (E1.1, E1.2...) when:

- There are too many parts to easily understand
- You're reaching a conclusion and want to show structure
- Grouping related mechanisms aids communication

| Notation | Meaning |
|----------|---------|
| E1 | Top-level component of shape E |
| E1.1, E1.2 | Sub-parts of E1 (add later if needed) |

Example of hierarchical grouping (used when shape is mature):

| Part | Mechanism |
|------|-----------|
| **E1** | **Swap data source** |
| E1.1 | Modify backend indexer |
| E1.2 | Route letters to new service |
| E1.3 | Route posts to new service |
| **E2** | **Add search input** |
| E2.1 | Add input with debounce |

## Communication

### Show Full Tables

When displaying R (requirements) or any S (shapes), always show every row — never summarize or abbreviate. The full table is the artifact; partial views lose information and break the collaborative process.

- Show all requirements, even if many
- Show all shape parts, including sub-parts (E1.1, E1.2...)
- Show all alternatives in fit checks

### Why This Matters

Shaping is collaborative negotiation. The user needs to see the complete picture to:
- Spot missing requirements
- Notice inconsistencies
- Make informed decisions
- Track what's been decided

Summaries hide detail and shift control away from the user.

### Mark Changes with 🟡

When re-rendering a requirements table or shape table after making changes, mark every changed or added line with a 🟡 so the user can instantly spot what's different. Place the 🟡 at the start of the changed cell content. This makes iterative refinement easy to follow — the user should never have to diff the table mentally.

