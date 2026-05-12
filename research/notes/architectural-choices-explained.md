# Architectural Choices Explained

This document explains the key architectural decisions in the voice-todos codebase. Each section is a self-contained question that can be read independently. Together, they build a complete picture of why the system is shaped the way it is.

## How do the backend files work together?

The backend has a small number of files, each with a specific role:

| File | Role |
|---|---|
| **main.py** | Entry point. Sets up FastAPI, CORS, logging, mounts the WebSocket router. |
| **config.py** | Loads environment variables (`soniox_api_key`, `gemini_api_key`, `record_sessions`, timeouts) through a single `get_settings()` function. |
| **models.py** | Defines `Todo` and `ExtractionResult` as Pydantic models with typed fields (`due_date` is a `date`, not a string). |
| **ws.py** | The WebSocket endpoint. Bridges the browser, Soniox, and extraction. Owns session lifecycle. |
| **transcript_accumulator.py** | Turns the stream of speech events from Soniox into one coherent transcript. |
| **extraction_loop.py** | Decides when to extract todos (on pauses, after enough new words, on stop). Collapses redundant requests. |
| **extract.py** | Calls Gemini with transcript + datetime context + previous todos. Returns structured todos. Stateless. |
| **session_recorder.py** | Opt-in recording of audio, Soniox messages, and results for debugging and replay tests. |

The data flows in one direction:

```
Browser (mic audio + control messages)
    |
    v
ws.py  --- relays audio ---------> Soniox
                                      |
                                      | speech events
                                      v
ws.py (_relay_soniox_to_browser) <----'
    |
    | 1. feeds speech events into TranscriptAccumulator
    | 2. notifies ExtractionLoop ("speaker paused" or "new words arrived")
    v
ExtractionLoop (decides IF and WHEN to extract)
    |
    | calls extract_fn(transcript)
    v
extract.py (calls Gemini, returns [Todo, ...])
    |
    | calls send_fn(todos)
    v
ws.py (send_todos) --> browser_ws.send_json({"type": "todos", ...})
    |
    v
Browser receives todos
```

**`ws.py` is the hub.** It is the only file that talks to the outside world (browser WebSocket + Soniox WebSocket). Everything else is an internal collaborator that `ws.py` wires together.

## How is the code decoupled?

A natural question when looking at the diagram above: if `extract.py` is stateless and just generates todos, who is responsible for sending them to the browser?

The answer is that `ws.py` wires everything together at construction time using **callbacks**. When it creates the `ExtractionLoop`, it passes in two functions:

```python
extraction_loop = ExtractionLoop(
    transcript=transcript,
    send_fn=send_todos,       # "here's how to send todos to the browser"
    extract_fn=extract_todos,  # "here's how to extract todos from text"
    token_threshold=TOKEN_THRESHOLD,
)
```

`ExtractionLoop` does not know about WebSockets, Gemini, or browsers. It only knows the shape of those two functions: one takes a transcript and returns todos, the other takes todos and delivers them somewhere. When extraction finishes, the loop calls `self._send_fn(todos)`, which happens to be the `send_todos` function that writes to the browser WebSocket.

This is a form of **dependency injection**. The responsibilities split like this:

- **`ws.py`** is the wiring layer — it connects everything and defines *what* happens
- **`ExtractionLoop`** is the timing/concurrency layer — it decides *when* and *how often*
- **`extract.py`** is pure computation — it does the work when asked

### What are the alternatives?

**Direct coupling (simpler, but rigid).** `ExtractionLoop` could directly import `extract_todos` and hold a reference to `browser_ws`. Easier to read — you follow the flow in one file. But testing would require mocking WebSocket objects and patching module imports. Any change to how todos are delivered would require modifying the loop itself.

**Event/observer pattern (more flexible, heavier).** The loop could emit events and let multiple listeners subscribe. More flexible — easy to add a logger, a database writer, anything. But it requires an event system, subscription management, and per-listener error handling. For a system with exactly one consumer (the browser), it is over-engineering.

**Message queue (fully decoupled, more moving parts).** The loop could put todos on an `asyncio.Queue` and `ws.py` could consume from a separate task. Fully separates producing from consuming. But `ws.py` would need to manage an additional consumer task and coordinate its shutdown.

**Why callbacks are the right fit:** the system has exactly one producer (Gemini) and one consumer (the browser). Callbacks give decoupling and testability without the overhead of a pub/sub system or a queue. The one trade-off is readability for newcomers — when you read `ExtractionLoop` alone, you see `self._send_fn(todos)` but have to go to `ws.py` to find out what that function actually does. That is the cost of decoupling: you trade "I can read one file" for "I can test one file in isolation."

## What happens when the user stops recording?

