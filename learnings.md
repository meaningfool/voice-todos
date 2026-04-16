# Learnings

## Soniox RT: trailing words lost on stop

**Symptom:** Last 1-2 words of speech disappear from the transcript when the user clicks Stop.

**Wrong hypothesis (session 1):** Audio bytes are being dropped between the browser AudioWorklet and the WebSocket. Built a byte-counting test with agent-browser — proved 0 bytes lost. Audio pipeline is fine.
That byte-counting script was retired afterward because it only disproved a
one-time investigation hypothesis and is not part of the durable test surface.

**Wrong hypothesis (session 1):** Soniox streams tokens as interim then final; when the stream ends, tail tokens exist only as interim. Fix: append last interim text to finals. This helped partially but didn't solve the root cause.

**Wrong hypothesis (session 2):** Adding a 200ms delay before tearing down the mic would give Soniox time to finalize. Tested with 0ms, 10ms, 100ms, 500ms, even 2 seconds of silence padding. Didn't help — Soniox still only returned partial text.

**Wrong hypothesis (session 2):** The frontend was independently reconstructing the transcript from interim tokens and losing them on stop due to React state timing. Fix: have the backend send the full transcript in the `stopped` message as source of truth. This fixed a real display bug but not the root cause.

**Root cause (session 2):** We were sending `b""` (empty frame) to signal end-of-stream. This tells Soniox "no more audio" but does NOT finalize pending tokens — they're silently dropped. Soniox has a separate `{"type": "finalize"}` control message that forces all interim tokens to become final. The Soniox console gets the full text because it uses batch processing, not the RT WebSocket.

**Fix:** Send `{"type": "finalize"}` before `b""`. Filter out the `<fin>` marker token. Clear stale interim state after finalize (otherwise interim text from before finalize gets appended, producing duplicated text).

**Key lesson:** Read the API docs. We spent two sessions assuming the empty frame was sufficient to end a stream cleanly. The finalize/finish distinction is documented but not obvious. When an external API behaves differently in its own console vs your code, the first question should be "are we using the API correctly?" not "is there a timing issue?"
