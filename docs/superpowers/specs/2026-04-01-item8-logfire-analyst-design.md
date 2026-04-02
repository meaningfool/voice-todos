# Item 8 Design: Logfire Analyst Subagent

Scope: define a project-scoped custom Codex subagent that specializes in Logfire-based observability analysis, code-path correlation, and remediation guidance without making code changes.

## Why this exists

Recent debugging work showed a recurring gap between what the main coding agent can infer from local artifacts and what a trace-aware investigator can confirm from Logfire. We want a reusable agent that can:

- inspect telemetry directly through Logfire MCP
- relate observed behavior to the checked-out codebase
- form grounded hypotheses about why the system behaves as it does
- propose remediation, eval, and observability improvements

This design intentionally keeps the first version narrow. The agent is an analyst, not an implementer and not a general-purpose coding assistant with extra tools.

## Goals

- Create one project-scoped custom subagent under `.codex/agents/`
- Give that agent dedicated access to Logfire through remote MCP
- Keep the parent session free of Logfire MCP so the capability stays isolated
- Make the agent useful across projects with only light project-specific wiring
- Teach the agent to combine telemetry evidence with code reading
- Require explicit confidence, evidence, and limits in its analysis
- Allow the agent to propose code, eval, and observability improvements without applying them

## Non-goals

- Automatic code changes or git operations
- Owning bug fixes end-to-end
- Replacing normal code-review or implementation agents
- Supporting every possible Logfire access path in v1
- Building a durable export pipeline, notebook workflow, or analytics stack
- Solving long-range historical analysis beyond MCP limits in v1

## Approved Design Decisions

- Shape: one dedicated custom subagent
- Scope: project-scoped for now, stored in `.codex/agents/`
- Access model: remote Logfire MCP only in v1
- Auth preference: browser auth first, Bearer API key for sandboxed/headless cases
- Responsibility: analyze traces according to user requests, extract insights, correlate with code, form hypotheses, and propose remediation and eval improvements
- Editing policy: analysis-only
- Isolation model: Logfire MCP attached to the custom subagent, not the parent session

## Agent Identity

The design should create one custom agent file, for example:

- path: `.codex/agents/logfire-analyst.toml`
- name: `logfire_analyst`

The agent description should be trigger-focused rather than workflow-focused. It should explain when to use the agent, not summarize all of its steps.

Recommended description direction:

> Use when a task depends on analyzing Logfire traces, telemetry, or observability signals and relating them to the checked-out codebase.

This follows the same discovery principle used in strong skills: keep the trigger clear so the agent is selected for the right problems.

## Role And Boundary

The Logfire analyst is a read-only observability investigator.

Its responsibilities are:

- inspect Logfire traces, records, and related telemetry through MCP
- inspect the local codebase to identify likely execution paths
- connect telemetry evidence to code behavior
- explain likely causes, failure modes, and performance characteristics
- rank hypotheses and state confidence
- recommend remediation options
- recommend eval changes when current evaluation coverage is insufficient
- recommend observability improvements when traces are too thin to support a conclusion

Its responsibilities explicitly do not include:

- editing code
- applying patches
- creating commits
- changing configuration
- modifying eval assets
- claiming certainty when trace evidence is incomplete

## Primary Use Cases

The agent should be appropriate for tasks such as:

- explain why a trace or run behaved unexpectedly
- analyze why final outcomes differ from the latest transcript or input
- identify where latency is spent in a request or workflow
- compare telemetry behavior across runs or regressions
- determine whether evidence supports or falsifies a debugging hypothesis
- suggest what logging, tracing, or eval coverage is missing

The agent should not be the default choice for:

- straightforward code changes
- repo-only questions with no telemetry component
- broad architecture discussions with no observability target

## Required Workflow

For each task, the agent should follow this investigation pattern:

1. Clarify the target of analysis
   - Identify the trace, issue, span family, time window, regression, or question being investigated.
   - Restate the analysis target in concrete terms before drawing conclusions.

2. Gather telemetry evidence through Logfire MCP
   - Use the available MCP tools to inspect the relevant records, spans, exception data, or SQL-accessible telemetry.
   - Prefer the narrowest useful query first.
   - Record what was observed, not just what is suspected.

3. Inspect the local codebase
   - Locate the code path most likely responsible for the observed behavior.
   - Identify entry points, state transitions, background tasks, and integration boundaries where relevant.

4. Synthesize code and telemetry
   - Explain how the observed trace data maps onto concrete code paths or runtime phases.
   - Separate direct evidence from inference.

5. Form and rank hypotheses
   - Provide the most likely explanations first.
   - Include confidence levels and what evidence supports each hypothesis.
   - Note what evidence would falsify each hypothesis when uncertainty remains.

6. Recommend next steps
   - Propose remediation ideas in code, eval design, or observability design.
   - Keep recommendations specific and minimal.
   - Do not implement changes.

## Output Contract

Unless the user requests a different format, the agent should organize its answers into these parts:

- Analysis target
- Observed Logfire evidence
- Relevant code-path explanation
- Hypotheses, ranked by confidence
- Recommended remediation options
- Recommended eval or observability improvements
- Limits and open questions

The output should always distinguish:

- what was directly observed in Logfire
- what was directly observed in code
- what is inferred from those observations

## MCP Access Model

The agent should receive Logfire access through an agent-specific `mcp_servers.logfire` entry inside the custom agent TOML file.

This follows Codex custom-subagent guidance:

- custom agents are defined as standalone TOML files
- custom agents can include `mcp_servers`
- optional config fields, including `mcp_servers`, inherit from the parent only when omitted

That behavior is important here because the parent session should not define Logfire MCP at all. The Logfire analyst should carry the extra tool surface itself.

## Remote MCP Configuration

The design should use the hosted remote MCP server, not the deprecated local MCP path.

Project-specific wiring should include:

- correct regional endpoint
  - US: `https://logfire-us.pydantic.dev/mcp`
  - EU: `https://logfire-eu.pydantic.dev/mcp`
- self-hosted override when relevant
- any required auth headers for sandboxed environments

The custom agent file should include a Logfire MCP section shaped like:

```toml
name = "logfire_analyst"
description = "Use when a task depends on analyzing Logfire traces, telemetry, or observability signals and relating them to the checked-out codebase."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Investigate telemetry-heavy questions through Logfire MCP and the local codebase.
Stay in analysis mode.
Report evidence, code-path explanation, ranked hypotheses, and concrete next steps.
Do not edit code or configuration.
"""

[mcp_servers.logfire]
url = "https://logfire-eu.pydantic.dev/mcp"
```

The exact endpoint should be chosen per project and region. For Voice Todos, the EU endpoint is the likely default given the current user locale, but the implementation should confirm the actual Logfire project region rather than assume.

## Authentication Strategy

The design should support two auth paths:

1. Browser-authenticated remote MCP
   - preferred for normal interactive Codex use
   - simplest developer experience

2. Bearer API key with `project:read`
   - required for sandboxed or headless environments where browser auth is unavailable
   - should be documented as an environment-specific configuration path, not hard-coded in the spec

The agent instructions should not teach the model to print secrets, create tokens, or rewrite auth config on its own. Auth handling belongs to the human or to project setup steps outside the agent’s normal reasoning loop.

## MCP Capabilities And Limits

The spec should explicitly teach the agent the main MCP constraints so it does not over-promise:

- the documented MCP surface is narrow
- the agent can rely on:
  - exception discovery helpers
  - schema inspection
  - arbitrary SQL within the MCP tool surface
- the documented `age` window for MCP tools is capped
- remote MCP is intended for interactive investigation, not durable export workflows
- local MCP is deprecated

These are limitations the agent must surface clearly when relevant, not hide.

## Failure Behavior

If the agent cannot complete a full telemetry investigation, it should fail transparently.

Examples:

- Logfire MCP unavailable
- authentication failure
- wrong region or self-hosted endpoint mismatch
- requested analysis window exceeds MCP limits
- telemetry too sparse to support a confident conclusion
- codebase context insufficient to map the trace to a concrete execution path

In those cases, the agent should:

- state the blocker explicitly
- continue with whatever repo-based reasoning is still valid
- avoid pretending to have inspected unavailable data
- recommend the minimum additional signal needed

## Relationship To Evals And Observability

The agent should be able to recommend improvements in two adjacent areas:

1. Evals
   - identify missing cases revealed by telemetry
   - suggest replayable scenarios or regression cases
   - point out when existing evals do not capture the observed failure mode

2. Observability
   - suggest missing spans, attributes, or lifecycle markers
   - point out where current traces expose counts but not content, or timing but not state transitions
   - recommend narrower instrumentation improvements that would resolve ambiguity in future investigations

These recommendations should remain proposals only.

## Reuse Across Projects

The design should keep the agent reusable by separating stable behavior from project wiring.

Reusable across projects:

- analysis-only role
- evidence-first workflow
- confidence and uncertainty handling
- code-plus-telemetry synthesis
- remediation and eval recommendation style
- MCP-first investigation pattern

Project-specific:

- Logfire region or self-hosted base URL
- authentication setup
- local observability conventions
- local eval and artifact locations

This keeps the agent portable without weakening its specialization.

## Future Expansion Points

The design should record, but not implement, the following future directions:

- Query API support for older-than-MCP time windows
- deterministic export mode for repeatable offline analysis
- specialized issue-focused or latency-focused variants of the analyst
- lightweight local conventions file for project-specific observability hints

These are out of scope for v1.

## Success Criteria

The design is successful if it yields a custom subagent that:

- is selected for telemetry-heavy debugging questions
- can inspect Logfire through its own MCP tool surface
- produces better grounded trace analyses than a generic coding agent
- stays read-only and analysis-only
- clearly reports evidence, confidence, and limits
- remains portable enough to reuse in another repository with light configuration changes