This was the biggest design correction in the project's history, and it starts with a misunderstanding.

When users stopped recording and their last few words were missing, the first instinct was that audio was being lost between the browser and the backend. That led to experiments with delays and flush timers.

The real problem was elsewhere. Soniox (the speech recognition service) has specific protocol rules. Sending empty bytes (`b""`) means "no more audio." But it does not mean "finalize whatever you are still processing." Soniox needs a separate, explicit `{"type": "finalize"}` message before the stream is ended. Without that, any words Soniox was still working on are silently dropped.

Think of it as hanging up a phone call mid-sentence versus saying "I'm done, go ahead and finish your thought."

There is also a `<fin>` marker that Soniox sends back after finalization. It is protocol metadata, not actual transcript text, so it must be filtered out. And after `<fin>`, any previously tracked in-progress text is stale and must be cleared, or you get duplicated words.

The frontend still has a 200ms mic-tail delay, but that is not what fixes the problem. The fix is explicit finalization. If someone changes stop handling without understanding this, the missing-words bug will come back.

## Where does the transcript live?

Originally the frontend (React) tried to reconstruct the final transcript from the streaming events it received during the session — piecing together what it had seen and trying to preserve trailing text on stop.

That turned out to be the wrong approach. The backend is the one talking to Soniox. It sees the full stream, including the finalization step described above. The frontend is downstream — it only sees what the WebSocket relays, shaped by network and rendering timing.

The current design:

- Live streaming messages are for responsive UI updates — showing text as you speak
- The backend-assembled transcript sent in the `stopped` message is the source of truth for the final session result

This prevents a class of bugs where the UI lost text but the backend had it. If you are changing final transcript behavior, start in `transcript_accumulator.py`, not in the React hook.

## How does speech become text?

`transcript_accumulator.py` is a small file (72 lines), but the architecture treats it as one of the most important in the repo.

Soniox sends a stream of word events as the user speaks. Each word is either **final** (Soniox is confident, this will not change) or **interim** (a best guess that may be revised with the next event). The accumulator's job is to maintain one coherent view of "what has been said so far" from that stream.

It handles three things:

1. **Final words** get appended permanently — they are done
2. **Interim words** replace the previous guess each time — they are always the latest estimate of what is being said right now
3. **Protocol markers** (`<fin>` and `<end>`) get filtered out of the text, but their meaning is captured — `<fin>` means "stream is finalized, clear in-progress text" and `<end>` means "the speaker paused" (which triggers todo extraction)

The `full_text` property combines all final words plus the current in-progress guess into one string. That string is what gets sent to Gemini for todo extraction.

### Why this needed its own module

Before this file existed, the same logic was scattered across different files. Parts lived in `ws.py`, parts were reimplemented differently in tests. That meant the production code could assemble the transcript one way, tests could assemble it a slightly different way, and both could pass while producing different results.

That is a dangerous kind of bug: the tests say everything is fine, but they are testing a different algorithm than what actually runs.

By putting this in one module, the project enforces a rule: there is exactly one definition of how speech events become transcript text. Production uses it. Tests use it. Replay tests use it. Nobody gets to invent their own version.

The pattern here is simpler than the callback injection described earlier. It is just: take logic that is important enough to get wrong, and give it a single home.

## How does the system handle todos that change?

This is a product architecture decision, not just a technical one. It defines what the system fundamentally is.

### The intuitive approach

If you were designing a todo app from scratch, you would probably think in terms of stable objects: each todo gets an ID, changes are sent as updates, the frontend applies them incrementally. That is how most apps work.

### Why it does not work here

The input is a live, growing transcript being interpreted by an LLM. That interpretation is not stable. Imagine someone says:

> "I need to buy groceries... oh and pick up the dry cleaning... actually the dry cleaning is at the same place so just do both at the grocery plaza"

Early in that sentence, a reasonable extraction is two todos. By the end, the correct extraction might be one merged todo. The second should disappear, and the first should change.

What ID did the second todo have? Is merging two todos an "update" to one and a "delete" of the other? What if the LLM reorders them? Trying to maintain stable identity when the LLM can merge, split, reorder, or remove items at any time becomes a mess of tracking logic for a guarantee the system cannot actually provide.

### What the system actually does

Every time extraction runs, Gemini receives the full current transcript and the previous todo list (as context). It returns a complete, fresh todo list — its best current interpretation. The backend sends that entire list to the frontend. The frontend replaces its displayed list wholesale. No diffing, no patching, no IDs.

The system prompt in `extract.py` encodes this explicitly:

- "Return the updated complete list"
- "If new speech adds details to an existing todo, update it in place"
- "If later context shows an earlier todo was over-split, duplicated, misheard... merge or remove it"

