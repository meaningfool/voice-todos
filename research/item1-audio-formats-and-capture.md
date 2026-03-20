# Audio Formats, Frames, and Capture

Research covering topics 1 (Audio Formats and Frames) and 5 (Audio Capture and the Web Audio API) from the research index. These topics are closely related — formats determine what the capture pipeline produces.

## Audio Fundamentals

Audio is a series of numbers representing air pressure over time.

- **Sample:** one measurement of air pressure at a point in time
- **Sample rate:** measurements per second. 16 kHz = 16,000 samples/second
- **Bit depth:** bits per sample. 16-bit = integers from -32,768 to +32,767
- **Channels:** mono (1) or stereo (2). Speech is always mono

## What "Frame" Means (Three Different Things)

The word "frame" is overloaded across three domains. There is no formal layered model — it's just the same word borrowed independently by each context.

1. **Codec frame** — from audio engineering. The smallest unit a codec encodes/decodes. An Opus frame is typically 20ms of audio (320 samples at 16 kHz). Raw PCM has no codec frames — it's a continuous stream. This term is well-defined within codec specifications (e.g., the Opus RFC).

2. **Processing buffer** — from real-time audio programming. Hardware and software work in chunks for efficiency. The Web Audio API's AudioWorklet always receives 128 samples at a time (the spec calls this a "render quantum," but nobody uses that term). People call these "frames," "blocks," or "buffers" interchangeably.

3. **WebSocket message** — from the networking protocol. WebSocket has its own framing at the protocol level. "Binary frames" in our design spec means WebSocket binary messages, each carrying a blob of audio bytes.

In our app, all three are in play simultaneously.

## PCM vs Opus (via WebM): The Trade-Off

The AudioWorklet always produces the same thing: 128 float32 samples. The WebSocket always carries a blob of bytes. What differs is what happens in between — whether you use a codec.

### Raw PCM (our choice)
- Float samples scaled to 16-bit integers, packed as bytes. 128 samples = 256 bytes.
- No compression, no encoding, no container.
- Server reads the bytes directly and forwards to Soniox.
- ~32 KB/s bandwidth (tiny by modern standards).
- Zero encoding latency.
- Easy to debug — raw bytes are human-interpretable.

### Opus via MediaRecorder
- Browser compresses audio using Opus codec, wraps in WebM container.
- ~2-4 KB/s bandwidth (significant compression).
- Adds 20-40ms encoding latency (Opus needs a full 20ms frame before compressing).
- MediaRecorder controls chunk timing, not you — `ondataavailable` fires unpredictably.
- If the receiving service (Soniox) expects PCM, the server must decode Opus back to PCM — adding a dependency (ffmpeg or Opus decoder) and CPU work.
- Harder to debug: encoding, container, or decoding could each be the problem.

### When Opus makes sense
- Many concurrent users where bandwidth costs matter
- Constrained mobile networks
- The receiving service natively accepts Opus (skipping the decode step)

For a single-user app talking to Soniox over a local connection, raw PCM is the clearly better choice.

## Audio Capture in the Browser

### The pipeline

```
Mic hardware (48 kHz) → getUserMedia → MediaStream
    → connect to AudioContext (16 kHz) → browser resamples automatically
    → AudioWorklet receives 128 samples at 16 kHz as float32 (-1.0 to +1.0)
    → worklet converts float32 → int16 (multiply by 32767)
    → send bytes over WebSocket
```

### getUserMedia

`getUserMedia({ audio: true })` asks the OS for the default microphone and returns a `MediaStream`. The stream produces raw samples at the hardware's native rate (typically 44.1 kHz or 48 kHz).

Constraints like `sampleRate`, `channelCount`, `echoCancellation` are *requests*, not guarantees. The browser may ignore them.

`getUserMedia` only captures the local microphone. It does not capture remote audio from a call, system sounds, or other apps. Those are entirely separate audio paths.

### AudioContext and resampling

`new AudioContext({ sampleRate: 16000 })` tells the Web Audio API to run its graph at 16 kHz. When the mic stream (48 kHz) feeds into this context, the browser resamples automatically and transparently.

### The Web Audio API graph model

The API is built around a directed graph: source nodes produce audio, processing nodes transform it, and a destination node represents the speakers. You connect them with `.connect()`.

For capture-only use (no playback), the graph should be:

```
getUserMedia (mic source) → AudioWorklet (grab samples)
```

**Not** connected to `audioContext.destination`. Connecting to the destination plays the mic audio through the speakers — causing echo or feedback. This was a bug we hit: the worklet was accidentally connected to the speakers.

### What you don't control

- **Format:** always float32 in -1.0 to +1.0. The int16 conversion is your code's job.
- **Buffer size:** always 128 samples per AudioWorklet callback. Not configurable. At 16 kHz, that's 8ms of audio.
- **Exact sample rate from the mic:** the browser decides based on hardware. The AudioContext resampling handles the conversion.

## Native Platform Equivalents

The concepts are the same (capture mic, get samples, send bytes). The APIs differ significantly.

### iOS (AVAudioEngine)
- Graph-based model like Web Audio API. Install a "tap" on the input node to receive sample buffers.
- You specify exact sample rate, buffer size, and format — precise control, not suggestions.
- Must manage `AVAudioSession` — declares how the app uses audio (recording, playback, both), affects interaction with other apps, Bluetooth routing, ringer switch. Nothing like this exists in the browser.
- Can request 16-bit PCM directly from capture — no float-to-int conversion needed.

### Android (AudioRecord)
- No graph model. Lower-level: open the mic, loop calling `read()` to pull sample buffers.
- Specify sample rate, format (16-bit PCM), and buffer size upfront. You get exactly what you ask for.
- `Oboe` (Google's C++ library) available for lower-latency capture. `AudioRecord` is the standard choice for speech.
- Also provides 16-bit PCM directly.

### Key differences from browser
- **Control:** native gives precise control over sample rate and buffer size. Browser gives suggestions.
- **Latency:** native achieves 5-10ms. Browser's 128-sample quantum is 8ms but has additional pipeline latency you can't control.
- **Background:** mobile OSes may interrupt or suspend audio capture when the app goes to background. Browser has similar tab-throttling issues.
- **Format:** native APIs can deliver 16-bit PCM directly from capture — no float-to-int conversion step.

### What this means for a future native version
The Soniox integration and WebSocket transport stay identical — still sending 16-bit PCM bytes. Only the audio capture layer changes, and it would actually be simpler on native.
