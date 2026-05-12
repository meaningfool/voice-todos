# Logfire Query API Notes

Focused notes from live benchmark-report debugging on April 16, 2026.

## Scope

These notes are about benchmark report case enrichment against Logfire, not
about app-level trace analysis.

The concrete use case was:

- benchmark summary rows already existed in Logfire
- case-level report enrichment was still empty in the JSON report
- the report path queried `records` for case spans by `trace_id`

## Main findings

### 1. `Retry-After`

During sequential per-trace case-span probing, Logfire returned `429 Too Many
Requests` with `Retry-After: 12`.

Meaning:

- `12` means the server is asking the client to wait 12 seconds before retrying
- this is standard HTTP behavior, not a Logfire-specific custom header

Observed behavior:

- the current per-trace report enrichment path retried after `1s`, `2s`, and
  `3s`
- that was too early relative to the server-provided `12` second cooldown
- some traces succeeded, later traces were rate-limited, and the report path
  then dropped all case-row enrichment

Decision for the next implementation step:

- do not add `Retry-After` handling in the next change
- keep this documented as a known rate-limit behavior for a future hardening
  pass

## 2. API `limit`

The Logfire Query API docs say the HTTP API supports an explicit `limit`
parameter, with a default of `500` and a max of `10,000`.

Live spike result for the extraction benchmark case-span query:

- `7` traces
- expected case rows: `182`

Observed:

- without explicit API `limit`: only `100` rows returned
- with `limit=1000`: all `182` rows returned

Practical conclusion:

- the benchmark report path should pass an explicit API `limit`
- SQL `LIMIT` alone was not sufficient for this case

## 3. `min_timestamp` / `max_timestamp`

The official Logfire Query API clients support `min_timestamp` and
`max_timestamp`.

Relevant documented behavior:

- the HTTP query API accepts `min_timestamp` and `max_timestamp`
- `logfire.db_api.connect(...)` defaults to a `24h` minimum timestamp window
  unless overridden

Live spike result:

- adding a narrow time window made the all-traces query faster
- but it was not required to make the query complete for our current benchmark
  scale

Decision for the next implementation step:

- do not introduce `min_timestamp` / `max_timestamp` filtering yet
- our benchmark report use case does not currently need that extra complexity

## 4. Query shape that worked

For the extraction benchmark report case spans, the following worked well:

- one query against `records`
- filter by all selected `trace_id`s in the same SQL statement
- pass explicit API `limit=1000`

This returned the full expected result set in one request:

- `182` rows
- `7` traces

That was enough to avoid the burst of per-trace requests that previously caused
the `429` failures.

## 5. Official clients

The following official Logfire read paths both worked for the same all-traces
query:

- `logfire.query_client.LogfireQueryClient.query_json_rows(...)`
- `logfire.db_api.connect(...)`

Both returned the complete `182`-row result set when given:

- the same SQL
- explicit `limit=1000`
- the same narrow time window

Decision for the next implementation step:

- keep the current report implementation on the existing query path
- do not switch clients just for this change
- the immediate win is the query shape plus explicit API `limit`

## 6. Recommended next step

For benchmark report case enrichment:

- switch from per-trace case-span requests to one all-traces request
- pass explicit API `limit`
- leave `Retry-After` handling and timestamp-window filtering for later unless
  they become necessary again

## Sources

- Logfire Query API:
  https://pydantic.dev/docs/logfire/manage/query-api/
- Logfire Explore docs:
  https://pydantic.dev/docs/logfire/observe/explore/
- HTTP `Retry-After`:
  https://datatracker.ietf.org/doc/html/rfc9110#section-10.2.3
