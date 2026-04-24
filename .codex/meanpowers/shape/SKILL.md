---
name: shape
description: Use when the user invokes it 
---

# Shaping

## Overview

The `shape` skill is inspired by Ryan Singer's methodology with my own tweaks. It posits that the understanding of a problem co-evolves with the exploration of solutions. 

In the context of Meanpowers, the `shape` skill provides a process to better define large and/or loosely scoped changes.

## File management

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

**Rules**:
1. Commit regularly
2. Each item that goes through shaping gets its own folder in `docs/meanpowers/` named according to the following convention `{next_2-digits_increment_available}_{name_of_the_item_validated_by_the_user}.md`
3. If the session was started from an `inbox` item, move that inbox item into the newly created folder.

## Core concepts

### Definitions

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

### R: Requirements
A numbered set defining the problem space.

- **R0, R1, R2...** are members of the requirements set
- Requirements are negotiated collaboratively
- not filled in automatically
- Track status: Core goal, Undecided, Leaning yes/no, Must-have, Nice-to-have, Out
- **R states what's needed, not what's satisfied** 

#### Requirement titles

- Give requirements short descriptive and specific titles.
- Requirement titles should be framed as assertions, in the present tense.
- Be concrete, avoid introducing new concepts, use a language that a human may use, don't use language that requires a deep prior understanding (acronyms, jargon)

```markdown
| ID | Requirement | Status |
|----|-------------|--------|
| R0 | {title} | Core goal |
| R1 | {title} | Undecided |
| R2 | {title} | {status} |
```

### J: Journeys (Solution Options)

- **J1, J2, J3...** are distinct journeys
- **J1.1, J2.3, J3.1...** are steps in a specific journey
- **J2.3-A, J2.3-B, J2.3-C...** are alternative steps in the a journey

#### Journey & Journey steps Titles

- Give journeys short descriptive and specific titles that characterizes the action performed. 
- Title shoud lead with a verb (e.g. "Create a report")
- Identify clearly which actor is the subject of the journey / step.
- Provide a 1-2 sentences description
- Be concrete, avoid introducing new concepts, use a language that a human may use, don't use language that requires a deep prior understanding (acronyms, jargon)

```markdown
| ID | Journey / Step | Actor | eee |
|----|-------------|--------|-------------|
| J1 | {title} | end-user | {description} |
| J1.1 | {title} | end-user | {description} |
| J2 | {title} | developer | {description} |
| J3 | {title} | back-office user | {description} |
```

### S: Shapes (Solution Options)
Letters represent mutually exclusive solution approaches.

- **A, B, C...** are top-level shape options (you pick one)
- **C1, C2, C3...** are components/parts of Shape C (they combine)
- **C3-A, C3-B, C3-C...** are alternative approaches to component C3 (you pick one)

#### Shape Titles

- Give shapes short descriptive and specific titles that characterizes the approach. 
- Be concrete, avoid introducing new concepts, use a language that a human may use, don't use language that requires a deep prior understanding (acronyms, jargon)

```markdown
| ID | Shape |
|------|-----------|
| E | {title} |
| F | {title} |
```

#### Component Titles

- Give components short descriptive and specific titles that characterizes the change introduced compared to the baseline. 
- Be concrete, avoid introducing new concepts, use a language that a human may use, don't use language that requires a deep prior understanding (acronyms, jargon)
- Flag Unknowns: a component can be described at a high level without being concretely understood. The WHAT is described but we don't yet know HOW. Leave empty otherwise.

```markdown
| ID | Component | Flag |
|------|-----------|:----:|
| E1 | {title} | {⚠️} |
| E2 | {title} | {⚠️} |
```

Example:
```markdown
| ID | Component | Flag |
|------|-----------|:----:|
| **F1** | Lead scoring in the dashboard | |
| **F2** | Magic authentication handler | ⚠️ |
```

### Avoid Tautologies Between R and S

**R** states the need/constraint (what outcome). **S** describes the system. 

Confusion may arise from "solution in disguise" leaking into the requirements

- ❌ R17: "Use Clerk for authentication"
- ✅ R17: "Only authenticated users can access the full articles" + C6.3: "Authentication link + Clerk authentication workflow"

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

