# Shape Skill Improvements From Cloudflare Hosting Path Shaping

## Context

This note captures improvements suggested by the slicing back-and-forth during
the Cloudflare hosting-path shaping session. The issue was not the existence of
slices, but how the skill guided slicing and how the slices were presented for
work that is mostly refactoring / migration rather than user-facing behavior
change.

## Problems Observed

### 1. The default slice presentation overfit product-facing work

The current shaping skill and final-shaping template frame slices around:

- behavioral or journey delta
- demo scenario
- notes for write-spec

That works well when each slice changes visible behavior. It is weak when the
work is mostly technical and the visible app behavior barely changes.

In this session, the more useful question was:

- what is the state of the system after this slice?

not:

- what new end-user behavior exists after this slice?

### 2. The slicing discussion drifted away from the shaped component map

The session already had a collaboratively built component map (`B1..B8`), but
the slicing exploration temporarily drifted into new abstractions and new axes.

That made the slices harder to understand because the user had to learn a new
mental model instead of reusing the shape model already built.

### 3. The skill does not distinguish enough between product slices and technical slices

The shaping skill says to slice vertically and keep slices demoable, which is
good. But it does not give strong enough guidance for:

- refactoring-heavy work
- migration work
- hosting/runtime replacement
- work where behavior is intentionally preserved for most of the implementation

### 4. The skill does not surface slice rationale early enough

The user needed two top-level answers before caring about per-slice detail:

1. what is the sequence?
2. why this order?

The skill currently goes quickly to per-slice formatting without first making
the sequence and rationale explicit.

### 5. The skill does not encourage component refinement during slicing

During slicing, it became clear that the original `B1` component bundled two
different responsibilities:

- shared session / transcript / finalization logic
- shared todo / extraction logic

Refining `B1` into `B1a` and `B1b` made the final slice sequence much cleaner.
The skill should explicitly allow and encourage this when slicing exposes a
component that is too broad.

## Recommended Skill Changes

### A. Add a refactoring / migration slice mode

The skill should explicitly say:

- when the work is mostly technical and user-facing behavior changes little,
  slices may be technical slices
- in that case, optimize for meaningful intermediate system states and coherent
  responsibilities, not for visible behavior at every step

Suggested wording:

> If the work is primarily refactoring, migration, or runtime replacement, do
> not force every slice to be described as a user-visible behavior change.
> Instead, slice around coherent technical responsibilities and meaningful
> intermediate system states that can still be validated.

### B. Require a slice sequence map before per-slice prose

Before the per-slice prose, the skill should ask for a simple map like:

| Component | V1 | V2 | V3 |
|---|---:|---:|---:|
| B1 | X |  |  |
| B2 | X |  |  |
| B3 |  | X |  |

This worked well because:

- it reused the existing shape component model
- it showed the sequence clearly
- it made alternative slicing orders easy to compare

Suggested guidance:

> When slicing a selected shape, first show a component-to-slice sequence map
> using the existing shape component IDs. Do not invent new axes or new
> abstractions unless the current component model is insufficient.

### C. Add a top-level slicing rationale section

Before the detailed slices, the skill should require:

- the sequence
- the rationale for that sequence

Suggested structure:

```md
## Slice Sequence

[component map]

## Slicing Rationale

- First ...
- Second ...
- Third ...
```

This was much easier for the user to reason about than repeating rationale
inside every slice.

### D. Replace "Behavioral / Journey Delta" with a more neutral field in the final template

For technical slices, the more useful field was:

- `State after this slice`

Suggested template change:

Current:

```md
**Behavioral / journey delta:**
```

Suggested replacement:

```md
**State after this slice:**
```

Behavioral change can still be described there when relevant, but the label
does not force a product-centric reading.

### E. Simplify the per-slice template

The most useful per-slice format in this session was:

```md
### V1: [Slice Name]

**State after this slice:**

...

**Included components:**

- ...

**Notes for write-spec:**

- ...
```

Fields that were less useful or actively confusing in this session:

- behavioral / journey delta
- repeated "why this comes before the next slice"
- repeated "still not done"

Those are better handled once in the top-level rationale.

### F. Add an anti-pattern warning about slice balancing

The skill should explicitly warn against:

- choosing a number of slices first
- stretching components awkwardly across slices to "balance" them
- inventing temporary scaffolding only to preserve a slice count

Suggested wording:

> Do not balance slices for symmetry alone. Prefer grouping work that serves one
> coherent responsibility or transition state, even if that makes later slices
> thinner or thicker.

### G. Add guidance on when to refine components during slicing

Suggested wording:

> If slicing reveals that a selected component bundles multiple responsibilities
> that become real at different times, refine the component model before locking
> the slices. Prefer refining the shape to stretching one component ambiguously
> across several slices.

## Recommended Template Changes

### Final shaping document

Replace the current final-slice section with something like:

```md
## Final Slices

## Slice Sequence

| Component | V1 | V2 | V3 |
|---|---:|---:|---:|
| ... |  |  |  |

## Slicing Rationale

- First ...
- Second ...

### V1: [Slice Name]

**State after this slice:**

...

**Included components:**

- ...

**Notes for write-spec:**

- ...
```

### Shape skill slicing guidance

Add a dedicated subsection for refactoring-heavy slicing:

- identify coherent responsibilities
- identify meaningful intermediate states
- reuse the current shape components as the main map
- allow component refinement before locking slices

## Bottom Line

The main lesson is:

For refactoring-heavy shaping, slices should be explained through the evolution
of the selected shape components and the state of the system after each slice,
not primarily through behavioral deltas.
