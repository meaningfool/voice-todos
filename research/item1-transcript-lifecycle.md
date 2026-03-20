# Transcript Token Lifecycle

Research covering topic 2 (Transcript Token Lifecycle) from the research index. Traces what Soniox sends, how tokens stabilize, and how it all reaches the UI.

## What Soniox Sends Back

Every response from Soniox is a JSON text frame with this structure:

```json
{
  "tokens": [
    {
      "text": "Hello",
      "start_ms": 600,
      "end_ms": 760,
      "confidence": 0.97,
      "is_final": true
    },
    {
      "text": " world",
      "start_ms": 780,
      "end_ms": 920,
      "confidence": 0.82,
      "is_final": false
    }
  ],
  "final_audio_proc_ms": 760,
  "total_audio_proc_ms": 920
}
```

Each response carries a **batch** of tokens — not one per message. The response also includes two progress markers: `final_audio_proc_ms` (how far the model has committed) and `total_audio_proc_ms` (how far it has processed, including speculative work).

### Token fields

| Field | Type | Description |
|---|---|---|
| `text` | `string` | The recognized text (word, subword, punctuation, whitespace) |
| `is_final` | `boolean` | Whether this token is finalized |
| `confidence` | `number` | Score 0.0–1.0 |
| `start_ms` | `number?` | Token start timestamp in the audio stream |
| `end_ms` | `number?` | Token end timestamp |
| `speaker` | `string?` | Speaker label (if diarization is enabled) |
| `language` | `string?` | Detected language code |

We currently relay only `text` and `is_final` to the browser. The other fields are available if needed later.

### Terminal response

When the session ends (client sends an empty binary frame), Soniox flushes remaining tokens and sends a final response with `"finished": true`. This is the signal to close the connection.

## Two Kinds of Tokens

Every token is either final or non-final. The rule is simple:

- **Final tokens** (`is_final: true`): Sent once. Never repeated, never changed. Append them permanently.
- **Non-final tokens** (`is_final: false`): Provisional. On the next response, the entire set of non-final tokens is **replaced**. Discard all previous non-final tokens and use only the latest batch.

This is a replace-the-whole-set pattern, not grow-one-word-at-a-time.

### Concrete example

User says: "How are you doing?"

| Response | Final tokens (this message) | Non-final tokens (this message) | Display |
|---|---|---|---|
| 1 | — | `"How"`, `"'re"` | How're |
| 2 | — | `"How"`, `" "`, `"are"` | How are |
| 3 | `"How"`, `" "` | `"are"`, `" "`, `"you"` | **How** are you |
| 4 | `"are"`, `" "`, `"you"` | `" "`, `"doing"` | **How are you** doing |
| 5 | `" "`, `"doing"`, `"?"` | — | **How are you doing?** |

Bold = cumulative final text. Observations:

- Response 1 guessed the contraction "How're". By response 2, it corrected to "How are" — the entire non-final set was replaced.
- In response 3, "How" and " " graduated to final. They will never change again.
- Non-final tokens can change, disappear, or be completely rewritten between responses. They are speculative.

## How Often Messages Arrive

Messages arrive as the model processes audio — not on a fixed timer. During active speech, roughly every few hundred milliseconds, with each message carrying one or more tokens. Silence produces no messages.

You cannot configure the response rate. The only timing-related parameter is `max_endpoint_delay_ms` (500–3000ms, default 2000ms), which controls how quickly endpoint detection fires after speech stops.

## Three Things That Finalize Tokens

### 1. Natural model progression

As the model processes more audio and gains confidence, it promotes tokens from non-final to final. This happens continuously — you don't control it. The model decides when it has enough context to commit.

### 2. Automatic endpoint detection

When `enable_endpoint_detection: true` is set, Soniox monitors for utterance boundaries using both acoustic signals (silence, falling intonation) and linguistic signals (does the sentence parse as complete?). This goes beyond simple silence-based VAD.

When it decides a boundary has been reached:
1. All non-final tokens up to the boundary are finalized
2. A special `<end>` token is emitted: `{"text": "<end>", "is_final": true}`

The `<end>` token is always `is_final: true` — it doesn't go through a non-final/final cycle. It appears once, decisively. And because it finalizes everything before it, the slate is clean: zero non-final tokens in flight after an `<end>`.

### 3. Manual finalization

Send `{"type": "finalize"}` as a JSON text frame. The server finalizes all outstanding tokens and emits a `<fin>` marker. The session stays open — you can keep streaming. Useful for push-to-talk or client-side VAD.

