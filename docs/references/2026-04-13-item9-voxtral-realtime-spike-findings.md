# Item 9 Voxtral Realtime Spike Findings

This note records what the realtime spike actually observed from
`voxtral-mini-transcribe-realtime-2602` using prerecorded fixture audio.

Fixtures probed:

- `stop-the-button`
- `continuous-speech`
- `call-mom-memo-supplier`

Raw traces:

- `backend/tests/fixtures/stop-the-button/mistral/trace.jsonl`
- `backend/tests/fixtures/continuous-speech/mistral/trace.jsonl`
- `backend/tests/fixtures/call-mom-memo-supplier/mistral/trace.jsonl`

## Observed event sequence

Across all three fixtures, the event pattern was:

1. `session.created`
2. `session.updated`
3. one or more additive `transcription.text.delta` events
4. one terminal `transcription.done` event

No `transcription.segment` events were observed in these runs.

## Stop-path conclusion

In all three captured traces:

- `transcription.done.text` matched the accumulated `transcription.text.delta`
  text exactly
- no additional correction or rewrite appeared after the visible streaming text
- the terminal event also carried `segments: []`

Current conclusion:

- `TranscriptionStreamDone.text` looks like the best stop-time transcript source
  of truth for a future Voxtral integration
- the captured evidence does not support a Soniox-style "wait for newly-final
  tokens" stop rule
- a future adapter should likely gate final stop handling on
  `transcription.done`, not on token-finalization semantics

This is still evidence from a small trace set, not a universal proof.

## Transcript-semantics conclusion

Observed behavior in these traces:

- transcript updates were additive text deltas
- punctuation can arrive as its own delta
- no per-token finality signal was present
- no replaceable interim batch was present
- no endpoint marker was present

No correction behavior was observed in the captured runs. That means the traces
support an additive streaming model, but they do not yet prove that corrections
can never happen.

## Seam mapping

| Behavior | Soniox today | Voxtral evidence | Fit status | Note |
|---|---|---|---|---|
| Stream audio and receive live transcript events | Provider session streams audio and yields normalized events | Live realtime stream works; raw events arrive reliably | `fits as-is` | Session seam is in the right place for transport |
| Explicit stop barrier | `finalize` then wait for `<fin>` | Wait for terminal `transcription.done` | `fits with different app logic` | Stop barrier moves from token finalization to terminal transcript event |
| Final transcript source on stop | Accumulator plus Soniox finalization semantics | `transcription.done.text` matched streaming text in all traces | `fits with different app logic` | Future Voxtral path should likely trust `done.text` |
| Per-token finality | Soniox `is_final` per token | No such signal observed | `unsupported` | Current token model is too Soniox-shaped here |
| Replaceable interim tail | Non-final tokens are replaced over time | Only additive deltas observed | `unsupported` | Current confirmed/interim UI cannot be reproduced natively |
| Endpoint marker | Soniox `<end>` | No endpoint-like event observed | `unsupported` | Current endpoint-triggered behavior does not carry over directly |
| `transcription.segment` as a possible boundary | Not needed because Soniox already exposes endpoint semantics | Not observed in these traces | `unclear` | Still unresolved until a trace actually contains segment events |

## What this means for Item 9.1

The next spec should assume:

- the session lifecycle seam from Item 8 is viable for Voxtral
- the transcript semantics above that seam need reshaping
- Voxtral integration should start from a single-stream additive transcript
  model
- stop-time logic should be designed around `transcription.done`

The next spec should not assume:

- Soniox-style confirmed/interim token behavior
- Soniox-style endpoint semantics
- that `transcription.segment` can drive product behavior
