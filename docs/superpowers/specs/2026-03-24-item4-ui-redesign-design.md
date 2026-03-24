# Item 4 Design: Voice-Todos UI Refresh

Scope: replace the current barebones frontend UI with a near 1:1 adaptation of the provided "Motion Light" reference, while preserving the existing live voice session behavior from items 1-3.

## Why this exists

The original roadmap framed item 4 as tentative vs confirmed todos. That is no longer the right scope for this project state. Item 3 already handles the core incremental extraction and snapshot replacement behavior. The next useful step is a UI rewrite:

- make the app feel like a real product instead of a prototype
- keep todos as the primary surface
- preserve the existing live recording and stop-time extraction behavior
- follow the provided HTML reference closely instead of inventing a new visual direction

## Goals

- Match the provided reference layout and visual tone as closely as practical
- Keep the existing recording lifecycle: `idle -> connecting -> recording -> extracting -> idle`
- Make the todo list the primary content area
- Remove the transcript from the main flow
- Preserve the current real-time todo updates during recording
- Add subtle visual emphasis when todos are added or refined

## Non-goals

- Tentative vs confirmed todo state
- New backend protocol or message types
- Stable todo identities from the backend
- Reinterpreting the mock into a different layout system
- Building a fully designed settings or overflow-menu experience

## Approved Product Decisions

- Title: `Voice-Todos`
- Layout: centered phone-shell card even on desktop
- Header: title only, no top-right more button
- Transcript: removed from the main flow
- Typography: match the reference closely with `Archivo` and `Manrope`
- Todo update treatment: subtle change highlight, not explicit tentative/confirmed states
- Connecting state: disable the main button and relabel it `Connecting...`
- Extracting state: disable the main button and relabel it `Extracting...`

## Canonical Reference

The user-provided HTML is the canonical visual reference for this item. It is checked into the repo at:

- `docs/references/2026-03-24-item4-motion-light-reference.html`

Implementation and planning must open that file directly and treat it as the source of truth for layout, hierarchy, spacing intent, labels, and motion cues. This item is not a loose interpretation exercise.

If this prose spec and the reference HTML ever feel in tension, use this rule:

- the reference HTML wins for visual composition
- this prose spec wins for how real app states map onto that composition

Planning should explicitly cite the reference file, not just this document.

Allowed adaptations are intentionally narrow:

- replace demo data with real `useTranscript()` state
- map the reference controls to real `start()` / `stop()` behavior
- add the missing `connecting` and `extracting` state handling
- preserve warning and debug functionality without letting them dominate the main screen

## Reference HTML Contract

To avoid drift during planning or implementation, the following parts of the reference HTML are considered non-negotiable unless the user explicitly changes them:

- outer page framing: warm full-page background with a single centered phone-shell card
- shell proportions: narrow mobile-style card, rounded corners, fixed bottom dock, scrollable inner feed
- header simplicity: title only in practice, with the mock's top-right button intentionally removed per user decision
- empty-state copy and structure: large mic illustration, `Start speaking...`, and the supporting sentence about voice turning into tasks in real time
- bottom action area: one dominant full-width CTA in the dock
- listening treatment: waveform bars plus `Listening now...` above the CTA during recording
- todo card shape: hollow leading circle, large rounded card, strong title, compact metadata chips
- motion language: spring-style entry and brief warm change highlight derived from `spring-entry`, `wave-bar`, and `flash-orange`

The following parts of the reference are explicitly adapted, not copied literally:

- title text changes from `Voice Tasks` to `Voice-Todos`
- the decorative top-right more button is removed
- demo JavaScript timing is replaced by real React state from `useTranscript()`
- fake demo tasks are replaced by real extracted todos
- the missing `connecting` and `extracting` states are added using the same visual language

## Screen Structure

The app becomes a single centered surface inside `App.tsx`:

1. full-page warm background
2. rounded white phone-shell container
3. simple header with only `Voice-Todos`
4. scrollable main feed for empty states, todos, loading states, and warnings
5. fixed bottom dock containing the listening UI and the single primary action button

This structure should stay close to the provided HTML, including spacing, radii, palette, and vertical composition.

## State Mapping

### Idle, first load

Show the reference empty state:

- large mic illustration
- `Start speaking...`
- supporting copy indicating that speech becomes todos in real time
- primary button labeled `Start Session`

### Connecting

Keep the same overall idle composition, but the button becomes disabled and reads `Connecting...`.

The UI should not prematurely switch into the live listening state until recording actually begins.

### Recording

Show the listening waveform block above the dock button and keep the main button labeled `Finish Session`.

Todos appear in the feed as they arrive from the existing `todos` WebSocket messages. The feed is snapshot-based: the latest payload replaces the rendered list.

