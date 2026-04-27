## Structure of a spec document

```markdown
# Spec: [Title]

## Objective
- What behaviour change this spec introduces

## Non-goals
- What this spec does not attempt to change.

## Slices

[List all the slices/sub-slices with their respective acceptance criteria and acceptance tests]

### Slice N: [Name]

#### Sub-slice Ni: [Name]

**Goal:** [What behaviour change this (sub-)slice introduces]

**Description:** [Description of the baseline and the target]

**Acceptance criteria:**
- [acceptance criterion 1]
- [acceptance criterion 2]
- ...


---

## Decision record

[List all the meaningful decisions and tradeoffs, rejected options with rationale. If shaping.md exist, link to it, and list only the additional decisions.]


```






