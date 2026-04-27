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

**Goal:** [What behaviour change this slice introduces]

**Description:** [Description of the baseline and the target]

**Acceptance criteria:**
- [acceptance criterion 1]
- [acceptance criterion 2]
- ...

#### System changes
[List of system changes to be done in this slice]

---

## Decision record

[List all the meaningful decisions and tradeoffs with regards to the system design, rejected options with rationale. If shaping.md exist, link to it, and list only the additional decisions.]


```