Wait ~200ms of silence after speech ends before calling finalize — calling too early degrades accuracy.

### Special tokens

| Token | Trigger | Meaning |
|---|---|---|
| `<end>` | Automatic endpoint detection | Utterance boundary detected |
| `<fin>` | Manual `{"type": "finalize"}` | Manual finalization complete |

Both are `is_final: true`. Neither represents spoken text — they are control signals that should be filtered from display.

## The `<end>` Token and Non-Final Rewind

An important detail: when `<end>` fires, it may "rewind" tokens that were previously shown as non-final.

Consider: the user says "Buy milk. Call the dentist." without pausing. Before Soniox detects the boundary:

```
Response 4 (no endpoint yet):
  tokens: [{text: " Call", is_final: false}, {text: " the", is_final: false}]

  finalText:   "Buy milk."
  interimText: " Call the"
  Screen:      Buy milk. Call the
```

The user sees "Call the" as interim text. Then Soniox decides the boundary was after "milk.":

```
Response 5 (<end> fires):
  tokens: [{text: "<end>", is_final: true}]

  interimText is replaced with "" (no non-final tokens in this response)
  finalText:   "Buy milk." + <end>
  Screen:      Buy milk.
```

" Call the" disappears — it was non-final and got replaced by an empty set. Then it comes back in the next response as part of the new utterance:

```
Response 6 (next utterance starts fresh):
  tokens: [{text: "Call", is_final: false}, {text: " the", is_final: false}]

  finalText:   "Buy milk.<end>"
  interimText: "Call the"
  Screen:      Buy milk. Call the
```

This works because non-final tokens are always disposable. The replace-the-whole-set rule handles the rewind naturally — no special logic needed.

## `finished` vs `<end>` vs the Stop Button

Three distinct "ending" concepts that don't overlap:

| Signal | Who decides | What it means | Connection stays open? |
|---|---|---|---|
| Long silence | Nobody | Nothing happens — Soniox waits | Yes |
| `<end>` token | Soniox (endpoint detection) | "That utterance is complete, but I'm still listening" | Yes |
| `finished: true` | Us (via empty binary frame) | "Session over, no more audio" | No — Soniox closes |
| Stop button | User | Triggers the empty frame → finished chain | No |

Soniox never decides the session is over on its own. It either detects utterance boundaries (if endpoint detection is on) or waits forever. The session lifecycle is entirely in our hands.

The stop button chain: browser sends `{"type": "stop"}` → FastAPI sends empty binary frame to Soniox → Soniox flushes and sends `{"finished": true}` → FastAPI sends `{"type": "stopped"}` to browser → browser transitions to idle.

## The FastAPI Bridge

The relay in `ws.py` does a light transformation:

- **Strips fields**: Only `text` and `is_final` are forwarded. Confidence, timestamps, speaker, and language are dropped.
- **Wraps in protocol**: Adds `{"type": "transcript", ...}` envelope.
- **Detects `finished`**: When Soniox sends `{"finished": true}`, the relay sends `{"type": "stopped"}` to the browser.

The relay does not batch, debounce, or reorder tokens. Every Soniox response becomes one browser message, 1:1. It adds negligible latency — just the network hop through the server.

## Endpoint Detection and Todo Extraction

We discussed whether Soniox's `<end>` token (utterance boundaries) would be the right trigger for extracting todos in item 3.

The conclusion: **utterance boundaries and todo boundaries are different things.** A single utterance can contain multiple todos ("buy milk and call the dentist and pick up the kids"). Multiple utterances can form one todo ("about the milk... the organic one... from Trader Joe's"). Soniox's endpoint detection solves a speech segmentation problem; todo extraction is an intent segmentation problem.

For item 3, a simpler approach is likely better: periodically send accumulated final text to the LLM and let it identify todos, regardless of where utterance boundaries fall. The `<end>` token could serve as a throttling signal (a natural moment to trigger extraction), but the LLM should decide what's a todo, not the acoustic model.

We do not currently enable endpoint detection. This decision can be revisited when item 3 work begins.

## What Our Code Does Not Handle Yet

These are all additive — the current pipeline is correct, just minimal:

- **`<end>` and `<fin>` marker tokens**: Would need to be filtered from display text if endpoint detection or manual finalization is enabled.
- **Confidence scores**: Available but not relayed. Could be used for visual styling or extraction quality signals.
- **Timestamps**: Available but not relayed. Needed for word-level highlighting or time-aligned playback.
- **`final_audio_proc_ms` / `total_audio_proc_ms`**: Not relayed. Useful for latency monitoring.
