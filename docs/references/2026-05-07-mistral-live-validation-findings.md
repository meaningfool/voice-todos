# Mistral Live Validation Findings

Date: 2026-05-07

This note records the live validation findings for the realtime Mistral STT
path while implementing specs 015 and 016.

## Scope

This note is a trace of observed issues and debugging results. The remaining
live-validation gap is not being solved in this branch.

## Fixture and acceptance surface

Primary fixture used during debugging:

- `backend/tests/fixtures/while-speaking-two-todos/audio.pcm`

Behavioral surface under discussion:

- transcript quality during live realtime use
- whether `todos` appear while audio is still streaming
- whether final stop output contains the expected transcript and todos

## Initial failure

Live validation with `STT_PROVIDER=mistral` initially failed on
`while-speaking-two-todos`.

Observed result:

- the raw realtime transcript was degraded
- no `todos` were emitted during audio in the FastAPI runtime
- final stop output contained only one malformed todo in the failing run

Recorded failing session:

- `sessions/recent/2026-05-07T15-27-55/`

The raw provider trace already contained the degraded text, so the problem was
upstream of extraction and UI rendering.

Example `transcription.done.text` from that failing run:

- `Bei Oatmilk Tonight zijn e-mail Sarah de revised budget.`

## Root cause 1: realtime Mistral is sensitive to target streaming delay

Direct realtime probes against the same fixture showed that transcript quality
changes materially with `target_streaming_delay_ms`.

Observed results:

| `target_streaming_delay_ms` | Result |
|---|---|
| `null` | `Bei Oatmilk Tonight zijn e-mail Sarah de revised budget.` |
| `240` | `Bei Oatmilk Tonight Zen emails Sarah the revised budget.` |
| `1000` | `Buy oat milk tonight, then email Sarah the revised budget.` |
| `2400` | `Buy oat milk tonight. Then email Sarah the revised budget.` |

Conclusion:

- the degraded transcript was not a frontend bug
- the degraded transcript was not an extraction bug
- the degraded transcript was not caused by the runtime-switching seam
- realtime Mistral quality on this fixture depends heavily on the streaming
  delay configuration

Related comparison:

- Mistral offline transcription of the same audio, after wrapping the PCM as
  WAV, produced clean text without this degradation:
  - `Buy oat milk tonight. Then email Sarah the revised budget.`

That narrows the issue to the realtime path rather than the underlying audio or
the extraction model.

## Root cause 2: FastAPI still misses live todo emission during streaming

After improving the realtime transcript quality, the FastAPI runtime still did
not satisfy the acceptance behavior that `todos` appear while audio is still
streaming.

Observed result in FastAPI after the transcript-quality improvement:

- transcript messages streamed correctly
- no `todos` were emitted during audio
- correct `todos` appeared after `stop`

Backend acceptance failure:

- `backend/tests/test_e2e.py::test_while_speaking_two_todos_during_audio_and_final_capture`

Failure shape:

- the test no longer failed on transcript quality
- it still failed on the first assertion requiring at least one `todos`
  message during audio

Current explanation:

- Mistral does not expose Soniox-style endpoint boundaries here
- the backend extraction loop only runs during streaming when:
  - an endpoint is observed, or
  - transcript growth crosses `EXTRACTION_TOKEN_THRESHOLD`
- the current threshold is `15`
- this corrected Mistral transcript is shorter than that threshold during the
  streaming window for the FastAPI path

Relevant backend code:

- `backend/app/ws.py`
- `backend/app/extraction_loop.py`
- `backend/app/extraction_thresholds.py`

## Runtime difference observed

The Cloudflare runtime behaved better than FastAPI on the same fixture during
live browser validation.

Observed result in Cloudflare:

- `todos` appeared during streaming
- final stop output also remained correct

Current conclusion:

- this is not evidence that "Mistral can never support live todos"
- it is evidence that the remaining gap is runtime-specific, or at least highly
  timing-sensitive
- the shared extraction-loop logic is effectively the same in both runtimes, so
  the likely difference is transport or pacing rather than business logic shape

This branch does not resolve that runtime difference.

## Commands used during debugging

Representative commands:

- realtime probe matrix against live Mistral via `uv run python`
- `cd backend && set -a && source .env && set +a && STT_PROVIDER=mistral RUN_E2E_INTEGRATION=1 uv run pytest tests/test_e2e.py::test_while_speaking_two_todos_during_audio_and_final_capture -v`
- FastAPI live browser validation with:
  - `cd backend && set -a && source .env && set +a && STT_PROVIDER=mistral uv run uvicorn app.main:app --port 8000 --log-level warning`
  - `WS_BACKEND=fastapi BACKEND_PORT=8000 FRONTEND_PORT=5174 pnpm dev --host 127.0.0.1 --port 5174`
  - `agent-browser open 'http://127.0.0.1:5174/?fixture=while-speaking-two-todos'`
- Cloudflare live browser validation with:
  - `cd cloudflare && set -a && source ../backend/.env && set +a && STT_PROVIDER=mistral uv run pywrangler dev --port 8790`
  - `WS_BACKEND=cloudflare CLOUDFLARE_PORT=8790 FRONTEND_PORT=5175 pnpm dev --host 127.0.0.1 --port 5175`
  - `agent-browser open 'http://127.0.0.1:5175/?fixture=while-speaking-two-todos'`

## Branch decision

Branch decision for specs 015 and 016:

- keep a written trace of these Mistral live-validation findings
- do not expand this branch to solve the remaining FastAPI live-streaming todo
  gap
- treat any FastAPI-specific follow-up as a separate item

## Recommended follow-up

If this is taken on later, the next investigation should focus on the FastAPI
live extraction trigger for providers that do not expose endpoint boundaries.

Likely follow-up candidates:

- add a provider-agnostic debounce trigger for short transcripts during active
  streaming
- tune or scope the extraction threshold for boundary-less providers
- compare websocket proxying and chunk pacing between the FastAPI and
  Cloudflare live paths before changing extraction rules
