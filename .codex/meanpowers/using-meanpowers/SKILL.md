---
name: using-meanpowers
description: Use when starting a conversation - provides context about the framework and the processes to apply when doing software development.
---

# Using Meanpowers

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

## Software development process

```
conversation or document
  → capture         demultiplexer: one inbox item per change

inbox item
  if well-defined   → write-spec
  if vague / large  → shape → write-spec

write-spec → write-plan
```

**`capture`skill:** extracts from a conversation or document a list of changes, establishing the baseline and target behaviour/state of the system and the intent. Files changes in the `inbox`

**`shape`skill:** turns a vague or large expected change into a list of of smaller scale changes organized in `slices`.

**`write-spec` skill:** turns approprietly scoped changes into a list of clearly defined `steps` with associated `acceptance criteria` in a `spec` document. 

**`write-plan` skill:** turns a `spec` into a detailed `plan` containing all the information for the executor to run on. 

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

### File structure

- In `docs/meanpowers` live an `inbox` folder and a number of `work item` folders. 
- Files in the inbox are created during the `capture` process.
- `work item` folders are created during the `shape` or `write-plan` processes.
- Files in the `work-item` folders are created during the `shape`, `write-plan` and `write-spec` processes. Details are provided by those specific skill files

## Always-on principles and instructions

### Instruction Priority

Superpowers skills override default system prompt behavior, but **user instructions always take precedence**:

1. **User's explicit instructions** (CLAUDE.md, GEMINI.md, AGENTS.md, direct requests) — highest priority
2. **Meanpowers skills** — override default system behavior where they conflict
3. **Default system prompt** — lowest priority

If CLAUDE.md, GEMINI.md, or AGENTS.md says "don't use TDD" and a skill says "always use TDD," follow the user's instructions. The user is in control.

### Using Skills
<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

### How to Access Skills

**In Claude Code:** Use the `Skill` tool. When you invoke a skill, its content is loaded and presented to you—follow it directly. Never use the Read tool on skill files.

**In Gemini CLI:** Skills activate via the `activate_skill` tool. Gemini loads skill metadata at session start and activates the full content on demand.

### Platform Adaptation

Meanpowers skills describe required capabilities, not fixed tool names. Use the
platform-native tool that provides the required capability. Do not skip a
capability because the exact tool name differs from an example.

| Capability | Claude Code | Codex | Gemini CLI |
|------------|-------------|-------|------------|
| Invoke a skill | `Skill` tool | Native skill loading; follow the skill instructions | `activate_skill` |
| Track runtime progress | `TodoWrite` or task-list tools | `update_plan` | `write_todos` |
| Dispatch an isolated subagent | `Agent` tool (`Task` in older docs/examples) | `spawn_agent`, then `wait_agent`/`close_agent` | No direct equivalent; use the documented fallback |
| Run shell commands | `Bash` | shell command tool | `run_shell_command` |
| Read files | `Read` | file/shell read tools | `read_file` |
| Write or edit files | `Write`/`Edit` | apply the platform's file-edit mechanism | `write_file`/`replace` |

### Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check git/files quickly" | Files lack conversation context. Check for skills. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. Skills prevent this. |
| "I know what that means" | Knowing the concept ≠ using the skill. Invoke it. |

### Skill Priority

When multiple skills could apply, use this order:

1. **Process skills first** - these determine HOW to approach the task
2. **Implementation skills second** (frontend-design, mcp-builder) - these guide execution

### Skill Types

**Rigid** (TDD, debugging): Follow exactly. Don't adapt away discipline.

**Flexible** (patterns): Adapt principles to context.

The skill itself tells you which.

### User Instructions

Instructions say WHAT, not HOW. "Add X" or "Fix Y" doesn't mean skip workflows.
