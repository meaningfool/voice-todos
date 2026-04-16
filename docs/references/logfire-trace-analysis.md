# Logfire Trace Analysis

Analysis of telemetry data from two recording sessions on 2026-03-25, compared against the baseline session from 2026-03-24.

For benchmark-report query behavior and Logfire Query API notes, see
`docs/references/2026-04-16-logfire-query-api-notes.md`.

## Setup

- **Service**: `voice-todos-backend` (previously reported as `unknown_service`, fixed by setting `service_name` in `logfire.configure()`)
- **Model**: `gemini-3-flash-preview` via Google Generative Language API (`google-gla`)
- **Query method**: Logfire SQL API at `https://logfire-eu.pydantic.dev/v1/query` using a read token
- **Dashboard**: https://logfire-eu.pydantic.dev/meaningfool/voice-todos

## Instrumentation changes (2026-03-25)

Replaced per-event `ws.soniox_event` (80 spans) and `ws.browser_relay` (74 spans) with a single `ws.soniox_relay` span that records `soniox_event_count` and `browser_relay_count` as attributes on completion. Result: session 1 yesterday produced 191 spans; session 1 today produced 45 spans for comparable content.

## Session inventory

| Session | Trace ID prefix | Time (UTC) | Soniox events | Relays | Extractions | Todos found | Total cost |
|---------|----------------|------------|---------------|--------|-------------|-------------|------------|
| Mar 24 #1 | `019d20cc8763` | 17:02–17:03 | 80 | 74 | 8 | 2 | ~$0.02 |
| Mar 25 #1 | `019d257a1a1b` | 14:50–14:52 | 148 | 137 | 12 | 3 | ~$0.03 |
| Mar 25 #2 | `019d257fabc6` | 14:56–14:57 | 48 | 30 | 3 | 1 | ~$0.005 |

Additionally, 13 ghost connections at 09:39:34 UTC on Mar 25 — each opened a WebSocket, received 1 Soniox event (the `finished` signal), relayed nothing, and closed. Likely caused by frontend dev server hot-reload or browser reconnects on page load.

## Finding 1: Soniox finalization delay dominates stop latency

When the user clicks stop, the server sends a `finalize` command and an empty frame to Soniox, then waits for the relay task to complete (Soniox must send a `finished: true` event and close its WebSocket). Only after the relay task finishes does the final extraction begin.

**Session 1 stop sequence:**

```
14:51:55.434  Last regular send_todos (3 todos)
              ── 14 seconds waiting for Soniox to close ──
14:52:09.551  ws.soniox_relay ends
14:52:09.556  ws.final_extraction starts
14:52:15.874  ws.final_extraction ends (LLM call ~6.3s)
```

**Session 2 stop sequence:**

```
14:57:18.787  Last regular send_todos (1 todo)
              ── 27 seconds waiting for Soniox to close ──
14:57:45.406  ws.soniox_relay ends
14:57:45.416  ws.final_extraction starts
14:57:49.364  ws.final_extraction ends (LLM call ~3.9s)
```

The perceived "long wait after pressing stop" is the Soniox finalization delay (14–27s), not the LLM extraction (4–6s). The code path is in `ws.py` lines 211–237: `await asyncio.wait_for(relay_task, timeout=...)`.

**Possible optimization**: Start the final extraction immediately after sending `finalize`, using the transcript accumulated so far, rather than waiting for Soniox to fully close. The transcript is effectively complete at the point the user stops.

## Finding 2: Thinking tokens dominate LLM output cost

Gemini Flash uses 85–97% of its output tokens on internal "thinking" for what is a structured extraction task.

| Call # | Transcript length | Output tokens | Thinking tokens | Thinking % | Actual result |
|--------|------------------|---------------|-----------------|------------|---------------|
| 1 | 38 chars | 96 | 83 | 87% | `[]` (empty) |
| 5 | 166 chars | 993 | 962 | 97% | 1 todo (same as before) |
| 10 | 298 chars | 2,034 | 1,933 | 95% | 2 todos (same as before) |
| 12 (final) | 369 chars | 1,131 | 1,030 | 91% | 3 todos |

Output tokens vary wildly between calls even when the result is identical (call #8 used 489 tokens, call #10 used 2,034 tokens — both returned the same 2 todos). This suggests the model is overthinking on repeated extractions.

**Possible optimizations**: Disable thinking/reasoning for this model call if Gemini supports a `thinking_budget: 0` parameter, or use a non-thinking model for extraction since the task doesn't require chain-of-thought reasoning.

## Finding 3: Extraction frequency is too aggressive

With `TOKEN_THRESHOLD = 10`, the system triggers extraction every few seconds during active speech. Session 1 ran 12 extraction cycles in ~60 seconds over 369 characters of transcript. Many consecutive calls returned identical results:

- Calls #3–#4: both returned 1 todo ("Buy flowers for mom's birthday")
- Calls #5–#9: all returned 2 todos (same list)
- Calls #11–#12: both returned 3 todos (same list)

Each redundant call costs ~$0.002–0.006 in thinking tokens for no new information.

**Possible optimization**: Increase `TOKEN_THRESHOLD`, debounce extractions, or skip extraction when the transcript hasn't changed since the last call.

## Finding 4: Final extraction often duplicates the previous result

In session 1, the final extraction (`trigger_reason=stop`) operated on 369 chars — the exact same transcript length as the previous cycle — and returned the same 3 todos. In session 2, the final extraction also returned the same 1 todo as the last regular cycle.

The final extraction is a safety net for cases where new speech arrived after the last extraction, but it should check whether the transcript has changed before making another LLM call.

## Logfire dashboard notes

### Column reference

| Field | Meaning |
|-------|---------|
| `otel_scope_name` | Which library produced the span: `opentelemetry.instrumentation.fastapi` (auto), `logfire` (manual spans), `pydantic-ai` (agent/LLM auto) |
| `level` | Severity: trace < debug < **info** (default) < notice < warning < error < fatal |
| `service_name` | Set via `logfire.configure(service_name=...)` — identifies the service in traces |
| `gen_ai.provider.name: google-gla` | Google Generative Language API (Gemini via AI Studio, not Vertex) |
| `gen_ai.usage.details.thoughts_tokens` | Gemini's internal reasoning tokens (billed as output tokens) |
| `operation.cost` | Estimated USD cost per LLM call |

### Useful SQL queries

```sql
-- Find all sessions with duration
SELECT start_timestamp, end_timestamp, trace_id, attributes
FROM records
WHERE span_name = 'ws.connection_session'
ORDER BY start_timestamp DESC

-- Total cost per session
SELECT r.trace_id,
       SUM(CAST(c.attributes->>'operation.cost' AS DOUBLE)) as session_cost
FROM records r
JOIN records c ON r.trace_id = c.trace_id
WHERE r.span_name = 'ws.connection_session'
  AND c.span_name = 'chat gemini-3-flash-preview'
GROUP BY r.trace_id

-- Thinking token ratio per call
SELECT start_timestamp,
       attributes->>'gen_ai.usage.output_tokens' as output,
       attributes->>'gen_ai.usage.details.thoughts_tokens' as thinking
FROM records
WHERE span_name = 'agent run'
ORDER BY start_timestamp DESC
```

### MCP integration

Logfire offers an MCP server for direct querying from Claude Code:

```bash
claude mcp add logfire --transport http https://logfire-eu.pydantic.dev/mcp
```