| ID | Component |
|------|-----------|
| **E1** | **{component title}** |
| E1.1 | {sub-component title} |
| E1.2 | {sub-component title} |
| **E2** | **{component title}** |
| E2.1 | {sub-component title} |

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

- Always create a document for a shaping session

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


## Fit Check (Decision Matrix)

THE fit check is the single table comparing all shapes against all requirements. Requirements are rows, shapes are columns. This is how we decide which shape to pursue.

### Format

```markdown
## Fit Check

| Req | Requirement | Status | A | B | C |
|-----|-------------|--------|---|---|---|
| R0 | Items are searchable from index page | Core goal | ✅ | ✅ | ✅ |
| R1 | State survives page refresh | Must-have | ✅ | ❌ | ✅ |
| R2 | Back button restores state | Must-have | ❌ | ✅ | ✅ |

**Notes:**
- A fails R2: [brief explanation]
- B fails R1: [brief explanation]
```

### Conventions
- **Always show full requirement text** — never abbreviate or summarize requirements in fit checks
- **Fit check is BINARY** — Use ✅ for pass, ❌ for fail. No other values.
- **Shape columns contain only ✅ or ❌** — no inline commentary; explanations go in Notes section
- **Never use ⚠️ or other symbols in fit check** — ⚠️ belongs only in the Components table's flagged column
- Keep notes minimal — just explain failures

### Missing Requirements
If a shape passes all checks but still feels wrong, there's a missing requirement. Articulate the implicit constraint as a new R, then re-run the fit check.

### Macro Fit Check

A separate tool from the standard fit check, used when working at a high level with chunked requirements and early-stage shapes where most mechanisms are still ⚠️. Use when explicitly requested.

The macro fit check has two columns per shape instead of one:

- **Addressed?** — Does some part of the shape seem to speak to this requirement at a high level?
- **Answered?** — Can you trace the concrete how? Is the mechanism actually spelled out?

**Format:**

```markdown
## Macro Fit Check: R × A

| Req | Requirement | Addressed? | Answered? |
|-----|-------------|:----------:|:---------:|
| R0 | Core goal description | ✅ | ❌ |
| R1 | Guided workflow | ✅ | ❌ |
| R2 | Agent boundary | ⚠️ | ❌ |
```

**Conventions:**
- Only show top-level requirements (R0, R1, R2...), not sub-requirements
- **No notes column** — keep the table narrow and scannable
- Use ✅ (yes), ⚠️ (partially), ❌ (no) for Addressed
- Use ✅ (yes) or ❌ (no) for Answered
- Follow the macro fit check with a separate **Gaps** table listing specific missing parts and their related sub-requirements

## Spikes

A spike is an investigation task to learn how the existing system works and what concrete steps are needed to implement a component. Use spikes when there's uncertainty about mechanics or feasibility:
- Learn how the existing system works in the relevant area
- Identify **what we would need to do** to achieve a result
- Enable informed decisions about whether to proceed
- Not about effort — effort is implicit in the steps themselves
- **Investigate before proposing** — discover what already exists; you may find the system already satisfies requirements

### File Management

- **Always create spikes in their own file in the same folder as the shaping file**. Use the convention `{itemID}_spike_{spike-name}.md`, e.g. `010_spike_clerk-investigation.md`
- The itemID should match the one used in the shaping session that started it
- Use `/references/spike-document-template.md` as template

## Communication

### Show Full Tables

When displaying R (requirements), S (shapes), or J (journeys) always show every row — never summarize or abbreviate. The full table is the artifact; partial views lose information and break the collaborative process.

- Show all requirements, even if many
- Show all shape parts, including sub-parts (E1.1, E1.2...)
- Show all journeys and journey steps, 
- Show all alternatives in fit checks

### Why This Matters

Shaping is collaborative negotiation. The user needs to see the complete picture to:
- Spot missing requirements
- Notice inconsistencies
- Make informed decisions
- Track what's been decided

Summaries hide detail and shift control away from the user.

### Mark Changes with 🟡

When re-rendering a table after making changes, mark every changed or added line with a 🟡 so the user can instantly spot what's different. Place the 🟡 at the start of the changed cell content. This makes iterative refinement easy to follow — the user should never have to diff the table mentally.

