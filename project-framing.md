# Roadmap: Voice Todo

Lightweight story map for the stepping-stone project. The goal is to learn the live voice processing stack on a small, concrete problem: capture todos from continuous speech in a web app.

The deliverable is a demo video showing todos appearing on screen as someone speaks. The repo may be public.

## Working Assumptions

- Web app only. No mobile development.
- The user talks, todos appear. That's the core loop.
- Use a real STT provider from item 1. No fake transcripts.
- Pipecat / LiveKit are not needed for the first items — plain STT streaming is enough. They become relevant when we need turn detection and slicing (item 3).
- PydanticAI for structured extraction is optional early on; can start with simpler extraction and add it later.
- Happy path first. Error handling and edge cases can come later.
- This project can become a public repo showcasing different approaches.

## Item Map

| Item | Adds | App behavior | Technical unlock | Notes |
| --- | --- | --- | --- | --- |
| 1 | `Live transcript in browser` | The user opens the web app, clicks Start, speaks, and sees their words appear as a live transcript on screen. The user clicks Stop when done. | Streaming STT working end-to-end: browser mic → STT provider → transcript displayed in browser. No Pipecat/LiveKit needed yet — direct STT API integration is enough. | This is the first spike. The user sees nothing about todos yet — just proof that live voice → text works. |
| 2 | `Extract todos on stop` | The user clicks Stop. Todos are extracted from the full transcript and appear as a list below the transcript. | Structured extraction from a complete transcript. Can use a simple prompt or PydanticAI. The Stop button is the trigger — no turn detection needed yet. | This introduces the extraction layer (PydanticAI or not) as a separate concern from STT. |
| 3 | `Todos appear while speaking` | Todos appear incrementally while the user is still talking, without waiting for Stop. The user can still click Stop to finalize. | Turn detection / utterance-end logic: decide when text is stable enough to extract from. This is where Pipecat or LiveKit becomes relevant — they provide VAD, turn strategies, and interim/final transcript framing. | Key design question: when to trigger extraction? On every final utterance? On silence gaps? On sentence boundaries? These are different techniques for deciding when to process a partial. The Pipecat vs LiveKit decision happens here. |
| 4 | `Tentative vs confirmed todos` | Todos that are still forming show as tentative (visually distinct). Once the transcript stabilizes, they become confirmed. | Tentative/confirmed state management. Dedup logic so the same todo doesn't appear twice as the transcript refines. | This is where the interim-result handling from Deepgram/AssemblyAI docs becomes concrete. |

## Reading The Map

- Item `1` = prove live STT works in the browser. Simplest possible setup.
- Item `2` = add extraction as a separate layer, gated by a Stop button. No real-time complexity yet.
- Item `3` = remove the Stop button dependency. This is the core slicing problem and the main technical learning goal. Pipecat / LiveKit decision happens here.
- Item `4` = tackle tentative state and dedup — the hardest UX/technical problem.

The progression is deliberate: each item adds exactly one layer of complexity. Item `1` is STT only. Item `2` adds extraction but keeps triggering trivial (button click). Item `3` makes triggering automatic — that's the hard part. Item `4` refines how the results look while the transcript is still unstable.