### Extracting

Preserve the recording/results layout, but disable the main button and relabel it `Extracting...`.

Two sub-cases matter:

- if todos already exist, keep them visible during extracting
- if no todos exist yet, show loading skeleton cards inside the feed

### Idle after a session with no todos

Do not revert to the first-load empty state if the session actually ran. Instead, show a quiet result-state message in the feed indicating that no todos were found in the recording.

## Todo Feed

The todo feed becomes the primary product surface and should visually match the reference card design:

- white cards with soft border and shadow
- large rounded corners
- hollow leading circle
- strong title typography
- warm neutral metadata chips

The old `Extracted Todos (N)` label is removed. The reference does not show a section heading, and the feed should feel like the main content rather than a report below the transcript.

## Todo Metadata

Render metadata using the existing todo schema:

- `dueDate`
- `priority`
- `category`
- `assignTo`
- `notification` when present

The first four should follow the chip treatment from the reference. `notification` is allowed as an additional chip but should remain visually secondary and only appear when present.

## Subtle Change Highlight

The reference shows two motion patterns:

- spring entry for newly rendered cards
- a brief warm highlight when a card is refined

The real app should preserve that visual idea without pretending it has a full tentative/confirmed state system.

Because the backend sends whole-list snapshots without stable IDs, the frontend highlight behavior is intentionally lightweight:

- best effort detection of changed or newly added todos by comparing the previous and next snapshots
- brief warm highlight on affected cards or fields
- no claim that every semantic change will be perfectly tracked

This is a visual affordance, not a source of truth.

## Transcript And Debug Surfaces

The transcript is removed from the main phone-shell UI.

However, transcript/debug capability should not be deleted from the product entirely. The current `warningMessage`, transcript text, and mic recording URL remain useful for development and troubleshooting.

Design decision for this item:

- keep those details outside the main styled shell
- treat them as a secondary debug/details surface
- do not let them compete with the primary task-first flow

The exact debug affordance is intentionally lightweight and not part of the styled reference adaptation. A simple post-session details panel is sufficient for implementation.

## Warning Handling

Warnings must remain visible when exposed by `useTranscript()`.

They should render as a warm inline notice card inside the main feed, using the same palette family as the reference, rather than as an unrelated utilitarian box.

## Component Mapping

### `frontend/src/App.tsx`

Becomes the screen shell and the state router for:

- header
- feed contents
- warnings
- todo list vs skeleton vs empty/result states
- secondary debug/details section outside the main shell if retained

### `frontend/src/components/RecordButton.tsx`

Stops being a tiny standalone button and becomes the entire bottom dock control area:

- listening waveform block
- state-aware CTA
- disabled states for `connecting` and `extracting`

### `frontend/src/components/TodoList.tsx`

Becomes a simple feed renderer without the old count heading.

### `frontend/src/components/TodoCard.tsx`

Gets rebuilt to match the reference card language and metadata chips.

### `frontend/src/components/TodoSkeleton.tsx`

Keeps the same role but visually matches the new card system so extracting does not flash a different UI language.

### `frontend/src/components/TranscriptArea.tsx`

No longer belongs in the main rendered flow for this item. It may remain as an internal utility until the implementation removes or repurposes it.

## Styling Direction

The reference should drive the styling:

- `Archivo` for headings
- `Manrope` for body copy
- warm off-white page background
- white device shell
- orange primary accent
- large radii
- soft borders and shadows

Global theme primitives, keyframes, and reusable animation classes should live in `frontend/src/index.css`. Components should use those classes rather than duplicating large inline style blocks.

## Testing Strategy

Testing should verify state behavior and rendered copy, not visual pixel perfection.

### App tests

Update `frontend/src/App.test.tsx` to cover:

- first-load empty state
- todo list visible during recording
- todo list remains visible during extracting when todos already exist
- skeletons only when extracting and no todos exist
- post-session no-todos result state
- warning notice rendering

### RecordButton tests

Update `frontend/src/components/RecordButton.test.tsx` to verify:

- `Start Session`
- `Connecting...`
- `Finish Session`
- `Extracting...`

### Todo list/card tests

Update list/card tests so they no longer expect the old heading and still verify conditional metadata rendering against the new presentation.

## Implementation Notes

- Keep the existing `useTranscript()` contract intact
- Do not change backend protocol to support this UI refresh
- Treat the provided reference as the default layout source of truth
- Keep changes focused on the relevant frontend files rather than broad refactors

## Open Assumptions Carried Into Planning

- The secondary debug/details surface can remain simple and unstylized compared with the main shell
- Google-hosted web fonts are acceptable for matching the reference closely
- The change-highlight behavior can be best effort rather than identity-perfect