### The trade-offs

**What you gain:** simplicity (the frontend just renders whatever arrives), self-correction (the system fixes its own mistakes as more speech arrives), no state to coordinate between backend and frontend.

**What you lose:** no per-item animation (no stable IDs to animate transitions), no per-item history, potential visual flicker if the LLM reorders items between snapshots.

The key realization is that this system is not streaming a growing list of todos. It is repeatedly publishing the best current interpretation of what the user has said so far. Each snapshot replaces the last one, and the last one wins.

## What happens when extraction can't keep up?

Extraction is expensive — it is an LLM call to Gemini that takes seconds. Meanwhile, the user keeps talking, new words keep arriving, and pauses keep being detected. Requests to extract can arrive faster than extraction can complete.

### Three strategies for handling this

**Queue every request.** Process extractions one by one, in order. The problem: by the time you process extraction #2, the transcript has already grown past what #3 and #4 would see. You pay for 4 Gemini calls and only the last result matters.

**Allow parallel extractions.** Start a new one for every request. Even worse — you pay for multiple calls, they can return out of order, and you need logic to determine which result is the freshest.

**Collapse into one re-run (what the system does).** A request arrives. If nothing is running, start an extraction. If one is already running, just note that something changed (a "dirty flag"). When the running extraction finishes, check the flag. If something changed, run one more time with the latest transcript. Repeat until nothing has changed.

Multiple requests collapse into a single re-run. The system does not care how many requests arrived or why. It only asks: "has anything changed since I last extracted?" That is a yes/no question, so it needs only a yes/no flag.

This is a well-known pattern in UI programming (sometimes called coalescing or debouncing), applied at the backend level. React does something similar: if state changes 5 times before the next paint, React does not render 5 times.

### The trade-off

**What you gain:** minimum LLM cost (only call Gemini when the result would actually differ), always current (uses the latest transcript, never a stale one), simple concurrency (no queue, no ordering problems).

**What you lose:** a slight delay when a request arrives while extraction is already running (the user waits for the current extraction to finish before the re-run starts). No history of intermediate states.

## What is the stop sequence?

"The user clicked stop" and "the system is done" are not the same moment. There is a precise sequence of steps between those two events.

When the user clicks stop, here is what has to happen, in order:

```
User clicks stop
    |
    v
1.  Send {"type": "finalize"} to Soniox
    |   "finish processing whatever you are still working on"
    v
2.  Send b"" to Soniox
    |   "no more audio is coming"
    v
3.  Wait for the relay task to finish (with timeout)
    |   Soniox sends back final tokens.
    |   TranscriptAccumulator processes them.
    v
4.  Call extraction_loop.on_stop()
    |   Waits for any in-flight extraction.
    |   Runs one final extraction on the now-complete transcript.
    v
5.  Send the final "todos" snapshot
    |   Either fresh from step 4, or last known good if step 4 failed.
    v
6.  Send "stopped" with the full transcript
    |   Plus a "warning" field if anything went wrong.
    v
Done. NOW the system is done.
```

### The protocol guarantee

The contract with the frontend is: you always receive `todos` before `stopped`, and `stopped` means everything is truly finished.

If `stopped` was sent immediately when the user clicked the button, the frontend would think the session was over while Soniox might still be finalizing, an extraction might still be in flight, and the final pass on complete text would not have happened.

### Failure handling

Three things can go wrong, and each is handled honestly:

**Soniox takes too long to finalize.** The relay task gets a timeout. If it expires, the task is cancelled and a warning is set. The system continues with whatever it has.

**Final extraction fails.** A warning is set. The system re-sends the last known good todo snapshot instead of an empty list. An empty list would falsely communicate "there are no todos" when the truth is "the final refinement failed."

**No todos were ever extracted.** The system still sends a `todos` message (the last known snapshot, possibly empty) before `stopped`, keeping the protocol consistent.

Stop is a convergence point. The system is not done when the user expresses intent. It is done when the speech service has fully flushed, the interpretation layer has had its shot, the result has been delivered, and any problems have been communicated.

## What counts as reliability in this project?

This is not about polishing after the feature works. The project treats reliability as a set of architectural boundaries that define what the system is and is not allowed to do.

### Four decisions that shape what "reliable" means

**Session recording is opt-in.** The system can record raw mic audio, Soniox messages, and results to disk — useful for debugging and replay tests. Originally this was always on. The problem: you are silently writing voice recordings to the filesystem. That is a privacy decision, not a logging detail. It is now behind `record_sessions = False` by default.

**Warnings are surfaced, not swallowed.** When stop degrades, the `stopped` message includes a `warning` field. Many apps hide degradation because it looks bad. This project chooses honesty over cosmetics.

