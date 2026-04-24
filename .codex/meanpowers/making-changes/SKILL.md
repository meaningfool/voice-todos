

3. Establish how the agent can automatically verify that the expected change in behaviour was achieved. We call those conditions the Acceptance Criteria.




### 4. Validate the scope of expected changes

Group changes that make sense as a whole but do not if considered separately.
For example:
- "Change 1: the content editor can submit an article for review" does not make sense without
- "Change 2: the content reviewer can review articles submitted for review and validate", which still does not make sense without more changes spelling out what happens when an article is validated, or when it is not validated. 

### 6. Create Acceptance Criteria

For each behavioral change unit, define acceptance criteria that prove whether the promised behavior is matched.

### 7. Present Behavioral Units And Criteria

Present the behavioral units and acceptance criteria to the user for approval.

If the user does not approve, revise the behavioral change units and criteria before continuing.




**Design for isolation and clarity:**

- Break the system into smaller units that each have one clear purpose, communicate through well-defined interfaces, and can be understood and tested independently
- For each unit, you should be able to answer: what does it do, how do you use it, and what does it depend on?
- Can someone understand what a unit does without reading its internals? Can you change the internals without breaking consumers? If not, the boundaries need work.
- Smaller, well-bounded units are also easier for you to work with - you reason better about code you can hold in context at once, and your edits are more reliable when files are focused. When a file grows large, that's often a signal that it's doing too much.

**Working in existing codebases:**

- Explore the current structure before proposing changes. Follow existing patterns.
- Where existing code has problems that affect the work (e.g., a file that's grown too large, unclear boundaries, tangled responsibilities), include targeted improvements as part of the design - the way a good developer improves code they're working in.
- Don't propose unrelated refactoring. Stay focused on what serves the current goal.



When you encounter inconsistencies, conflicting requirements, or unclear specifications:

STOP. Do not proceed with a guess.
Name the specific confusion.
Present the tradeoff or ask the clarifying question.
Wait for resolution before continuing.