**Default tests are deterministic and vendor-independent.** Running `pytest` does not call Soniox or Gemini. The default suite uses fakes and replay data. It runs offline, in CI, on a plane, and always gives the same answer.

**Runtime controls are explicit.** Timeouts, recording flags, and API keys are loaded through one `get_settings()` function, not scattered as module-level globals. Tests can override them cleanly and runtime policy is visible in one place.

If you remove any of these, the system still works — but it becomes harder to trust. Tests might pass because Gemini happened to be fast that day. A recording might be written that nobody expected. A failure might be hidden that the user should know about.

## How is the test suite designed?

### The core principle: test real behavior, fake the outside world

The project moved away from shallow tests — tests that replace the core logic with a fake and then check that the fake did what you told it to. For example, an early version of the extraction tests mocked the Gemini agent, told the mock to return certain todos, called the function, and asserted it returned those todos. That proves nothing about actual extraction behavior.

The corrected principle: the code you wrote stays real in tests. The external services you call (Soniox, Gemini) get faked.

| Component | In tests | Why |
|---|---|---|
| TranscriptAccumulator | Always real | It is our logic. Replacing it with a fake hides the bugs we want to catch. |
| ExtractionLoop | Always real | Its value is timing and concurrency behavior. Replacing it tests nothing. |
| Soniox | Usually faked | External service we do not control. Tests would be unpredictable. |
| Gemini | Usually faked | External, slow, and gives different answers each time. |
| WebSocket message flow in ws.py | Real (via TestClient) | Message ordering is a core guarantee worth proving. |

### The four layers

**Layer 1: Our logic (always runs, no network needed)**

- `test_transcript_accumulator.py` — does speech-to-text assembly work correctly?
- `test_extraction_loop.py` — does the dirty flag collapse? Does stop wait properly? Does the final pass happen?
- `test_models.py` — do the data models validate correctly?
- `test_config.py` — does settings loading work?

These run in milliseconds, offline. They prove that the code does what we think it does.

**Layer 2: Message flow (always runs, Soniox and Gemini faked)**

- `test_ws.py` — runs the real WebSocket endpoint with faked external services. Proves message ordering (`started` then `todos` then `stopped`), error handling, timeout behavior, and the stop sequence.
- `test_extract.py` (non-Gemini tests) — checks that the prompt sent to Gemini includes the right context (date, timezone, previous todos) and that empty input is handled correctly. Does not call Gemini.

**Layer 3: Replay (always runs, uses recorded sessions)**

- `test_replay.py` — takes real Soniox session recordings (saved as files) and plays them through the transcript accumulator. No network, fully deterministic, but uses real-world speech patterns rather than hand-crafted examples.

**Layer 4: Real services (opt-in, requires API keys)**

- `test_soniox_integration.py` — sends real audio to real Soniox. Requires `SONIOX_API_KEY` + `RUN_SONIOX_INTEGRATION=1`.
- `test_e2e.py` — full pipeline: real audio, real Soniox, real Gemini, real todos. Requires both API keys + `RUN_E2E_INTEGRATION=1`.
- `test_extract.py` (Gemini tests) — calls real Gemini with real transcripts. Requires `GEMINI_API_KEY` + `RUN_GEMINI_INTEGRATION=1`.

These are the tests closest to real user scenarios. They are valuable but opt-in because they are slow, can fail for reasons outside our control, and cost money per call.

### How the architecture enables the testing strategy

The testing layers above are not just a policy choice. They are made possible by how the code is structured:

- **TranscriptAccumulator is a standalone module** so you can test it by feeding speech events and checking the output. If this logic were mixed into `ws.py`, you would need a full WebSocket session just to test how words are assembled.

- **ExtractionLoop takes callbacks** so you can test its timing behavior by passing in simple fake functions. If it directly called Gemini and wrote to the browser, you would need both services running just to test when extraction happens.

- **extract.py separates prompt building from the LLM call** so you can test "does the prompt include the timezone?" without calling Gemini. The prompt is where our design decisions live. The LLM response is Gemini's job.

- **ws.py uses FastAPI's TestClient** so the message flow runs against a real HTTP stack with faked services behind it. You test the orchestration without needing the orchestra.

### The layered trust model

```
Most trust    |  Our logic + message flow (layers 1-2)
              |  Always run. Always same result. Prove our own code works.
              |
              |  Replay tests (layer 3)
              |  No network. Prove our code handles real-world speech patterns.
              |
              |  Real services (layer 4, opt-in)
Least trust   |  Prove the full pipeline works. Can fail for external reasons.
```

Layers 1-3 answer: "does our code work?" Layer 4 answers: "does the whole pipeline work?" Day-to-day, layers 1-3 are what you rely on.
